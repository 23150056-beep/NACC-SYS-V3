# AI Utilization Upgrades Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the live local-AI layer materially more useful: harden the brief prompt (F1), pre-generate briefs for today's appointments (F2), wire the dormant case-study AI summary (F3), and track draft outcomes with an admin metrics panel (F4).

**Architecture:** All work stays inside the existing `ai` Django app + three React pages. F2 uses one guarded daemon thread (no queue infra). F4 adds one `AIJob.outcome` field and two endpoints. Every feature keeps the existing invariants: flag-gated, 503 degradation, drafts only, `AIJob` audit, minimal prompt data.

**Tech Stack:** Django 5.1 / DRF, React 18 + Vite, Ollama (`qwen2.5:3b-instruct`), SQLite dev DB.

**Repo:** `C:\Users\User\Desktop\NACC SYS\NACC-V2` (its own git repo — run all git commands there).
**Spec:** `docs/superpowers/specs/2026-07-09-ai-utilization-upgrades-design.md`
**Run tests:** from `backend\`: `venv\Scripts\python.exe manage.py test ai -v 1` (full suite: `manage.py test`). 184 tests green before this work.
**Commit rule (user convention):** commits are authored by the user ONLY — never add a `Co-Authored-By` trailer of any kind.
**Backend runs `--noreload`** in the preview config — restart `v2-backend` after backend edits when live-checking.

### File map

| File | Change |
|---|---|
| `backend/ai/prompts.py` | BRIEF gains Age/Sex lines + anti-guessing instruction; new CASE_STUDY prompt |
| `backend/ai/briefs.py` | **new** — `build_brief_prompt`, `latest_brief_job`, `prefetch_briefs` |
| `backend/ai/services.py` | `_normalize_output` applied in `run_job` |
| `backend/ai/models.py` | `AIJob.outcome` + constants; `case_study` TYPE_CHOICES entry |
| `backend/ai/views.py` | brief view uses helper; 5 new views (latest, prefetch, case-study draft/confirm, feedback, metrics) |
| `backend/ai/urls.py` | routes for the new views |
| `backend/ai/migrations/0002_*.py`, `0003_*.py` | generated |
| `backend/ai/tests/test_ai.py` | new test classes per task |
| `frontend/src/pages/ChildProgressReport.jsx` | instant brief + regenerate, brief thumbs, polish outcome, case-study AI summary |
| `frontend/src/pages/Schedule.jsx` | prefetch on load; brief button in appointment detail |
| `frontend/src/pages/AgencySummary.jsx` | narrative thumbs |
| `frontend/src/pages/Settings.jsx` | admin AI usage panel |

---

### Task 1: F1 — prompt grounding + output normalization (backend)

**Files:**
- Create: `backend/ai/briefs.py`
- Modify: `backend/ai/prompts.py`, `backend/ai/services.py`, `backend/ai/views.py` (PreSessionBriefView)
- Test: `backend/ai/tests/test_ai.py`

- [ ] **Step 1: Make FakeClient record prompts** — in `test_ai.py`, extend the existing `FakeClient` (additive; existing tests unaffected):

```python
class FakeClient:
    available = True

    def __init__(self, reply="Drafted text."):
        self.reply = reply
        self.prompts = []

    def generate(self, prompt, system=None):
        self.prompts.append(prompt)
        return self.reply
```

- [ ] **Step 2: Write the failing tests** — append to `test_ai.py`:

```python
class PromptHardeningTest(AIBase):
    @patch("ai.services.get_ai_client")
    def test_brief_prompt_includes_age_and_gender(self, mock_get):
        from datetime import date
        fake = FakeClient()
        mock_get.return_value = fake
        self._enable()
        self.child.birth_date = date(2018, 3, 1)
        self.child.gender = "Female"
        self.child.save()
        self._auth("p@racco1.gov.ph")
        resp = self.client.post(f"/api/ai/brief/child/{self.child.id}/")
        self.assertEqual(resp.status_code, 200)
        prompt = fake.prompts[0]
        self.assertIn("Sex/gender: Female", prompt)
        self.assertRegex(prompt, r"Age: \d+")
        self.assertIn("Do not state age, gender, or any other detail", prompt)

    @patch("ai.services.get_ai_client")
    def test_brief_prompt_unknown_when_missing(self, mock_get):
        fake = FakeClient()
        mock_get.return_value = fake
        self._enable()
        self._auth("p@racco1.gov.ph")
        self.client.post(f"/api/ai/brief/child/{self.child.id}/")
        prompt = fake.prompts[0]
        self.assertIn("Age: unknown", prompt)
        self.assertIn("Sex/gender: unspecified", prompt)

    def test_normalize_output(self):
        from ai.services import _normalize_output
        self.assertEqual(
            _normalize_output("Mika’s day — all “fine” now"),
            "Mika's day - all \"fine\" now")

    @patch("ai.services.get_ai_client")
    def test_run_job_normalizes(self, mock_get):
        mock_get.return_value = FakeClient(reply="Mika’s ok")
        self._enable()
        self._auth("p@racco1.gov.ph")
        resp = self.client.post("/api/ai/polish-remark/", {"text": "x"}, format="json")
        self.assertEqual(resp.data["draft"], "Mika's ok")
```

- [ ] **Step 3: Run to verify failure** — `venv\Scripts\python.exe manage.py test ai.tests.test_ai.PromptHardeningTest -v 1` → FAIL (no `Sex/gender` in prompt; no `_normalize_output`).

- [ ] **Step 4: Create `backend/ai/briefs.py`:**

```python
"""Pre-session brief assembly, shared by the on-demand view and the prefetcher (F2)."""
from datetime import date

