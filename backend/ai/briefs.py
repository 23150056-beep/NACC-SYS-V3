"""Pre-session brief assembly, shared by the on-demand view and the prefetcher (F2)."""
import threading
from datetime import date

from django.db import connection
from django.utils import timezone

from ai import prompts
from ai.models import AIJob
from ai.services import AIUnavailable, run_job


def _age(child):
    if not child.birth_date:
        return "unknown"
    today = date.today()
    years = today.year - child.birth_date.year - (
        (today.month, today.day) < (child.birth_date.month, child.birth_date.day))
    return str(years)


def build_brief_prompt(child):
    pa = child.pre_assessments.filter(status="completed").first()
    result = child.result_entries.first()
    remarks = list(child.remarks.all()[:5])
    problems = list(child.problems.filter(resolved=False)[:6])
    survey = child.opinionnaire_invites.filter(status="submitted").first()
    survey_text = "\n".join(
        f"- {q}: {str(a)[:300]}" for q, a in (survey.answers or {}).items()
    ) if survey else "- not answered yet"
    return prompts.BRIEF.format(
        opinionnaire=survey_text,
        first_name=child.fullname.split(" ")[0] if child.fullname else "the child",
        age=_age(child),
        gender=child.gender or "unspecified",
        case_type=child.case_type or "unspecified",
        pre_assessment=(f"{pa.date}, instruments: "
                        f"{', '.join(i.title for i in pa.instruments.all()) or 'none'}"
                        if pa else "none completed"),
        latest_result=(f"{result.classification or ''} — {result.summary[:400]}"
                       if result else "none"),
        problems="; ".join(p.description for p in problems) or "none open",
        remarks="\n".join(f"- {r.date}: {r.text[:200]}" for r in remarks) or "- none",
    )


_inflight_lock = threading.Lock()
_inflight = set()


def latest_brief_job(child_id):
    """Newest successful brief for this child generated today, or None."""
    return AIJob.objects.filter(
        job_type="brief", input_ref=f"child:{child_id}", ok=True,
        created_at__date=timezone.localdate()).order_by("-created_at").first()


def prefetch_briefs(children, user):
    """Generate today-briefs for the given children in one background thread.
    Returns (queued_ids, skipped_ids). Ollama on CPU must never run concurrent
    generations, so all work is sequential inside a single daemon thread."""
    queued, skipped = [], []
    with _inflight_lock:
        for child in children:
            if child.id in _inflight or latest_brief_job(child.id):
                skipped.append(child.id)
            else:
                _inflight.add(child.id)
                queued.append(child)
    if queued:
        threading.Thread(target=_generate_all, args=(queued, user), daemon=True).start()
    return [c.id for c in queued], skipped


def _generate_all(children, user):
    try:
        for child in children:
            try:
                run_job("brief", f"child:{child.id}", build_brief_prompt(child),
                        prompts.SYSTEM, user)
            except AIUnavailable:
                pass  # audit row already logged by run_job; prefetch is best-effort
            finally:
                with _inflight_lock:
                    _inflight.discard(child.id)
    finally:
        if not connection.in_atomic_block:  # tests run inside a transaction
            connection.close()
