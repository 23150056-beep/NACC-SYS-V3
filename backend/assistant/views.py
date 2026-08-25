from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import IsAdministrator
from assistant import prompts
from assistant.models import AssistantSetting
from assistant.serializers import AssistantSettingSerializer
from assistant.services import AIUnavailable, DISCLAIMER, gate, run_job


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