from ai import prompts


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
```

(This is the body of `PreSessionBriefView.post` moved verbatim, plus the two new fields.)

- [ ] **Step 5: Update `prompts.BRIEF`** — replace the whole template with:

```python
BRIEF = """Write a pre-session brief (max 150 words) for the psychologist who
is about to see this child. Summarize current status, recent findings, open
problems, and one or two suggested focus points for today's session.

Child (first name): {first_name}
Age: {age}
Sex/gender: {gender}
Case type: {case_type}
Latest pre-assessment: {pre_assessment}
Latest result entry: {latest_result}
Open problems: {problems}
Recent remarks:
{remarks}
Child's own answers to the agency self-report opinionnaire (verbatim; note any
recurring emotional keywords or distress indicators):
{opinionnaire}

Use only the facts provided above. Do not state age, gender, or any other detail
not given. Refer to the child by first name only.
"""
```

- [ ] **Step 6: Add normalization to `services.py`** — above `run_job`:

```python
_PUNCT_MAP = {"‘": "'", "’": "'", "“": '"', "”": '"',
              "–": "-", "—": "-", " ": " "}


def _normalize_output(text):
    """Small local models emit curly quotes/dashes that render as mojibake in
    some consoles and PDFs — normalize deterministically instead of prompting."""
    for bad, good in _PUNCT_MAP.items():
        text = text.replace(bad, good)
    return text
```

and inside `run_job`, right after `text = client.generate(...)` succeeds (i.e., after the try/except block, before latency is computed is fine too — just before the `AIJob.objects.create` for the ok path):

```python
    text = _normalize_output(text)
```

- [ ] **Step 7: Refactor `PreSessionBriefView.post`** in `views.py` — delete the inline prompt assembly (the `pa = …` through `prompt = prompts.BRIEF.format(...)` block) and replace with:

```python
        from ai.briefs import build_brief_prompt
        prompt = build_brief_prompt(child)
```

(Put the import at the top of the file with the others: `from ai.briefs import build_brief_prompt`.)

- [ ] **Step 8: Run** `manage.py test ai -v 1` → ALL PASS (existing + new).

- [ ] **Step 9: Commit** — `git add backend/ai && git commit -m "feat(ai): ground brief prompt with age/sex, normalize model output"`

---

### Task 2: F2 — latest-brief + prefetch endpoints (backend)

**Files:**
- Modify: `backend/ai/briefs.py`, `backend/ai/views.py`, `backend/ai/urls.py`
- Test: `backend/ai/tests/test_ai.py`

- [ ] **Step 1: Write the failing tests** — append to `test_ai.py`:

```python
class ImmediateThread:
    """Stand-in for threading.Thread that runs the target synchronously."""
    def __init__(self, target=None, args=(), kwargs=None, daemon=None):
        self._target, self._args, self._kwargs = target, args, kwargs or {}

    def start(self):
        self._target(*self._args, **self._kwargs)


