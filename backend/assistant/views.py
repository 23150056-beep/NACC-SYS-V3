import logging
import threading

from django.db import connection
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import Role
from accounts.permissions import IsAdministrator
from assistant import prompts
from assistant.models import AssistantJob, AssistantSetting
from assistant.serializers import AssistantSettingSerializer
from assistant.services import AIUnavailable, DISCLAIMER, gate, run_job
from children.models import Child
from scheduling.models import Appointment

logger = logging.getLogger(__name__)


def _role(request):
    return getattr(getattr(request.user, "role", None), "role_name", None)


class AssistantBaseView(generics.GenericAPIView):
    """Turns AIUnavailable into a 503 for every assistant endpoint.

    503 rather than 500: the assistant being off, or the runtime being
    unreachable, is a normal state of this system, not a fault.
    """
    permission_classes = [IsAuthenticated]

    def handle_exception(self, exc):
        if isinstance(exc, AIUnavailable):
            return Response({"detail": str(exc)},
                            status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return super().handle_exception(exc)


class AssistantSettingView(AssistantBaseView):
    """Read/update the singleton. Administrator only — this switch decides
    whether case text reaches a model at all."""
    permission_classes = [IsAdministrator]
    serializer_class = AssistantSettingSerializer

    def get(self, request):
        return Response(AssistantSettingSerializer(AssistantSetting.load()).data)

    def put(self, request):
        serializer = AssistantSettingSerializer(
            AssistantSetting.load(), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class RemarkPolishView(AssistantBaseView):
    """Polish a remark the psychologist is writing. Returns a draft only —
    nothing is saved to the remark until the human saves it themselves."""

    def post(self, request):
        gate("feature_remark_polish")
        raw = (request.data.get("text") or "").strip()
        if not raw:
            return Response({"detail": "Nothing to polish."},
                            status=status.HTTP_400_BAD_REQUEST)
        draft, job = run_job(
            "remark_polish",
            prompts.build_remark_prompt(raw),
            system=prompts.REMARK_POLISH_SYSTEM,
            input_ref="remark:draft",
            user=request.user)
        return Response({"draft": draft, "job_id": job.id,
                         "disclaimer": DISCLAIMER})


class AssistantJobFeedbackView(AssistantBaseView):
    """Record what the human did with a draft. Deliberately does NOT gate on
    the feature flags: it writes history, and history must stay recordable
    after an administrator switches the assistant off."""

    def post(self, request, job_id):
        outcome = request.data.get("outcome")
        valid = {AssistantJob.ACCEPTED, AssistantJob.EDITED, AssistantJob.DISCARDED}
        if outcome not in valid:
            return Response({"detail": f"outcome must be one of {sorted(valid)}."},
                            status=status.HTTP_400_BAD_REQUEST)
        qs = AssistantJob.objects.all()
        if _role(request) != Role.ADMINISTRATOR:
            qs = qs.filter(created_by=request.user)
        try:
            job = qs.get(pk=job_id)
        except AssistantJob.DoesNotExist:
            return Response({"detail": "Not found."},
                            status=status.HTTP_404_NOT_FOUND)
        job.outcome = outcome
        job.save(update_fields=["outcome"])
        return Response({"outcome": job.outcome})


def _visible_children(request):
    """Children this user may see — the same rule as _ChildScopedClinicalViewSet.

    Scope always comes from request.user. No endpoint accepts an
    "assigned to me" parameter, so no caller can widen its own view.
    """
    qs = Child.objects.all()
    if _role(request) == Role.PSYCHOLOGIST:
        qs = qs.filter(assigned_psychologist=request.user)
    return qs


class PreSessionBriefView(AssistantBaseView):
    """Generate a brief now. This is the ~40s path — the UI reaches for
    LatestBriefView first and only falls back to here."""

    def post(self, request, child_id):
        gate("feature_brief")
        try:
            child = _visible_children(request).get(pk=child_id)
        except Child.DoesNotExist:
            return Response({"detail": "Not found."},
                            status=status.HTTP_404_NOT_FOUND)
        draft, job = run_job(
            "brief",
            prompts.build_brief_prompt(child),
            system=prompts.BRIEF_SYSTEM,
            input_ref=f"child:{child.id}",
            user=request.user)
        return Response({"draft": draft, "job_id": job.id,
                         "generated_at": job.created_at,
                         "disclaimer": DISCLAIMER})


class LatestBriefView(AssistantBaseView):
    """Today's already-generated brief, served instantly.

    Reads history only, so it deliberately does NOT gate: a brief drafted this
    morning stays readable after an administrator switches the assistant off.
    """

    def get(self, request, child_id):
        try:
            child = _visible_children(request).get(pk=child_id)
        except Child.DoesNotExist:
            return Response({"detail": "Not found."},
                            status=status.HTTP_404_NOT_FOUND)
        job = AssistantJob.objects.filter(
            job_type="brief", input_ref=f"child:{child.id}", ok=True,
            created_at__date=timezone.localdate()).first()
        if not job:
            return Response({"detail": "No brief drafted today."},
                            status=status.HTTP_404_NOT_FOUND)
        return Response({"draft": job.output_text, "job_id": job.id,
                         "generated_at": job.created_at,
                         "disclaimer": DISCLAIMER})


# Children currently being briefed, so two page loads cannot queue the same
# child twice. Guarded by its own lock; the generation lock lives in services.
_IN_FLIGHT = set()
_IN_FLIGHT_LOCK = threading.Lock()


def _generate_briefs_now(child_ids, user):
    """Generate briefs one at a time. Never raises.

    Sequential on purpose: the runtime is CPU-only and concurrent generations
    make every request slower rather than parallel.
    """
    try:
        for child_id in child_ids:
            child = Child.objects.filter(pk=child_id).first()
            if not child:
                continue
            try:
                run_job("brief", prompts.build_brief_prompt(child),
                        system=prompts.BRIEF_SYSTEM,
                        input_ref=f"child:{child.id}", user=user)
            except AIUnavailable:
                # Already audited by run_job. A runtime that is down must not
                # abandon the rest of the queue.
                logger.info("Prefetch skipped child %s: runtime unavailable", child_id)
    finally:
        with _IN_FLIGHT_LOCK:
            _IN_FLIGHT.difference_update(child_ids)


def _start_prefetch_thread(child_ids, user):
    def worker():
        try:
            _generate_briefs_now(child_ids, user)
        finally:
            # A thread owns its own connection and must hand it back.
            connection.close()

    threading.Thread(target=worker, daemon=True).start()


class PrefetchBriefsView(AssistantBaseView):
    """Draft briefs ahead of today's sessions so the button press is instant.

    Returns immediately. The caller ignores the result — this is fire and
    forget, and a failure here must never be visible on the schedule screen.
    """

    def post(self, request):
        gate("feature_brief")
        today = timezone.localdate()
        visible = _visible_children(request)
        appts = Appointment.objects.filter(
            child__in=visible, status=Appointment.SCHEDULED,
            start__date=today)
        if _role(request) == Role.PSYCHOLOGIST:
            appts = appts.filter(psychologist=request.user)

        child_ids = list(dict.fromkeys(appts.values_list("child_id", flat=True)))
        already = set(AssistantJob.objects.filter(
            job_type="brief", ok=True, created_at__date=today,
            input_ref__in=[f"child:{cid}" for cid in child_ids]
        ).values_list("input_ref", flat=True))

        queued, skipped = [], []
        with _IN_FLIGHT_LOCK:
            for cid in child_ids:
                if f"child:{cid}" in already or cid in _IN_FLIGHT:
                    skipped.append(cid)
                else:
                    _IN_FLIGHT.add(cid)
                    queued.append(cid)

        if queued:
            _start_prefetch_thread(queued, request.user)
        return Response({"queued": queued, "skipped": skipped})