class PrefetchBriefTest(AIBase):
    def setUp(self):
        super().setUp()
        from django.utils import timezone
        from scheduling.models import Appointment
        self.appt = Appointment.objects.create(
            child=self.child, psychologist=self.psy,
            start=timezone.now().replace(hour=23, minute=0),
            end=timezone.now().replace(hour=23, minute=30),
            status=Appointment.SCHEDULED)

    def test_latest_404_when_none(self):
        self._auth("p@racco1.gov.ph")
        resp = self.client.get(f"/api/ai/brief/child/{self.child.id}/latest/")
        self.assertEqual(resp.status_code, 404)

    def test_latest_returns_todays_brief(self):
        AIJob.objects.create(job_type="brief", input_ref=f"child:{self.child.id}",
                             output_text="Cached brief.", ok=True, created_by=self.psy)
        self._auth("p@racco1.gov.ph")
        resp = self.client.get(f"/api/ai/brief/child/{self.child.id}/latest/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["draft"], "Cached brief.")
        self.assertIn("generated_at", resp.data)

    def test_latest_scoped_to_assigned(self):
        other = User.objects.create_user(
            email="o@racco1.gov.ph", username="o", password="pass1234", role=self.psy_role)
        AIJob.objects.create(job_type="brief", input_ref=f"child:{self.child.id}",
                             output_text="Cached.", ok=True, created_by=self.psy)
        self._auth("o@racco1.gov.ph")
        resp = self.client.get(f"/api/ai/brief/child/{self.child.id}/latest/")
        self.assertEqual(resp.status_code, 404)

    def test_prefetch_disabled_503(self):
        self._auth("p@racco1.gov.ph")
        self.assertEqual(self.client.post("/api/ai/prefetch-briefs/").status_code, 503)

    @patch("ai.briefs.threading.Thread", ImmediateThread)
    @patch("ai.services.get_ai_client", return_value=FakeClient("Prefetched."))
    def test_prefetch_generates_for_todays_appointments(self, _mock):
        self._enable()
        self._auth("p@racco1.gov.ph")
        resp = self.client.post("/api/ai/prefetch-briefs/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["queued"], [self.child.id])
        job = AIJob.objects.get(job_type="brief")
        self.assertEqual(job.output_text, "Prefetched.")

    @patch("ai.briefs.threading.Thread", ImmediateThread)
    @patch("ai.services.get_ai_client", return_value=FakeClient())
    def test_prefetch_skips_when_today_brief_exists(self, _mock):
        self._enable()
        AIJob.objects.create(job_type="brief", input_ref=f"child:{self.child.id}",
                             output_text="Existing.", ok=True, created_by=self.psy)
        self._auth("p@racco1.gov.ph")
        resp = self.client.post("/api/ai/prefetch-briefs/")
        self.assertEqual(resp.data["queued"], [])
        self.assertEqual(resp.data["skipped"], [self.child.id])
        self.assertEqual(AIJob.objects.filter(job_type="brief").count(), 1)

    @patch("ai.briefs.threading.Thread", ImmediateThread)
    @patch("ai.services.get_ai_client", return_value=FakeClient())
    def test_prefetch_scoped_for_psychologist(self, _mock):
        from django.utils import timezone
        from scheduling.models import Appointment
        self._enable()
        other_psy = User.objects.create_user(
            email="o@racco1.gov.ph", username="o", password="pass1234", role=self.psy_role)
        other_child = Child.objects.create(fullname="Ben Cruz", assigned_psychologist=other_psy)
        Appointment.objects.create(
            child=other_child, psychologist=other_psy,
            start=timezone.now().replace(hour=23, minute=0),
            end=timezone.now().replace(hour=23, minute=30),
            status=Appointment.SCHEDULED)
        self._auth("p@racco1.gov.ph")
        resp = self.client.post("/api/ai/prefetch-briefs/")
        self.assertEqual(resp.data["queued"], [self.child.id])
```

**Note:** check `scheduling/models.py` for `Appointment`'s exact required fields (e.g., `end`, `purpose`, capacity fields) and adjust the two `Appointment.objects.create(...)` calls so they satisfy model constraints — keep `child`, `psychologist`, `start` today, `status=Appointment.SCHEDULED` as the essentials. If `Appointment` has no `psychologist` field, drop it; scoping goes through `child__assigned_psychologist`.

- [ ] **Step 2: Run to verify failure** — `manage.py test ai.tests.test_ai.PrefetchBriefTest -v 1` → FAIL (404s on missing routes).

- [ ] **Step 3: Extend `backend/ai/briefs.py`** — add at top: `import threading`, `from django.db import connection`, `from django.utils import timezone`, `from ai.models import AIJob`, `from ai.services import AIUnavailable, run_job`. Then append:

```python
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
```

- [ ] **Step 4: Add the views** in `views.py` (imports: `from django.utils import timezone`, `from scheduling.models import Appointment`, `from ai.briefs import build_brief_prompt, latest_brief_job, prefetch_briefs`):

```python
class LatestBriefView(APIView):
    """F2 — return today's cached brief instantly (404 when none)."""
    permission_classes = [CanViewResults]

    def get(self, request, child_id):
        try:
            child = Child.objects.get(pk=child_id)
        except Child.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if _role(request) == Role.PSYCHOLOGIST and \
                child.assigned_psychologist_id != request.user.id:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        job = latest_brief_job(child.id)
        if not job:
            return Response({"detail": "No brief generated today."},
                            status=status.HTTP_404_NOT_FOUND)
        return Response({"draft": job.output_text, "job_id": job.id,
                         "generated_at": job.created_at, "disclaimer": DISCLAIMER})


class PrefetchBriefsView(APIView):
    """F2 — queue background brief generation for today's scheduled appointments."""
    permission_classes = [CanViewResults]

    def post(self, request):
        if not feature_enabled("brief"):
            return _gate("brief")
        appts = Appointment.objects.filter(
            status=Appointment.SCHEDULED,
            start__date=timezone.localdate()).select_related("child")
        if _role(request) == Role.PSYCHOLOGIST:
            appts = appts.filter(child__assigned_psychologist=request.user)
        children = list({a.child_id: a.child for a in appts}.values())
        queued, skipped = prefetch_briefs(children, request.user)
        return Response({"queued": queued, "skipped": skipped})
```

- [ ] **Step 5: Routes** in `urls.py` (order doesn't matter — `path()` matches full strings):

```python
    path("ai/brief/child/<int:child_id>/latest/", LatestBriefView.as_view(), name="ai-brief-latest"),
    path("ai/prefetch-briefs/", PrefetchBriefsView.as_view(), name="ai-prefetch-briefs"),
```

- [ ] **Step 6: Run** `manage.py test ai -v 1` → ALL PASS.
- [ ] **Step 7: Commit** — `git commit -m "feat(ai): pre-generated briefs — latest-brief cache endpoint + prefetch for today's appointments"`

---

### Task 3: F3 — case-study AI summary (backend)

**Files:**
- Modify: `backend/ai/models.py` (TYPE_CHOICES), `backend/ai/prompts.py`, `backend/ai/views.py`, `backend/ai/urls.py`
- Create: migration `0002` (choices change)
- Test: `backend/ai/tests/test_ai.py`

- [ ] **Step 1: Write the failing tests:**

```python
class CaseStudySummaryTest(AIBase):
    def setUp(self):
        super().setUp()
        from clinical.models import CaseStudy
        self.staff = User.objects.create_user(
            email="s@racco1.gov.ph", username="s", password="pass1234", role=self.staff_role)
        self.cs = CaseStudy.objects.create(
            child=self.child, uploaded_by=self.staff, file="case_studies/x.pdf",
            extracted_text="Family background: the child lives with a foster family.")

    @patch("ai.services.get_ai_client", return_value=FakeClient("1. Background…"))
    def test_draft_saved_unconfirmed(self, _mock):
        self._enable()
        self._auth("p@racco1.gov.ph")
        resp = self.client.post(f"/api/ai/summarize-case-study/{self.cs.id}/")
        self.assertEqual(resp.status_code, 200)
        self.cs.refresh_from_db()
        self.assertEqual(self.cs.ai_summary, "1. Background…")
        self.assertFalse(self.cs.ai_summary_confirmed)
        job = AIJob.objects.get()
        self.assertEqual(job.job_type, "case_study")
        self.assertEqual(job.input_ref, f"casestudy:{self.cs.id}")

    @patch("ai.services.get_ai_client", return_value=FakeClient())
    def test_scoped_to_assigned_psychologist(self, _mock):
        self._enable()
        other = User.objects.create_user(
            email="o@racco1.gov.ph", username="o", password="pass1234", role=self.psy_role)
        self._auth("o@racco1.gov.ph")
        resp = self.client.post(f"/api/ai/summarize-case-study/{self.cs.id}/")
        self.assertEqual(resp.status_code, 404)

    def test_no_text_400(self):
        self._enable()
        self.cs.extracted_text = ""
        self.cs.save()
        with patch("ai.services.get_ai_client", return_value=FakeClient()):
            self._auth("p@racco1.gov.ph")
            resp = self.client.post(f"/api/ai/summarize-case-study/{self.cs.id}/")
        self.assertEqual(resp.status_code, 400)

    @patch("ai.services.get_ai_client", return_value=FakeClient())
    def test_confirm_flow(self, _mock):
        self._enable()
        self._auth("p@racco1.gov.ph")
        self.client.post(f"/api/ai/summarize-case-study/{self.cs.id}/")
        resp = self.client.post(f"/api/ai/confirm-case-study-summary/{self.cs.id}/",
                                {"text": "Edited case summary."}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.cs.refresh_from_db()
        self.assertTrue(self.cs.ai_summary_confirmed)
        self.assertEqual(self.cs.ai_summary, "Edited case summary.")

    @patch("ai.services.get_ai_client", return_value=FakeClient())
    def test_staff_cannot_confirm(self, _mock):
        self._enable()
        self._auth("s@racco1.gov.ph")
        resp = self.client.post(f"/api/ai/confirm-case-study-summary/{self.cs.id}/",
                                {"text": "x"}, format="json")
        self.assertEqual(resp.status_code, 403)
```

(Adjust `CaseStudy.objects.create` kwargs to the real model if `uploaded_by`/`file` differ — check `clinical/models.py:206`.)

- [ ] **Step 2: Run to verify failure** — 404 (no routes).

- [ ] **Step 3: Model + migration** — in `AIJob.TYPE_CHOICES` add `("case_study", "Case Study Summary")`, then `venv\Scripts\python.exe manage.py makemigrations ai` (→ `0002_alter_aijob_job_type.py`) and `manage.py migrate`.

- [ ] **Step 4: Prompt** — append to `prompts.py`:

```python
CASE_STUDY = """From the social worker's case study text below, draft:
1. Background and family/social context (3-5 bullet points)
2. Presenting concerns (2-4 bullet points)
3. Recommendations noted by the author (1-3 bullet points)

Only use information present in the text.

CASE STUDY TEXT:
{text}
"""
```

- [ ] **Step 5: Views** — add to `views.py` (import `CaseStudy` from `clinical.models`):

```python
class CaseStudySummaryDraftView(APIView):
    """F3 — draft structured fields from the social worker's case study."""
    permission_classes = [CanViewResults]

    def post(self, request, case_study_id):
        if not feature_enabled("doc_intelligence"):
            return _gate("doc_intelligence")
        try:
            cs = CaseStudy.objects.select_related("child").get(pk=case_study_id)
        except CaseStudy.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if _role(request) == Role.PSYCHOLOGIST and \
                cs.child.assigned_psychologist_id != request.user.id:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if not cs.extracted_text:
            return Response(
                {"detail": "No extractable text in this case study (scanned or Word file)."},
                status=status.HTTP_400_BAD_REQUEST)
        prompt = prompts.CASE_STUDY.format(text=cs.extracted_text[:12000])
        try:
            text, job = run_job("case_study", f"casestudy:{cs.id}", prompt,
                                prompts.SYSTEM, request.user)
        except AIUnavailable:
            return _gate("doc_intelligence")
        cs.ai_summary = text
        cs.ai_summary_confirmed = False
        cs.save(update_fields=["ai_summary", "ai_summary_confirmed"])
        return Response({"draft": text, "job_id": job.id, "disclaimer": DISCLAIMER})


class ConfirmCaseStudySummaryView(APIView):
    """Human-in-the-loop confirm/edit of the case-study draft."""
    permission_classes = [CanViewResults]

    def post(self, request, case_study_id):
        try:
            cs = CaseStudy.objects.select_related("child").get(pk=case_study_id)
        except CaseStudy.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        role = _role(request)
        can = role == Role.ADMINISTRATOR or (
            role == Role.PSYCHOLOGIST and cs.child.assigned_psychologist_id == request.user.id)
        if not can:
            return Response(
                {"detail": "Only the assigned psychologist can confirm the summary."},
                status=status.HTTP_403_FORBIDDEN)
        text = (request.data.get("text") or "").strip()
        if not text:
            return Response({"text": "Provide the confirmed summary text."},
                            status=status.HTTP_400_BAD_REQUEST)
        cs.ai_summary = text
        cs.ai_summary_confirmed = True
        cs.save(update_fields=["ai_summary", "ai_summary_confirmed"])
        AIJob.objects.filter(input_ref=f"casestudy:{cs.id}",
                             job_type="case_study").update(accepted=True)
        return Response({"ai_summary": cs.ai_summary, "confirmed": True})
```

- [ ] **Step 6: Routes:**

```python
    path("ai/summarize-case-study/<int:case_study_id>/", CaseStudySummaryDraftView.as_view(), name="ai-summarize-case-study"),
    path("ai/confirm-case-study-summary/<int:case_study_id>/", ConfirmCaseStudySummaryView.as_view(), name="ai-confirm-case-study-summary"),
```

- [ ] **Step 7: Run** `manage.py test ai -v 1` → ALL PASS.
- [ ] **Step 8: Commit** — `git commit -m "feat(ai): case-study document intelligence with confirm flow"`

---

### Task 4: F4 — outcome tracking, feedback + metrics endpoints (backend)

**Files:**
- Modify: `backend/ai/models.py`, `backend/ai/views.py`, `backend/ai/urls.py`
- Create: migration `0003` (outcome field)
- Test: `backend/ai/tests/test_ai.py`

- [ ] **Step 1: Write the failing tests:**

```python
class FeedbackAndMetricsTest(AIBase):
    def _job(self, **kw):
        base = dict(job_type="brief", input_ref=f"child:{self.child.id}",
                    output_text="Draft.", ok=True, created_by=self.psy, latency_ms=100)
        base.update(kw)
        return AIJob.objects.create(**base)

    def test_feedback_sets_outcome(self):
        job = self._job()
        self._auth("p@racco1.gov.ph")
        resp = self.client.post(f"/api/ai/jobs/{job.id}/feedback/",
                                {"outcome": "accepted"}, format="json")
        self.assertEqual(resp.status_code, 200)
        job.refresh_from_db()
        self.assertEqual(job.outcome, "accepted")
        self.assertTrue(job.accepted)

    def test_feedback_discarded(self):
        job = self._job()
        self._auth("p@racco1.gov.ph")
        self.client.post(f"/api/ai/jobs/{job.id}/feedback/",
                         {"outcome": "discarded"}, format="json")
        job.refresh_from_db()
        self.assertEqual(job.outcome, "discarded")
        self.assertFalse(job.accepted)

    def test_feedback_invalid_outcome_400(self):
        job = self._job()
        self._auth("p@racco1.gov.ph")
        resp = self.client.post(f"/api/ai/jobs/{job.id}/feedback/",
                                {"outcome": "loved-it"}, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_feedback_creator_only(self):
        job = self._job()
        other = User.objects.create_user(
            email="o@racco1.gov.ph", username="o", password="pass1234", role=self.psy_role)
        self._auth("o@racco1.gov.ph")
        resp = self.client.post(f"/api/ai/jobs/{job.id}/feedback/",
                                {"outcome": "accepted"}, format="json")
        self.assertEqual(resp.status_code, 404)

    def test_metrics_admin_only(self):
        self._auth("p@racco1.gov.ph")
        self.assertEqual(self.client.get("/api/ai/metrics/").status_code, 403)

    def test_metrics_aggregates(self):
        self._job(outcome="accepted", latency_ms=100)
        self._job(outcome="edited", latency_ms=300)
        self._job(ok=False, error="boom", latency_ms=None)
        self._auth("a@racco1.gov.ph")
        resp = self.client.get("/api/ai/metrics/")
        self.assertEqual(resp.status_code, 200)
        brief = resp.data["brief"]["all_time"]
        self.assertEqual(brief["runs"], 3)
        self.assertEqual(brief["ok"], 2)
        self.assertEqual(brief["errors"], 1)
        self.assertEqual(brief["avg_latency_ms"], 200)
        self.assertEqual(brief["outcomes"]["accepted"], 1)
        self.assertEqual(brief["outcomes"]["edited"], 1)


class ConfirmOutcomeTest(AIBase):
    def setUp(self):
        super().setUp()
        self.report = PsychologicalReport.objects.create(
            child=self.child, author=self.psy, file="reports/x.pdf",
            extracted_text="The child shows improvement.")

    @patch("ai.services.get_ai_client", return_value=FakeClient("Draft summary."))
    def test_confirm_unchanged_marks_accepted(self, _mock):
        self._enable()
        self._auth("p@racco1.gov.ph")
        self.client.post(f"/api/ai/summarize-report/{self.report.id}/")
        self.client.post(f"/api/ai/confirm-summary/{self.report.id}/",
                         {"text": "Draft summary."}, format="json")
        job = AIJob.objects.get(job_type="doc_intelligence")
        self.assertEqual(job.outcome, "accepted")

    @patch("ai.services.get_ai_client", return_value=FakeClient("Draft summary."))
    def test_confirm_changed_marks_edited(self, _mock):
        self._enable()
        self._auth("p@racco1.gov.ph")
        self.client.post(f"/api/ai/summarize-report/{self.report.id}/")
        self.client.post(f"/api/ai/confirm-summary/{self.report.id}/",
                         {"text": "Heavily edited."}, format="json")
        job = AIJob.objects.get(job_type="doc_intelligence")
        self.assertEqual(job.outcome, "edited")
```

- [ ] **Step 2: Run to verify failure.**

- [ ] **Step 3: Model** — add to `AIJob` (below the TYPE_CHOICES block):

```python
    PENDING, ACCEPTED, EDITED, DISCARDED = "pending", "accepted", "edited", "discarded"
    OUTCOME_CHOICES = [(PENDING, "Pending"), (ACCEPTED, "Accepted as-is"),
                       (EDITED, "Edited then used"), (DISCARDED, "Discarded")]
```

and the field (next to `accepted`):

```python
    outcome = models.CharField(max_length=10, choices=OUTCOME_CHOICES, default=PENDING)
```

Run `manage.py makemigrations ai && manage.py migrate` (→ `0003_aijob_outcome.py`).

- [ ] **Step 4: Views** — add to `views.py` (imports: `from datetime import timedelta`, `from django.db.models import Avg, Count, Q`):

```python
def _set_confirm_outcome(job_type, input_ref, confirmed_text):
    """After a human confirm, record whether the draft was used verbatim or edited."""
    job = AIJob.objects.filter(job_type=job_type, input_ref=input_ref,
                               ok=True).order_by("-created_at").first()
    if not job:
        return
    same = " ".join(confirmed_text.split()) == " ".join((job.output_text or "").split())
    job.outcome = AIJob.ACCEPTED if same else AIJob.EDITED
    job.accepted = True
    job.save(update_fields=["outcome", "accepted"])


class AIJobFeedbackView(APIView):
    """F4 — record the human verdict on a draft (accepted / edited / discarded)."""
    permission_classes = [IsAuthenticated]

    def post(self, request, job_id):
        try:
            job = AIJob.objects.get(pk=job_id)
        except AIJob.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if _role(request) != Role.ADMINISTRATOR and job.created_by_id != request.user.id:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        outcome = request.data.get("outcome")
        if outcome not in (AIJob.ACCEPTED, AIJob.EDITED, AIJob.DISCARDED):
            return Response({"outcome": "Must be accepted, edited, or discarded."},
                            status=status.HTTP_400_BAD_REQUEST)
        job.outcome = outcome
        job.accepted = outcome != AIJob.DISCARDED
        job.save(update_fields=["outcome", "accepted"])
        return Response({"id": job.id, "outcome": job.outcome})


class AIMetricsView(APIView):
    """F4 — per-feature usage aggregates for the admin settings panel."""
    permission_classes = [IsAdministrator]

    def get(self, request):
        since = timezone.now() - timedelta(days=30)

        def bucket(qs):
            agg = qs.aggregate(runs=Count("id"), ok=Count("id", filter=Q(ok=True)),
                               errors=Count("id", filter=Q(ok=False)),
                               avg_latency_ms=Avg("latency_ms"))
            agg["avg_latency_ms"] = (round(agg["avg_latency_ms"])
                                     if agg["avg_latency_ms"] is not None else None)
            counts = dict(qs.values_list("outcome").annotate(n=Count("id")))
            agg["outcomes"] = {k: counts.get(k, 0)
                               for k in ("pending", "accepted", "edited", "discarded")}
            return agg

        data = {}
        for jt, label in AIJob.TYPE_CHOICES:
            qs = AIJob.objects.filter(job_type=jt)
            data[jt] = {"label": label, "all_time": bucket(qs),
                        "last_30_days": bucket(qs.filter(created_at__gte=since))}
        return Response(data)
```

- [ ] **Step 5: Wire confirm views** — in `ConfirmReportSummaryView.post`, replace the `AIJob.objects.filter(...).update(accepted=True)` line with:

```python
        _set_confirm_outcome("doc_intelligence", f"report:{report.id}", text)
```

In `ConfirmCaseStudySummaryView.post`, replace its `AIJob.objects.filter(...).update(accepted=True)` line with:

```python
        _set_confirm_outcome("case_study", f"casestudy:{cs.id}", text)
```

- [ ] **Step 6: Routes:**

```python
    path("ai/jobs/<int:job_id>/feedback/", AIJobFeedbackView.as_view(), name="ai-job-feedback"),
    path("ai/metrics/", AIMetricsView.as_view(), name="ai-metrics"),
```

- [ ] **Step 7: Run** `manage.py test ai -v 1`, then the full `manage.py test` → ALL PASS (existing `test_confirm_flow` asserts `accepted=True` — `_set_confirm_outcome` preserves that).
- [ ] **Step 8: Commit** — `git commit -m "feat(ai): draft outcome tracking, feedback endpoint, admin usage metrics"`

---

### Task 5: Frontend — child chart: instant brief, thumbs, polish outcome, case-study summary

**Files:**
- Modify: `frontend/src/pages/ChildProgressReport.jsx`

No frontend test harness — verify with `npm run build` + live browser checks (Task 8).

- [ ] **Step 1: State + load.** Next to the existing `aiModal` state add:

```jsx
  const [latestBrief, setLatestBrief] = useState(null); // { draft, job_id, generated_at }
  const [polishJob, setPolishJob] = useState(null);     // { id, draft } — last polish result
```

In the page's initial data-loading effect (where the other `api.get` calls fire), add:

```jsx
    api.get(`/ai/brief/child/${id}/latest/`).then((r) => setLatestBrief(r.data)).catch(() => {});
```

- [ ] **Step 2: Feedback helper** (place near `aiUnavailable`):

```jsx
  const sendAiFeedback = (jobId, outcome) => {
    if (!jobId) return;
    api.post(`/ai/jobs/${jobId}/feedback/`, { outcome }).catch(() => {});
  };
```

- [ ] **Step 3: Instant brief.** Replace the `aiBrief` handler with:

```jsx
  const openBrief = (data, regenerated) => {
    setAiModal({
      title: 'AI pre-session brief (draft)', draft: data.draft, disclaimer: data.disclaimer,
      jobId: data.job_id, feedback: true,
      generatedAt: regenerated ? null : data.generated_at,
      onRegenerate: regenerateBrief,
    });
  };

  const regenerateBrief = async () => {
    setAiBusy(true);
    try {
      const { data: d } = await api.post(`/ai/brief/child/${id}/`);
      setLatestBrief({ draft: d.draft, job_id: d.job_id, generated_at: new Date().toISOString() });
      openBrief(d, true);
    } catch (err) { aiUnavailable(err); } finally { setAiBusy(false); }
  };

  const aiBrief = () => {
    if (latestBrief) openBrief({ ...latestBrief, disclaimer: DISCLAIMER_TEXT });
    else regenerateBrief();
  };
```

Add near the top of the file (module scope):

```jsx
const DISCLAIMER_TEXT = 'AI-drafted decision support, not a diagnosis. The licensed psychologist reviews, edits, and approves all content.';
```

- [ ] **Step 4: Polish outcome.** In `aiPolish`, after `setRemarkText(d.draft);` add:

```jsx
      setPolishJob({ id: d.job_id, draft: d.draft });
```

In `addRemark`, capture the text before clearing and report the outcome after a successful save — replace the body with:

```jsx
  const addRemark = async () => {
    if (!remarkText.trim()) return;
    const saved = remarkText.trim();
    try {
      await api.post('/remarks/', { child: Number(id), text: saved });
      if (polishJob) {
        sendAiFeedback(polishJob.id, saved === polishJob.draft.trim() ? 'accepted' : 'edited');
        setPolishJob(null);
      }
      setRemarkText(''); load(); toast.success('Remark added');
    } catch (err) { toast.error(err.response?.data?.detail || 'Could not add the remark.'); }
  };
```

Also clear a stale `polishJob` when the user wipes the box: in the remark textarea's `onChange`, if the new value is empty, `setPolishJob(null)` (only if that's a one-line addition; otherwise skip — a stale diff still yields the correct `edited` verdict).

- [ ] **Step 5: Case-study summarize.** Add a handler mirroring `aiSummarize`:

```jsx
  const aiSummarizeCaseStudy = (f) => {
    setAiBusy(true);
    api.post(`/ai/summarize-case-study/${f.id}/`)
      .then(({ data: d }) => setAiModal({
        title: `AI summary draft — ${f.original_filename}`,
        draft: d.draft, disclaimer: d.disclaimer, editable: true,
        onConfirm: async (text) => {
          try {
            await api.post(`/ai/confirm-case-study-summary/${f.id}/`, { text });
            toast.success('Summary confirmed');
            setAiModal(null); load();
          } catch (err) { aiUnavailable(err); }
        },
      }))
      .catch(aiUnavailable).finally(() => setAiBusy(false));
  };
```

In the case-study file list (the block whose Download button calls `/case-studies/${f.id}/download/`, around line 275), add next to Download — visible when `canWrite` and `f.has_text`:

```jsx
  {canWrite && f.has_text && (
    <Button variant="ghost" onClick={() => aiSummarizeCaseStudy(f)} disabled={aiBusy}
            iconLeft={<Icon name="sparkles" size={15} />}>AI summary</Button>
  )}
```

And below the case-study row, render the summary exactly like the report files already do (copy the `f.ai_summary && (...)` block pattern from line ~326, same "confirmed / draft (unconfirmed)" label).

- [ ] **Step 6: Modal upgrades.** In the AI draft modal JSX (around line 469):
  - Under the title, when `aiModal.generatedAt` is set, show a stamp + regenerate:

```jsx
  {aiModal.generatedAt && (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 12, color: 'var(--text-muted)' }}>
      <span>Drafted {new Date(aiModal.generatedAt).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })} — ready before you clicked.</span>
      <Button variant="ghost" onClick={() => { setAiModal(null); aiModal.onRegenerate?.(); }} iconLeft={<Icon name="refresh-cw" size={14} />}>Regenerate</Button>
    </div>
  )}
```

  - In the footer, when `aiModal.feedback && !aiModal.feedbackSent`, add thumbs:

```jsx
  {aiModal.feedback && !aiModal.feedbackSent && (
    <>
      <Button variant="ghost" onClick={() => { sendAiFeedback(aiModal.jobId, 'accepted'); setAiModal({ ...aiModal, feedbackSent: true }); }} iconLeft={<Icon name="thumbs-up" size={15} />}>Useful</Button>
      <Button variant="ghost" onClick={() => { sendAiFeedback(aiModal.jobId, 'discarded'); setAiModal({ ...aiModal, feedbackSent: true }); }} iconLeft={<Icon name="thumbs-down" size={15} />}>Not useful</Button>
    </>
  )}
```

  (If the `Icon` set lacks `thumbs-up`/`thumbs-down`/`refresh-cw`, check `frontend/src/ui` for the icon registry and use the closest existing names, e.g. `check`/`x`; do not add a new icon library.)

- [ ] **Step 7:** `npm run build` from `frontend\` → must succeed with no errors.
- [ ] **Step 8: Commit** — `git commit -m "feat(ai): chart UX — instant cached brief, draft feedback, case-study AI summary"`

---

### Task 6: Frontend — Schedule: prefetch + pre-session brief button

**Files:**
- Modify: `frontend/src/pages/Schedule.jsx`

- [ ] **Step 1: Prefetch on load.** After the appointments are first loaded (the `useEffect` that calls `api.get('/appointments/')`), fire once, silently:

```jsx
  useEffect(() => { api.post('/ai/prefetch-briefs/').catch(() => {}); }, []);
```

- [ ] **Step 2: Brief state + handler** (component scope):

```jsx
  const [brief, setBrief] = useState(null);      // { draft, generated_at, job_id, childName }
  const [briefBusy, setBriefBusy] = useState(false);

  const showBrief = async (a) => {
    setBriefBusy(true);
    try {
      let d;
      try {
        ({ data: d } = await api.get(`/ai/brief/child/${a.child}/latest/`));
      } catch {
        ({ data: d } = await api.post(`/ai/brief/child/${a.child}/`));
        d.generated_at = new Date().toISOString();
      }
      setBrief({ ...d, childName: a.child_name });
    } catch (err) {
      toast.error(err.response?.status === 503
        ? 'AI assistance is switched off or unreachable.'
        : 'Could not load the brief.');
    } finally { setBriefBusy(false); }
  };
```

(Check the appointment object's field names in this file — the child id may be `a.child` or `a.child_id`, and the display name `a.child_name`; match what the detail panel already uses.)

- [ ] **Step 3: Button in the appointment detail panel** (the `{/* Appointment detail */}` block, ~line 312). In its actions row, for an appointment that is `scheduled` and starts today, add:

```jsx
  <Button variant="secondary" onClick={() => showBrief(detail)} disabled={briefBusy}
          iconLeft={<Icon name={briefBusy ? 'loader' : 'sparkles'} size={16} />}>
    {briefBusy ? 'Working…' : 'Pre-session brief'}
  </Button>
```

(`detail` = whatever local variable holds the selected appointment in that panel; "starts today" test: `new Date(detail.start).toDateString() === new Date().toDateString()`.)

- [ ] **Step 4: Brief modal.** Reuse the page's existing modal pattern (the booking modal markup) for a read-only brief modal at the end of the JSX:

```jsx
  {brief && (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(15,23,42,.45)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 60 }} onClick={() => setBrief(null)}>
      <div onClick={(e) => e.stopPropagation()} style={{ background: 'var(--surface)', borderRadius: 'var(--radius-lg)', width: 'min(560px, 92vw)', maxHeight: '84vh', overflow: 'auto', boxShadow: 'var(--shadow-lg)' }}>
        <div style={{ padding: '18px 20px', borderBottom: '1px solid var(--border)', background: 'var(--ink-50)', fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 17, color: 'var(--text-strong)' }}>
          Pre-session brief — {brief.childName}
        </div>
        <div style={{ padding: 20 }}>
          {brief.generated_at && <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 8 }}>Drafted {new Date(brief.generated_at).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}</div>}
          <p style={{ fontSize: 13.5, color: 'var(--text-body)', lineHeight: 1.65, margin: 0, whiteSpace: 'pre-wrap' }}>{brief.draft}</p>
          <p style={{ fontSize: 11.5, color: 'var(--text-muted)', marginTop: 12 }}>AI-drafted decision support, not a diagnosis. The licensed psychologist reviews, edits, and approves all content.</p>
        </div>
        <div style={{ padding: '14px 20px', borderTop: '1px solid var(--border)', display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          <Button variant="ghost" onClick={() => { api.post(`/ai/jobs/${brief.job_id}/feedback/`, { outcome: 'accepted' }).catch(() => {}); setBrief(null); }} iconLeft={<Icon name="thumbs-up" size={15} />}>Useful</Button>
          <Button variant="ghost" onClick={() => { api.post(`/ai/jobs/${brief.job_id}/feedback/`, { outcome: 'discarded' }).catch(() => {}); setBrief(null); }} iconLeft={<Icon name="thumbs-down" size={15} />}>Not useful</Button>
          <Button variant="secondary" onClick={() => setBrief(null)}>Close</Button>
        </div>
      </div>
    </div>
  )}
```

(Match the page's actual modal styling if it differs — copy the booking-modal wrapper styles verbatim rather than inventing new ones.)

- [ ] **Step 5:** `npm run build` → succeeds.
- [ ] **Step 6: Commit** — `git commit -m "feat(ai): schedule — prefetch today's briefs, instant brief from appointment detail"`

---

### Task 7: Frontend — AgencySummary thumbs + Settings usage panel

**Files:**
- Modify: `frontend/src/pages/AgencySummary.jsx`, `frontend/src/pages/Settings.jsx`

- [ ] **Step 1: AgencySummary.** Track the job and feedback state — change `narrative` state and `generateNarrative`:

```jsx
  const [narrative, setNarrative] = useState(null); // { text, jobId, feedbackSent }
```

In `generateNarrative`, replace `setNarrative(resp.draft)` with:

```jsx
      setNarrative({ text: resp.draft, jobId: resp.job_id, feedbackSent: false });
```

Find where the narrative renders (search `narrative` in the JSX; it prints the string) and update it to `narrative.text`, guarded by `narrative && …`, adding under it:

```jsx
  {narrative && !narrative.feedbackSent && (
    <div style={{ display: 'flex', gap: 8, marginTop: 8 }} className="racco-no-print">
      <Button variant="ghost" onClick={() => { api.post(`/ai/jobs/${narrative.jobId}/feedback/`, { outcome: 'accepted' }).catch(() => {}); setNarrative({ ...narrative, feedbackSent: true }); }} iconLeft={<Icon name="thumbs-up" size={15} />}>Useful</Button>
      <Button variant="ghost" onClick={() => { api.post(`/ai/jobs/${narrative.jobId}/feedback/`, { outcome: 'discarded' }).catch(() => {}); setNarrative(null); }} iconLeft={<Icon name="thumbs-down" size={15} />}>Discard</Button>
    </div>
  )}
```

- [ ] **Step 2: Settings usage panel.** In `Settings.jsx`, alongside the existing `api.get('/ai/settings/')`, fetch metrics (admins only reach this page's AI card):

```jsx
  const [metrics, setMetrics] = useState(null);
  useEffect(() => { api.get('/ai/metrics/').then((r) => setMetrics(r.data)).catch(() => {}); }, []);
```

Below the feature-flag switches inside the "Local AI Layer (Ollama)" card, render:

```jsx
  {metrics && (
    <div style={{ marginTop: 18 }}>
      <div style={{ fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 14, color: 'var(--text-strong)', marginBottom: 8 }}>Usage (last 30 days)</div>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12.5 }}>
          <thead>
            <tr style={{ textAlign: 'left', color: 'var(--text-muted)' }}>
              {['Feature', 'Runs', 'Success', 'Avg latency', 'Accepted', 'Edited', 'Discarded'].map((h) => (
                <th key={h} style={{ padding: '6px 8px', borderBottom: '1px solid var(--border)' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {Object.entries(metrics).map(([k, m]) => {
              const d = m.last_30_days;
              return (
                <tr key={k}>
                  <td style={{ padding: '6px 8px' }}>{m.label}</td>
                  <td style={{ padding: '6px 8px' }}>{d.runs}</td>
                  <td style={{ padding: '6px 8px' }}>{d.runs ? Math.round((d.ok / d.runs) * 100) + '%' : '—'}</td>
                  <td style={{ padding: '6px 8px' }}>{d.avg_latency_ms != null ? (d.avg_latency_ms / 1000).toFixed(1) + ' s' : '—'}</td>
                  <td style={{ padding: '6px 8px' }}>{d.outcomes.accepted}</td>
                  <td style={{ padding: '6px 8px' }}>{d.outcomes.edited}</td>
                  <td style={{ padding: '6px 8px' }}>{d.outcomes.discarded}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p style={{ fontSize: 11.5, color: 'var(--text-muted)', marginTop: 6 }}>Acceptance is recorded when a draft is confirmed, inserted, or rated by the psychologist.</p>
    </div>
  )}
```

- [ ] **Step 3: Report.jsx case-study summary display (read-only).** `frontend/src/pages/Report.jsx` lists case studies in its "Case Studies" tab (rows around line 201, Download button calls `/case-studies/${f.id}/download/`). Below each row's filename/description, when `f.ai_summary` exists, render the same summary block used in `ChildProgressReport.jsx` (~line 326): the `AI summary · confirmed / · draft (unconfirmed)` label plus the `whiteSpace: 'pre-wrap'` paragraph. Display only — no generate button here; generation lives on the child chart.

- [ ] **Step 4:** `npm run build` → succeeds.
- [ ] **Step 5: Commit** — `git commit -m "feat(ai): narrative feedback, admin AI usage panel, case-study summary on results page"`

---

### Task 8: Full verification + push

- [ ] **Step 1:** Backend full suite from `backend\`: `venv\Scripts\python.exe manage.py test` → ALL PASS (expect 184 + ~20 new).
- [ ] **Step 2:** `npm run build` in `frontend\` → clean.
- [ ] **Step 3:** Restart the `v2-backend` preview server (it runs `--noreload`), reload `v2-frontend`.
- [ ] **Step 4: Live checks** (login `psy@racco1.gov.ph` / `psy12345`, child Mika Santos id 2; Ollama must be running with all AI flags on):
  1. Child chart → "AI Pre-Session Brief" → generates (~25 s) → close → click again → **instant** (cached, stamped) → Regenerate works → thumbs record (check `AIJob.outcome` via Django shell).
  2. Type a shorthand remark → Polish → Save → the polish job's `outcome` becomes `accepted` (unedited) or `edited` (after tweaking).
  3. Upload or use an existing case study with text → "AI summary" → draft appears → confirm → label flips to "confirmed"; job outcome `accepted`/`edited`.
  4. Schedule → open a today appointment → "Pre-session brief" → instant if prefetched.
  5. Agency Summary (admin `admin@racco1.gov.ph`) → AI Narrative → thumbs.
  6. Settings (admin) → usage table shows real rows.
- [ ] **Step 5:** Commit any remaining docs (spec + plan) if not yet committed: `git add docs && git commit -m "docs: AI utilization upgrades spec + plan"`.
- [ ] **Step 6:** `git push origin main` (user-authored commits only — NO Co-Authored-By trailer).
