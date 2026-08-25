# Local AI Assistant Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore a local-Ollama drafting assistant to NACC SYS V3 as a new
`assistant` app — a spine (settings, audit, client seam, generation lock) plus
four human-in-the-loop drafting features.

**Architecture:** One Django app, `assistant`, exposing `/api/assistant/*`. Every
endpoint passes through a feature gate that 503s when the assistant is off, and
every model call goes through `run_job()`, which serialises generations behind a
lock and writes an audit row on success *and* failure. Prompts are assembled
static-prefix-first so Ollama's prefix cache stays warm. Nothing is ever
auto-applied: every output is a draft a human edits and confirms.

**Tech Stack:** Django 5.1 + DRF (no new Python dependencies — `urllib` only),
React 18 + Vite, Ollama running `qwen2.5:3b-instruct` on localhost.

**Spec:** `docs/superpowers/specs/2026-08-25-local-ai-assistant-design.md`

## Global Constraints

- **App label is `assistant`, never `ai`.** A recreated `ai.0001_initial` would be
  skipped as already-applied on any database that ran `activity/0003_drop_ai_tables.py`.
- Tables are `tbl_assistant_setting` and `tbl_assistant_job`.
- **No new entries in `backend/requirements.txt`.** Use `urllib.request`.
- **No per-request model options.** `run_job` sends `model`, `prompt`, `system`,
  `stream: false` and nothing else — no `num_ctx`, no `temperature`. Each distinct
  option set forces a ~5–6 s model reload.
- **Static prefix first.** Every prompt is `STATIC_INSTRUCTIONS + dynamic_facts`.
  Anything varying per call goes last. Violating this costs ~17 s per call.
- **Permissions never come from the model or the request body.** Scope is derived
  from `request.user`, mirroring `_ChildScopedClinicalViewSet` in `clinical/views.py:162`.
- **No scores, ratings, or classifications of children.** Deterministic code
  supplies every number; the model only writes prose.
- **No test may require a running Ollama.** Patch the client.
- Commit authorship is `Reynold <jreynoldcanedo@gmail.com>`. No Claude
  attribution, no `Co-Authored-By`, no model name in any commit message or code
  comment (`CLAUDE.md`).
- **Test expectations are "zero failures, zero errors", never a total count.**
  Do not hunt for a missing test because a total looks low.
- Test command: `cd backend && .venv/Scripts/python.exe manage.py test`.
  (CLAUDE.md documents `.venv/bin/python`; this machine's venv is Windows-layout.
  Task 20 fixes that doc.)
- Frontend gate: `npm run lint` **and** `npm run build`, then open each touched
  screen. Vite exits 0 on a page that renders nothing.

---

# Phase A — The Spine

Tasks 1–5. At the end of Phase A nothing user-visible has changed and the
assistant is off by default. That is the point: the spine ships as a no-op.

### Task 1: The `assistant` app, models, and migration

**Files:**
- Create: `backend/assistant/__init__.py`, `backend/assistant/apps.py`, `backend/assistant/models.py`, `backend/assistant/admin.py`, `backend/assistant/migrations/__init__.py`
- Create: `backend/assistant/tests/__init__.py`, `backend/assistant/tests/test_models.py`
- Modify: `backend/config/settings.py:61-77` (INSTALLED_APPS)

**Interfaces:**
- Consumes: nothing.
- Produces: `AssistantSetting.load() -> AssistantSetting` (singleton, pk=1);
  `AssistantJob` with fields `job_type, input_ref, output_text, model_used,
  latency_ms, ok, error, outcome, created_by, created_at` and constants
  `AssistantJob.PENDING/ACCEPTED/EDITED/DISCARDED`.

- [ ] **Step 1: Write the failing test**

Create `backend/assistant/tests/test_models.py`:

```python
from django.test import TestCase

from assistant.models import AssistantSetting, AssistantJob


class AssistantSettingTest(TestCase):
    def test_load_creates_singleton_with_safe_defaults(self):
        cfg = AssistantSetting.load()
        self.assertEqual(cfg.pk, 1)
        # Off by default: installing the app must change nothing.
        self.assertFalse(cfg.enabled)
        self.assertEqual(cfg.model_name, "qwen2.5:3b-instruct")
        self.assertEqual(cfg.ollama_url, "http://localhost:11434")

    def test_load_is_idempotent(self):
        AssistantSetting.load()
        AssistantSetting.load()
        self.assertEqual(AssistantSetting.objects.count(), 1)

    def test_save_always_pins_pk_to_one(self):
        cfg = AssistantSetting(pk=99, enabled=True)
        cfg.save()
        self.assertEqual(cfg.pk, 1)
        self.assertEqual(AssistantSetting.objects.count(), 1)


class AssistantJobTest(TestCase):
    def test_job_defaults_to_pending_outcome(self):
        job = AssistantJob.objects.create(job_type="remark_polish", input_ref="child:1")
        self.assertEqual(job.outcome, AssistantJob.PENDING)
        self.assertTrue(job.ok)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python.exe manage.py test assistant -v 2`
Expected: FAIL — `ModuleNotFoundError: No module named 'assistant'`

- [ ] **Step 3: Create the app package**

`backend/assistant/__init__.py` — empty.
`backend/assistant/migrations/__init__.py` — empty.
`backend/assistant/tests/__init__.py` — empty.

`backend/assistant/apps.py`:

```python
from django.apps import AppConfig


class AssistantConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "assistant"
```

- [ ] **Step 4: Write the models**

`backend/assistant/models.py`:

```python
from django.conf import settings
from django.db import models


class AssistantSetting(models.Model):
    """Singleton (pk=1): assistant feature flags plus local runtime config.

    Everything is off by default — the system is fully functional with the
    assistant switched off, and installing this app must change nothing.
    """

    enabled = models.BooleanField(default=False)  # master switch
    feature_brief = models.BooleanField(default=True)
    feature_doc_intelligence = models.BooleanField(default=True)
    feature_remark_polish = models.BooleanField(default=True)
    feature_census_narrative = models.BooleanField(default=True)

    # On-premises runtime only. There is no hosted provider: sending clinical
    # free text to an outside processor is what removed the V2 layer.
    ollama_url = models.URLField(default="http://localhost:11434")
    model_name = models.CharField(max_length=100, default="qwen2.5:3b-instruct")

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tbl_assistant_setting"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class AssistantJob(models.Model):
    """Audit row for every model call: what ran, on what, what came back, how
    long it took, and what the human did with it."""

    TYPE_CHOICES = [
        ("brief", "Pre-Session Brief"),
        ("doc_intelligence", "Document Summary"),
        ("remark_polish", "Remark Polishing"),
        ("census_narrative", "Census Narrative"),
    ]

    PENDING, ACCEPTED, EDITED, DISCARDED = "pending", "accepted", "edited", "discarded"
    OUTCOME_CHOICES = [
        (PENDING, "Pending"),
        (ACCEPTED, "Accepted as-is"),
        (EDITED, "Edited then used"),
        (DISCARDED, "Discarded"),
    ]

    job_type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    input_ref = models.CharField(max_length=150, blank=True)  # "child:12", "report:3"
    output_text = models.TextField(blank=True)
    model_used = models.CharField(max_length=100, blank=True)
    latency_ms = models.PositiveIntegerField(null=True, blank=True)
    ok = models.BooleanField(default=True)
    error = models.CharField(max_length=255, blank=True)
    outcome = models.CharField(max_length=10, choices=OUTCOME_CHOICES, default=PENDING)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="assistant_jobs")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "tbl_assistant_job"
        ordering = ["-created_at"]
```

`backend/assistant/admin.py`:

```python
from django.contrib import admin

from assistant.models import AssistantJob, AssistantSetting


@admin.register(AssistantSetting)
class AssistantSettingAdmin(admin.ModelAdmin):
    list_display = ("enabled", "model_name", "ollama_url", "updated_at")


@admin.register(AssistantJob)
class AssistantJobAdmin(admin.ModelAdmin):
    list_display = ("created_at", "job_type", "input_ref", "ok", "outcome", "latency_ms")
    list_filter = ("job_type", "ok", "outcome")
    readonly_fields = ("created_at",)
```

- [ ] **Step 5: Register the app**

In `backend/config/settings.py`, add `"assistant",` to `INSTALLED_APPS` after
`"samd",`.

- [ ] **Step 6: Make the migration**

Run: `cd backend && .venv/Scripts/python.exe manage.py makemigrations assistant`
Expected: creates `backend/assistant/migrations/0001_initial.py`

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd backend && .venv/Scripts/python.exe manage.py test assistant -v 2`
Expected: PASS — zero failures, zero errors.

- [ ] **Step 8: Commit**

```bash
git add backend/assistant backend/config/settings.py
git commit -m "Add the assistant app, off by default"
```

---

### Task 2: The client seam and `run_job`

**Files:**
- Create: `backend/assistant/services.py`
- Create: `backend/assistant/tests/test_services.py`

**Interfaces:**
- Consumes: `AssistantSetting.load()`, `AssistantJob` (Task 1).
- Produces:
  - `AIUnavailable(Exception)`
  - `NullClient` / `OllamaClient(base_url, model)` — both expose `.model` and
    `.generate(prompt, system=None) -> str`
  - `get_ai_client() -> NullClient | OllamaClient`
  - `run_job(job_type, prompt, *, system=None, input_ref="", user=None) -> (str, AssistantJob)`
  - `gate(feature_attr) -> AssistantSetting` — raises `AIUnavailable`
  - `_normalize_output(text) -> str`
  - `DISCLAIMER: str`

- [ ] **Step 1: Write the failing test**

Create `backend/assistant/tests/test_services.py`:

```python
from unittest.mock import patch

from django.test import TestCase

from assistant import services
from assistant.models import AssistantJob, AssistantSetting


class NormalizeOutputTest(TestCase):
    def test_replaces_unicode_punctuation_with_ascii(self):
        raw = "“The child’s mother” – arrived late—again. Noted."
        self.assertEqual(
            services._normalize_output(raw),
            '"The child\'s mother" - arrived late-again. Noted.')

    def test_leaves_plain_ascii_untouched(self):
        self.assertEqual(services._normalize_output("Plain note."), "Plain note.")


class GetClientTest(TestCase):
    def test_returns_null_client_when_disabled(self):
        AssistantSetting.load()  # enabled defaults to False
        self.assertIsInstance(services.get_ai_client(), services.NullClient)

    def test_returns_ollama_client_when_enabled(self):
        cfg = AssistantSetting.load()
        cfg.enabled = True
        cfg.save()
        client = services.get_ai_client()
        self.assertIsInstance(client, services.OllamaClient)
        self.assertEqual(client.model, "qwen2.5:3b-instruct")

    def test_null_client_raises(self):
        with self.assertRaises(services.AIUnavailable):
            services.NullClient().generate("anything")


class GateTest(TestCase):
    def test_raises_when_master_switch_off(self):
        AssistantSetting.load()
        with self.assertRaises(services.AIUnavailable):
            services.gate("feature_remark_polish")

    def test_raises_when_feature_flag_off(self):
        cfg = AssistantSetting.load()
        cfg.enabled = True
        cfg.feature_remark_polish = False
        cfg.save()
        with self.assertRaises(services.AIUnavailable):
            services.gate("feature_remark_polish")

    def test_returns_config_when_enabled(self):
        cfg = AssistantSetting.load()
        cfg.enabled = True
        cfg.save()
        self.assertEqual(services.gate("feature_remark_polish").pk, 1)


class RunJobTest(TestCase):
    def setUp(self):
        cfg = AssistantSetting.load()
        cfg.enabled = True
        cfg.save()

    def test_writes_audit_row_and_normalizes_on_success(self):
        with patch.object(services.OllamaClient, "generate", return_value="A ‘draft’."):
            text, job = services.run_job(
                "remark_polish", "prompt", input_ref="child:1")
        self.assertEqual(text, "A 'draft'.")
        self.assertTrue(job.ok)
        self.assertEqual(job.output_text, "A 'draft'.")
        self.assertEqual(job.input_ref, "child:1")
        self.assertEqual(job.model_used, "qwen2.5:3b-instruct")
        self.assertIsNotNone(job.latency_ms)

    def test_writes_audit_row_on_failure_and_reraises(self):
        boom = services.AIUnavailable("runtime unreachable")
        with patch.object(services.OllamaClient, "generate", side_effect=boom):
            with self.assertRaises(services.AIUnavailable):
                services.run_job("remark_polish", "prompt", input_ref="child:1")
        job = AssistantJob.objects.get()
        self.assertFalse(job.ok)
        self.assertIn("unreachable", job.error)
        self.assertEqual(job.output_text, "")

    def test_unauthenticated_user_is_stored_as_null(self):
        with patch.object(services.OllamaClient, "generate", return_value="ok"):
            _, job = services.run_job("remark_polish", "p", user=None)
        self.assertIsNone(job.created_by)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python.exe manage.py test assistant.tests.test_services -v 2`
Expected: FAIL — `ModuleNotFoundError: No module named 'assistant.services'`

- [ ] **Step 3: Write the implementation**

`backend/assistant/services.py`:

```python
"""Client seam for the on-premises model runtime.

get_ai_client() returns a live client when the master switch is on, else a
NullClient. Every caller must handle AIUnavailable — the system is fully
functional without the assistant.

There is deliberately only one provider. A hosted API would mean sending
clinical free text to a processor outside the agency's data-processing
agreements, which is what removed the V2 layer. The seam is kept so adding one
later is an addition rather than a rewrite; adding one is its own decision.
"""
import json
import logging
import threading
import time
import urllib.error
import urllib.request

from assistant.models import AssistantJob, AssistantSetting

logger = logging.getLogger(__name__)

DISCLAIMER = ("AI-drafted decision support, not a diagnosis. The licensed "
              "psychologist reviews, edits, and approves all content.")

# On 4 CPU cores, concurrent generations make every request slower rather than
# parallel, and each parallel slot multiplies the KV cache against very little
# free RAM. One generation at a time, always.
_GENERATION_LOCK = threading.Lock()


class AIUnavailable(Exception):
    """Raised whenever a draft cannot be produced. Always surfaces as a 503."""


class NullClient:
    available = False
    model = ""

    def generate(self, prompt, system=None):
        raise AIUnavailable("The assistant is switched off.")


class OllamaClient:
    available = True

    def __init__(self, base_url, model):
        self.base_url = base_url.rstrip("/")
        self.model = model

    def generate(self, prompt, system=None):
        # No num_ctx, no temperature, no options block: each distinct option set
        # forces Ollama to evict and reload the model (~5-6s).
        payload = {"model": self.model, "prompt": prompt, "stream": False}
        if system:
            payload["system"] = system
        req = urllib.request.Request(
            f"{self.base_url}/api/generate",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST")
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                data = json.loads(resp.read().decode())
        except (urllib.error.URLError, TimeoutError, OSError,
                json.JSONDecodeError) as exc:
            raise AIUnavailable(f"Local AI runtime unreachable: {exc}") from exc
        return (data.get("response") or "").strip()


def get_ai_client():
    cfg = AssistantSetting.load()
    if not cfg.enabled:
        return NullClient()
    return OllamaClient(cfg.ollama_url, cfg.model_name)


def gate(feature_attr):
    """Return the config when this feature may run, else raise AIUnavailable."""
    cfg = AssistantSetting.load()
    if not cfg.enabled:
        raise AIUnavailable("The assistant is switched off.")
    if not getattr(cfg, feature_attr):
        raise AIUnavailable("This assistant feature is switched off.")
    return cfg


# Post-processing beats prompting the model about punctuation: prompting is
# advisory, this is certain. Curly quotes render as mojibake in exported PDFs.
_PUNCTUATION = {
    "‘": "'", "’": "'",
    "“": '"', "”": '"',
    "–": "-", "—": "-",
    " ": " ",
}


def _normalize_output(text):
    for bad, good in _PUNCTUATION.items():
        text = text.replace(bad, good)
    return text


def run_job(job_type, prompt, *, system=None, input_ref="", user=None):
    """Run one generation and audit it. Returns (text, AssistantJob).

    Writes an AssistantJob row on failure as well as success, so "it stopped
    working on Tuesday" is answerable from data rather than from memory.
    """
    client = get_ai_client()
    creator = user if getattr(user, "is_authenticated", False) else None
    started = time.monotonic()
    try:
        # Only the generation is serialised; the DB writes below are not.
        with _GENERATION_LOCK:
            raw = client.generate(prompt, system=system)
    except AIUnavailable as exc:
        AssistantJob.objects.create(
            job_type=job_type, input_ref=input_ref, ok=False,
            error=str(exc)[:255], model_used=getattr(client, "model", ""),
            latency_ms=int((time.monotonic() - started) * 1000),
            created_by=creator)
        raise

    text = _normalize_output(raw)
    job = AssistantJob.objects.create(
        job_type=job_type, input_ref=input_ref, output_text=text,
        model_used=client.model, ok=True,
        latency_ms=int((time.monotonic() - started) * 1000),
        created_by=creator)
    return text, job
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/Scripts/python.exe manage.py test assistant -v 2`
Expected: PASS — zero failures, zero errors.

- [ ] **Step 5: Commit**

```bash
git add backend/assistant/services.py backend/assistant/tests/test_services.py
git commit -m "Serialise generations and audit every call, success or not"
```

---

### Task 3: Prompts, with the static-prefix guarantee

**Files:**
- Create: `backend/assistant/prompts.py`
- Create: `backend/assistant/tests/test_prompts.py`

**Interfaces:**
- Consumes: `children.models.Child`.
- Produces: `REMARK_POLISH_SYSTEM`, `BRIEF_SYSTEM`, `SUMMARY_SYSTEM`,
  `CENSUS_SYSTEM` (str constants); `BRIEF_INSTRUCTIONS`, `SUMMARY_INSTRUCTIONS`,
  `CENSUS_INSTRUCTIONS`, `REMARK_INSTRUCTIONS` (str constants);
  `child_age(child) -> str`; `build_brief_prompt(child) -> str`;
  `build_remark_prompt(raw_text) -> str`;
  `build_summary_prompt(extracted_text, kind) -> str`;
  `build_census_prompt(figures: dict) -> str`.

- [ ] **Step 1: Write the failing test**

Create `backend/assistant/tests/test_prompts.py`:

```python
from datetime import date

from django.test import TestCase

from assistant import prompts
from children.models import Child


class ChildAgeTest(TestCase):
    def test_unknown_when_no_birth_date(self):
        self.assertEqual(prompts.child_age(Child(fullname="A")), "unknown")

    def test_computed_from_birth_date(self):
        child = Child(fullname="A", birth_date=date(2015, 6, 1))
        age = prompts.child_age(child)
        self.assertTrue(age.isdigit(), f"expected a number, got {age!r}")


class BriefPromptTest(TestCase):
    def setUp(self):
        self.child = Child.objects.create(
            fullname="Maria Santos", birth_date=date(2015, 6, 1), gender="female")

    def test_includes_age_and_gender_so_the_model_need_not_guess(self):
        prompt = prompts.build_brief_prompt(self.child)
        self.assertIn("Age:", prompt)
        self.assertIn("Gender: female", prompt)

    def test_unspecified_gender_is_labelled_not_omitted(self):
        child = Child.objects.create(fullname="Ben", birth_date=None)
        prompt = prompts.build_brief_prompt(child)
        self.assertIn("Age: unknown", prompt)
        self.assertIn("Gender: unspecified", prompt)

    def test_forbids_inventing_details(self):
        self.assertIn("Do not state age, gender, or any other detail not given",
                      prompts.BRIEF_INSTRUCTIONS)

    def test_static_instructions_come_first_and_carry_no_case_data(self):
        """This is the prefix-cache guarantee: ~17s per call depends on it."""
        other = Child.objects.create(fullname="Juan Dela Cruz", gender="male")
        a = prompts.build_brief_prompt(self.child)
        b = prompts.build_brief_prompt(other)
        self.assertTrue(a.startswith(prompts.BRIEF_INSTRUCTIONS))
        self.assertTrue(b.startswith(prompts.BRIEF_INSTRUCTIONS))
        self.assertNotIn("Maria", prompts.BRIEF_INSTRUCTIONS)
        self.assertNotIn("Juan", prompts.BRIEF_INSTRUCTIONS)


class OtherPromptsTest(TestCase):
    def test_remark_prompt_puts_instructions_first(self):
        p = prompts.build_remark_prompt("kid came in late again")
        self.assertTrue(p.startswith(prompts.REMARK_INSTRUCTIONS))
        self.assertIn("kid came in late again", p)

    def test_summary_prompt_puts_instructions_first(self):
        p = prompts.build_summary_prompt("Some report text.", "report")
        self.assertTrue(p.startswith(prompts.SUMMARY_INSTRUCTIONS))
        self.assertIn("Some report text.", p)

    def test_census_prompt_forbids_calculating(self):
        p = prompts.build_census_prompt({"active_children": 40})
        self.assertTrue(p.startswith(prompts.CENSUS_INSTRUCTIONS))
        self.assertIn("active_children: 40", p)
        self.assertIn("Do not calculate", prompts.CENSUS_INSTRUCTIONS)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python.exe manage.py test assistant.tests.test_prompts -v 2`
Expected: FAIL — `ModuleNotFoundError: No module named 'assistant.prompts'`

- [ ] **Step 3: Write the implementation**

`backend/assistant/prompts.py`:

```python
"""Prompt templates.

Every builder returns STATIC_INSTRUCTIONS + dynamic_facts, in that order and
never the other way round. The static half is a module constant so it is
literally the same bytes on every call, which keeps the runtime's prefix cache
warm — the difference between a 0.37s and a 17s prefill.
"""
from django.utils import timezone

# --- systems -------------------------------------------------------------

REMARK_POLISH_SYSTEM = (
    "You rewrite clinical case notes for a child protection agency in clear, "
    "professional English. You keep every fact exactly as given. You never add "
    "information, never diagnose, and never estimate ages or dates."
)

BRIEF_SYSTEM = (
    "You prepare short factual briefs for a licensed psychologist before a "
    "session with a child. You use only the facts you are given."
)

SUMMARY_SYSTEM = (
    "You summarise case documents for a child protection agency. You report "
    "only what the document says."
)

CENSUS_SYSTEM = (
    "You write short factual narratives about agency caseload figures. You "
    "restate the figures you are given and never compute new ones."
)

# --- static instruction blocks -------------------------------------------

REMARK_INSTRUCTIONS = (
    "Rewrite the case note below in clear professional English.\n"
    "Keep every fact. Do not add anything that is not written.\n"
    "Return only the rewritten note, with no preamble.\n\n"
    "NOTE:\n"
)

BRIEF_INSTRUCTIONS = (
    "Write a short pre-session brief for the psychologist from the facts "
    "below.\n"
    "Cover, in this order: (1) where the case stands, (2) what has changed "
    "recently, (3) what to look for in this session.\n"
    "Use only the facts provided below. Do not state age, gender, or any other "
    "detail not given. Refer to the child by first name only.\n"
    "Do not diagnose and do not suggest a score or rating.\n"
    "Keep it under 200 words.\n\n"
    "FACTS:\n"
)

SUMMARY_INSTRUCTIONS = (
    "Summarise the document below.\n"
    "Cover: (1) background and family or social context, 3-5 bullets; "
    "(2) presenting concerns, 2-4 bullets; (3) recommendations the author "
    "noted, 1-3 bullets.\n"
    "Use only information present in the text. If a section has nothing, write "
    "'Not stated'.\n\n"
    "DOCUMENT:\n"
)

CENSUS_INSTRUCTIONS = (
    "Write a short narrative describing the caseload figures below.\n"
    "Restate the figures given. Do not calculate anything, do not infer trends "
    "that are not stated, and do not name any child.\n"
    "Two short paragraphs at most.\n\n"
    "FIGURES:\n"
)


# --- builders ------------------------------------------------------------

def child_age(child):
    """Age in years as a string, or the literal 'unknown'.

    The model guessed ages in V2 when it was not told one, so it is always
    told one — including being told that it is unknown.
    """
    if not child.birth_date:
        return "unknown"
    today = timezone.localdate()
    born = child.birth_date
    years = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
    return str(years)


def build_brief_prompt(child):
    facts = [
        f"First name: {(child.fullname or '').split(' ')[0]}",
        f"Age: {child_age(child)}",
        f"Gender: {child.gender or 'unspecified'}",
        f"Case status: {child.status or 'unknown'}",
    ]
    remarks = child.remarks.all()[:5] if child.pk else []
    if remarks:
        facts.append("Recent remarks (newest first):")
        facts.extend(f"- {r.date}: {r.text}" for r in remarks)
    else:
        facts.append("Recent remarks: none recorded.")
    return BRIEF_INSTRUCTIONS + "\n".join(facts)


def build_remark_prompt(raw_text):
    return REMARK_INSTRUCTIONS + raw_text


def build_summary_prompt(extracted_text, kind):
    # `kind` labels the document for the reader; it goes after the static block.
    return SUMMARY_INSTRUCTIONS + f"({kind})\n{extracted_text}"


def build_census_prompt(figures):
    lines = [f"{key}: {value}" for key, value in sorted(figures.items())]
    return CENSUS_INSTRUCTIONS + "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/Scripts/python.exe manage.py test assistant -v 2`
Expected: PASS — zero failures, zero errors.

- [ ] **Step 5: Commit**

```bash
git add backend/assistant/prompts.py backend/assistant/tests/test_prompts.py
git commit -m "Put the static half of every prompt first, and prove it stays there"
```

---

### Task 4: The base view, settings endpoint, and URL wiring

**Files:**
- Create: `backend/assistant/views.py`, `backend/assistant/serializers.py`, `backend/assistant/urls.py`
- Create: `backend/assistant/tests/test_settings_api.py`
- Modify: `backend/config/urls.py:9-16`

**Interfaces:**
- Consumes: `services.gate`, `services.AIUnavailable`, `AssistantSetting`.
- Produces: `AssistantBaseView` (DRF `GenericAPIView` subclass translating
  `AIUnavailable` into a 503); `GET/PUT /api/assistant/settings/` (administrator
  only); `AssistantSettingSerializer`.

- [ ] **Step 1: Write the failing test**

Create `backend/assistant/tests/test_settings_api.py`:

```python
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from accounts.models import Role
from assistant.models import AssistantSetting

User = get_user_model()


class AssistantSettingsApiTest(APITestCase):
    def setUp(self):
        self.admin_role = Role.objects.create(role_name=Role.ADMINISTRATOR)
        self.psy_role = Role.objects.create(role_name=Role.PSYCHOLOGIST)
        self.admin = User.objects.create_user(
            email="a@racco1.gov.ph", username="a", password="pass1234",
            role=self.admin_role)
        self.psy = User.objects.create_user(
            email="p@racco1.gov.ph", username="p", password="pass1234",
            role=self.psy_role)

    def test_administrator_can_read_settings(self):
        self.client.force_authenticate(self.admin)
        res = self.client.get("/api/assistant/settings/")
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.data["enabled"])
        self.assertEqual(res.data["model_name"], "qwen2.5:3b-instruct")

    def test_psychologist_cannot_read_settings(self):
        self.client.force_authenticate(self.psy)
        self.assertEqual(self.client.get("/api/assistant/settings/").status_code, 403)

    def test_anonymous_cannot_read_settings(self):
        self.assertIn(self.client.get("/api/assistant/settings/").status_code, (401, 403))

    def test_administrator_can_switch_the_assistant_on(self):
        self.client.force_authenticate(self.admin)
        res = self.client.put("/api/assistant/settings/", {
            "enabled": True, "feature_brief": True, "feature_doc_intelligence": True,
            "feature_remark_polish": True, "feature_census_narrative": True,
            "ollama_url": "http://localhost:11434",
            "model_name": "qwen2.5:3b-instruct",
        }, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(AssistantSetting.load().enabled)

    def test_settings_stay_a_singleton(self):
        self.client.force_authenticate(self.admin)
        self.client.put("/api/assistant/settings/", {"enabled": True},
                        format="json")
        self.client.put("/api/assistant/settings/", {"enabled": False},
                        format="json")
        self.assertEqual(AssistantSetting.objects.count(), 1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python.exe manage.py test assistant.tests.test_settings_api -v 2`
Expected: FAIL — 404, the URL does not exist yet

- [ ] **Step 3: Write serializer and views**

`backend/assistant/serializers.py`:

```python
from rest_framework import serializers

from assistant.models import AssistantJob, AssistantSetting


class AssistantSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssistantSetting
        fields = ["enabled", "feature_brief", "feature_doc_intelligence",
                  "feature_remark_polish", "feature_census_narrative",
                  "ollama_url", "model_name", "updated_at"]
        read_only_fields = ["updated_at"]


class AssistantJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssistantJob
        fields = ["id", "job_type", "input_ref", "output_text", "model_used",
                  "latency_ms", "ok", "error", "outcome", "created_at"]
```

`backend/assistant/views.py`:

```python
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import IsAdministrator
from assistant.models import AssistantSetting
from assistant.serializers import AssistantSettingSerializer
from assistant.services import AIUnavailable


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
```

`backend/assistant/urls.py`:

```python
from django.urls import path

from assistant.views import AssistantSettingView

urlpatterns = [
    path("assistant/settings/", AssistantSettingView.as_view(),
         name="assistant-settings"),
]
```

- [ ] **Step 4: Wire the URLs**

In `backend/config/urls.py`, add after the `samd` line:

```python
    path("api/", include("assistant.urls")),
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && .venv/Scripts/python.exe manage.py test assistant -v 2`
Expected: PASS — zero failures, zero errors.

- [ ] **Step 6: Commit**

```bash
git add backend/assistant backend/config/urls.py
git commit -m "Expose the assistant switch to administrators only"
```

---

### Task 5: `manage.py ai_check`

**Files:**
- Create: `backend/assistant/management/__init__.py`, `backend/assistant/management/commands/__init__.py`, `backend/assistant/management/commands/ai_check.py`
- Create: `backend/assistant/tests/test_ai_check.py`

**Interfaces:**
- Consumes: `services.get_ai_client`, `AssistantSetting`.
- Produces: `manage.py ai_check` — exit code 0 when a draft can be produced,
  1 otherwise.

This exists because "sign-in works but every draft 503s" is otherwise hard to
diagnose, and this project cannot depend on a shell being available in a hosted
environment.

- [ ] **Step 1: Write the failing test**

Create `backend/assistant/tests/test_ai_check.py`:

```python
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from assistant import services
from assistant.models import AssistantSetting


class AiCheckCommandTest(TestCase):
    def test_reports_switched_off_without_calling_the_runtime(self):
        out = StringIO()
        with self.assertRaises(SystemExit) as ctx:
            call_command("ai_check", stdout=out)
        self.assertEqual(ctx.exception.code, 1)
        self.assertIn("switched off", out.getvalue())

    def test_reports_ok_and_latency_when_reachable(self):
        cfg = AssistantSetting.load()
        cfg.enabled = True
        cfg.save()
        out = StringIO()
        with patch.object(services.OllamaClient, "generate", return_value="OK"):
            call_command("ai_check", stdout=out)
        text = out.getvalue()
        self.assertIn("reachable", text)
        self.assertIn("qwen2.5:3b-instruct", text)

    def test_reports_unreachable_runtime_as_failure(self):
        cfg = AssistantSetting.load()
        cfg.enabled = True
        cfg.save()
        out = StringIO()
        err = services.AIUnavailable("Local AI runtime unreachable: refused")
        with patch.object(services.OllamaClient, "generate", side_effect=err):
            with self.assertRaises(SystemExit) as ctx:
                call_command("ai_check", stdout=out)
        self.assertEqual(ctx.exception.code, 1)
        self.assertIn("unreachable", out.getvalue())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python.exe manage.py test assistant.tests.test_ai_check -v 2`
Expected: FAIL — `CommandError: Unknown command: 'ai_check'`

- [ ] **Step 3: Write the command**

Create the two empty `__init__.py` files, then
`backend/assistant/management/commands/ai_check.py`:

```python
"""Smoke-test the local model runtime.

Prints what is configured, whether it answers, and how long it took. Exits 1
when a draft could not be produced, so it is usable from a script.
"""
import time

from django.core.management.base import BaseCommand

from assistant.models import AssistantSetting
from assistant.services import AIUnavailable, get_ai_client


class Command(BaseCommand):
    help = "Check that the local model runtime is reachable and answering."

    def handle(self, *args, **options):
        cfg = AssistantSetting.load()
        self.stdout.write(f"URL:   {cfg.ollama_url}")
        self.stdout.write(f"Model: {cfg.model_name}")

        if not cfg.enabled:
            self.stdout.write("Result: the assistant is switched off.")
            raise SystemExit(1)

        client = get_ai_client()
        started = time.monotonic()
        try:
            client.generate("Reply with the single word: OK.")
        except AIUnavailable as exc:
            self.stdout.write(f"Result: {exc}")
            raise SystemExit(1)

        elapsed = int((time.monotonic() - started) * 1000)
        self.stdout.write(f"Result: reachable, answered in {elapsed} ms.")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/Scripts/python.exe manage.py test assistant -v 2`
Expected: PASS — zero failures, zero errors.

- [ ] **Step 5: Run the full suite — nothing existing may break**

Run: `cd backend && .venv/Scripts/python.exe manage.py test`
Expected: PASS, 379 existing + 31 new

- [ ] **Step 6: Commit**

```bash
git add backend/assistant
git commit -m "Add ai_check so a silent 503 can be diagnosed without a shell"
```

---

# Phase B — Remark Polish

Tasks 6–8. The cheapest feature, built first because it touches one field on one
screen and proves the whole spine end to end. Measured at 9.8 s.

### Task 6: The polish endpoint

**Files:**
- Modify: `backend/assistant/views.py`, `backend/assistant/urls.py`
- Create: `backend/assistant/tests/test_remark_polish.py`

**Interfaces:**
- Consumes: `services.gate`, `services.run_job`, `services.DISCLAIMER`,
  `prompts.build_remark_prompt`, `prompts.REMARK_POLISH_SYSTEM`.
- Produces: `POST /api/assistant/polish-remark/` with body `{"text": str}`,
  returning `{"draft": str, "job_id": int, "disclaimer": str}`.

- [ ] **Step 1: Write the failing test**

Create `backend/assistant/tests/test_remark_polish.py`:

```python
from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from accounts.models import Role
from assistant import services
from assistant.models import AssistantJob, AssistantSetting

User = get_user_model()
URL = "/api/assistant/polish-remark/"


class RemarkPolishTest(APITestCase):
    def setUp(self):
        self.psy_role = Role.objects.create(role_name=Role.PSYCHOLOGIST)
        self.psy = User.objects.create_user(
            email="p@racco1.gov.ph", username="p", password="pass1234",
            role=self.psy_role)
        cfg = AssistantSetting.load()
        cfg.enabled = True
        cfg.save()
        self.client.force_authenticate(self.psy)

    def test_returns_draft_and_job_id(self):
        with patch.object(services.OllamaClient, "generate",
                          return_value="The child arrived late."):
            res = self.client.post(URL, {"text": "kid late again"}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["draft"], "The child arrived late.")
        self.assertEqual(res.data["disclaimer"], services.DISCLAIMER)
        self.assertTrue(AssistantJob.objects.filter(
            id=res.data["job_id"], job_type="remark_polish").exists())

    def test_blank_text_is_rejected(self):
        res = self.client.post(URL, {"text": "   "}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_missing_text_is_rejected(self):
        self.assertEqual(self.client.post(URL, {}, format="json").status_code, 400)

    def test_503_when_master_switch_off(self):
        cfg = AssistantSetting.load()
        cfg.enabled = False
        cfg.save()
        res = self.client.post(URL, {"text": "note"}, format="json")
        self.assertEqual(res.status_code, 503)

    def test_503_when_feature_flag_off(self):
        cfg = AssistantSetting.load()
        cfg.feature_remark_polish = False
        cfg.save()
        res = self.client.post(URL, {"text": "note"}, format="json")
        self.assertEqual(res.status_code, 503)

    def test_503_when_runtime_unreachable(self):
        err = services.AIUnavailable("Local AI runtime unreachable: refused")
        with patch.object(services.OllamaClient, "generate", side_effect=err):
            res = self.client.post(URL, {"text": "note"}, format="json")
        self.assertEqual(res.status_code, 503)
        self.assertFalse(AssistantJob.objects.get().ok)

    def test_anonymous_is_refused(self):
        self.client.force_authenticate(None)
        self.assertIn(self.client.post(URL, {"text": "n"}, format="json").status_code,
                      (401, 403))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python.exe manage.py test assistant.tests.test_remark_polish -v 2`
Expected: FAIL — 404

- [ ] **Step 3: Add the view**

Append to `backend/assistant/views.py`:

```python
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
```

Extend the imports at the top of `views.py`:

```python
from assistant import prompts
from assistant.services import AIUnavailable, DISCLAIMER, gate, run_job
```

- [ ] **Step 4: Add the route**

In `backend/assistant/urls.py`, import `RemarkPolishView` and add:

```python
    path("assistant/polish-remark/", RemarkPolishView.as_view(),
         name="assistant-polish-remark"),
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && .venv/Scripts/python.exe manage.py test assistant -v 2`
Expected: PASS — zero failures, zero errors.

- [ ] **Step 6: Commit**

```bash
git add backend/assistant
git commit -m "Draft a polished remark without saving anything"
```

---

### Task 7: The outcome feedback endpoint

**Files:**
- Modify: `backend/assistant/views.py`, `backend/assistant/urls.py`
- Create: `backend/assistant/tests/test_feedback.py`

**Interfaces:**
- Consumes: `AssistantJob`, `AssistantBaseView`.
- Produces: `POST /api/assistant/jobs/<int:job_id>/feedback/` with body
  `{"outcome": "accepted"|"edited"|"discarded"}`, returning `{"outcome": str}`.
  Creator or administrator only; 404 otherwise.

This is what turns the audit trail into evaluation evidence — "the psychologist
accepted N% of drafts" — and it is the quality safeguard for a 3B model.

- [ ] **Step 1: Write the failing test**

Create `backend/assistant/tests/test_feedback.py`:

```python
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from accounts.models import Role
from assistant.models import AssistantJob

User = get_user_model()


class FeedbackTest(APITestCase):
    def setUp(self):
        psy_role = Role.objects.create(role_name=Role.PSYCHOLOGIST)
        admin_role = Role.objects.create(role_name=Role.ADMINISTRATOR)
        self.owner = User.objects.create_user(
            email="p@racco1.gov.ph", username="p", password="pass1234", role=psy_role)
        self.other = User.objects.create_user(
            email="q@racco1.gov.ph", username="q", password="pass1234", role=psy_role)
        self.admin = User.objects.create_user(
            email="a@racco1.gov.ph", username="a", password="pass1234", role=admin_role)
        self.job = AssistantJob.objects.create(
            job_type="remark_polish", output_text="draft", created_by=self.owner)

    def _url(self, job=None):
        return f"/api/assistant/jobs/{(job or self.job).id}/feedback/"

    def test_creator_can_record_outcome(self):
        self.client.force_authenticate(self.owner)
        res = self.client.post(self._url(), {"outcome": "accepted"}, format="json")
        self.assertEqual(res.status_code, 200)
        self.job.refresh_from_db()
        self.assertEqual(self.job.outcome, AssistantJob.ACCEPTED)

    def test_administrator_can_record_outcome(self):
        self.client.force_authenticate(self.admin)
        res = self.client.post(self._url(), {"outcome": "discarded"}, format="json")
        self.assertEqual(res.status_code, 200)

    def test_another_psychologist_gets_404_not_403(self):
        self.client.force_authenticate(self.other)
        res = self.client.post(self._url(), {"outcome": "accepted"}, format="json")
        self.assertEqual(res.status_code, 404)

    def test_invalid_outcome_is_rejected(self):
        self.client.force_authenticate(self.owner)
        res = self.client.post(self._url(), {"outcome": "brilliant"}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_feedback_works_with_the_assistant_switched_off(self):
        """It only writes history, so it must not 503."""
        self.client.force_authenticate(self.owner)
        res = self.client.post(self._url(), {"outcome": "edited"}, format="json")
        self.assertEqual(res.status_code, 200)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python.exe manage.py test assistant.tests.test_feedback -v 2`
Expected: FAIL — 404

- [ ] **Step 3: Add the view**

Append to `backend/assistant/views.py`:

```python
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
```

Add to the imports in `views.py`:

```python
from accounts.models import Role
from assistant.models import AssistantJob


def _role(request):
    return getattr(getattr(request.user, "role", None), "role_name", None)
```

- [ ] **Step 4: Add the route**

In `backend/assistant/urls.py`, import `AssistantJobFeedbackView` and add:

```python
    path("assistant/jobs/<int:job_id>/feedback/",
         AssistantJobFeedbackView.as_view(), name="assistant-job-feedback"),
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && .venv/Scripts/python.exe manage.py test assistant -v 2`
Expected: PASS — zero failures, zero errors.

- [ ] **Step 6: Commit**

```bash
git add backend/assistant
git commit -m "Record what the psychologist did with each draft"
```

---

### Task 8: Remark polish in the UI

**Files:**
- Create: `frontend/src/api/assistant.js`
- Modify: `frontend/src/pages/ChildProgressReport.jsx:20-90` (state + handlers), `:421-430` (remark card)

**Interfaces:**
- Consumes: `POST /api/assistant/polish-remark/`,
  `POST /api/assistant/jobs/<id>/feedback/`.
- Produces: `polishRemark(text)`, `sendFeedback(jobId, outcome)`,
  `getAssistantSettings()`, `saveAssistantSettings(payload)` from
  `frontend/src/api/assistant.js`.

- [ ] **Step 1: Write the API module**

Create `frontend/src/api/assistant.js`:

```javascript
import api from './client';

// Every call here degrades silently at the call site: the assistant returns 503
// when it is switched off, and no screen may break because of that.
export const polishRemark = (text) =>
  api.post('/assistant/polish-remark/', { text }).then((r) => r.data);

export const sendFeedback = (jobId, outcome) =>
  api.post(`/assistant/jobs/${jobId}/feedback/`, { outcome }).then((r) => r.data);

export const getAssistantSettings = () =>
  api.get('/assistant/settings/').then((r) => r.data);

export const saveAssistantSettings = (payload) =>
  api.put('/assistant/settings/', payload).then((r) => r.data);
```

- [ ] **Step 2: Add state to ChildProgressReport**

In `frontend/src/pages/ChildProgressReport.jsx`, add to the imports:

```javascript
import { polishRemark, sendFeedback } from '../api/assistant';
```

Add these next to `const [remarkText, setRemarkText] = useState('');` — **with
the other hooks, above every early return.** A hook below an early return has
already crashed this exact page once (see CLAUDE.md):

```javascript
  const [polishing, setPolishing] = useState(false);
  const [polishJob, setPolishJob] = useState(null); // { id, draft }
```

- [ ] **Step 3: Add the handler**

Add next to `addRemark`:

```javascript
  const polish = async () => {
    const raw = remarkText.trim();
    if (!raw) return;
    setPolishing(true);
    try {
      const { draft, job_id } = await polishRemark(raw);
      setRemarkText(draft);
      setPolishJob({ id: job_id, draft });
    } catch (err) {
      // 503 means the assistant is off or the runtime is down. That is a normal
      // state, not an error the psychologist caused.
      toast.error(err.response?.status === 503
        ? 'The writing assistant is unavailable right now.'
        : 'Could not polish the remark.');
    } finally {
      setPolishing(false);
    }
  };
```

Then change `addRemark` so saving records the outcome. Replace its body with:

```javascript
  const addRemark = async () => {
    if (!remarkText.trim()) return;
    const saved = remarkText.trim();
    try {
      await api.post('/remarks/', { child: Number(id), text: saved });
      if (polishJob) {
        // Accepted if the saved text is the draft verbatim, else edited.
        const outcome = saved === polishJob.draft.trim() ? 'accepted' : 'edited';
        sendFeedback(polishJob.id, outcome).catch(() => {});
        setPolishJob(null);
      }
      setRemarkText(''); load(); toast.success('Remark added');
    } catch (err) { toast.error(err.response?.data?.detail || 'Could not add the remark.'); }
  };
```

- [ ] **Step 4: Add the button**

In the remarks card, replace the button row (around line 427) so the polish
action sits beside "Add remark":

```jsx
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <Button variant="ghost" onClick={polish}
                      disabled={!remarkText.trim() || polishing}
                      iconLeft={<Icon name="sparkles" size={16} />}>
                {polishing ? 'Polishing…' : 'Polish writing'}
              </Button>
              <Button variant="primary" onClick={addRemark} iconLeft={<Icon name="plus" size={16} />} disabled={!remarkText.trim()}>Add remark</Button>
            </div>
```

Directly below that row, show the disclaimer only while a draft is pending:

```jsx
            {polishJob && (
              <Alert tone="info" disclaimer style={{ marginTop: 4 }}>
                AI-drafted decision support, not a diagnosis. Review and edit before saving.
              </Alert>
            )}
```

- [ ] **Step 5: Verify the icon name exists**

Run: `grep -n "sparkles" frontend/src/ui/index.jsx`
If it returns nothing, use `name="edit"` instead — `Icon` renders nothing for an
unknown name, which `npm run build` will not catch.

- [ ] **Step 6: Lint and build**

Run: `cd frontend && npm run lint && npm run build`
Expected: both exit 0, with no `react-hooks/rules-of-hooks` warning.

- [ ] **Step 7: Load the page**

Start the app (`run-local.bat`), sign in as a psychologist, open a child's
progress report, type into the remark box, and confirm: the button is disabled
while empty, "Polishing…" appears, and with the assistant off you get the
"unavailable" toast rather than a broken page.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/api/assistant.js frontend/src/pages/ChildProgressReport.jsx
git commit -m "Offer to polish a remark, and notice whether the psychologist kept it"
```

---

# Phase C — Pre-Session Briefs

Tasks 9–12. A brief is ~40 s, so the normal path is pre-generated and the
on-demand path is a labelled fallback.

### Task 9: Generate a brief on demand

**Files:**
- Modify: `backend/assistant/views.py`, `backend/assistant/urls.py`
- Create: `backend/assistant/tests/test_briefs.py`

**Interfaces:**
- Consumes: `prompts.build_brief_prompt`, `prompts.BRIEF_SYSTEM`, `services.run_job`.
- Produces: `POST /api/assistant/brief/child/<int:child_id>/` returning
  `{"draft", "job_id", "generated_at", "disclaimer"}`; module-level helper
  `_visible_children(request) -> QuerySet` shared by Tasks 10 and 11.

- [ ] **Step 1: Write the failing test**

Create `backend/assistant/tests/test_briefs.py`:

```python
from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from accounts.models import Role
from assistant import services
from assistant.models import AssistantJob, AssistantSetting
from children.models import Child

User = get_user_model()


class BriefTestBase(APITestCase):
    """Shared fixtures only — no tests. Task 10 extends this too, and a
    subclass that inherited these tests would re-run POST cases against the
    read-only `latest` URL."""

    def setUp(self):
        psy_role = Role.objects.create(role_name=Role.PSYCHOLOGIST)
        admin_role = Role.objects.create(role_name=Role.ADMINISTRATOR)
        self.psy = User.objects.create_user(
            email="p@racco1.gov.ph", username="p", password="pass1234", role=psy_role)
        self.other = User.objects.create_user(
            email="q@racco1.gov.ph", username="q", password="pass1234", role=psy_role)
        self.admin = User.objects.create_user(
            email="a@racco1.gov.ph", username="a", password="pass1234", role=admin_role)
        self.mine = Child.objects.create(fullname="Maria Santos",
                                         assigned_psychologist=self.psy)
        self.theirs = Child.objects.create(fullname="Juan Dela Cruz",
                                           assigned_psychologist=self.other)
        cfg = AssistantSetting.load()
        cfg.enabled = True
        cfg.save()


class BriefTest(BriefTestBase):
    def _url(self, child):
        return f"/api/assistant/brief/child/{child.id}/"

    def test_psychologist_gets_a_brief_for_their_own_child(self):
        self.client.force_authenticate(self.psy)
        with patch.object(services.OllamaClient, "generate", return_value="Brief."):
            res = self.client.post(self._url(self.mine))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["draft"], "Brief.")
        job = AssistantJob.objects.get()
        self.assertEqual(job.input_ref, f"child:{self.mine.id}")
        self.assertEqual(job.job_type, "brief")

    def test_psychologist_gets_404_for_another_psychologists_child(self):
        self.client.force_authenticate(self.psy)
        with patch.object(services.OllamaClient, "generate", return_value="Brief."):
            res = self.client.post(self._url(self.theirs))
        self.assertEqual(res.status_code, 404)
        self.assertFalse(AssistantJob.objects.exists())

    def test_administrator_may_brief_any_child(self):
        self.client.force_authenticate(self.admin)
        with patch.object(services.OllamaClient, "generate", return_value="Brief."):
            res = self.client.post(self._url(self.theirs))
        self.assertEqual(res.status_code, 200)

    def test_missing_child_is_404(self):
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.post("/api/assistant/brief/child/99999/").status_code, 404)

    def test_503_when_feature_flag_off(self):
        cfg = AssistantSetting.load()
        cfg.feature_brief = False
        cfg.save()
        self.client.force_authenticate(self.psy)
        self.assertEqual(self.client.post(self._url(self.mine)).status_code, 503)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python.exe manage.py test assistant.tests.test_briefs -v 2`
Expected: FAIL — 404

- [ ] **Step 3: Add the scoping helper and the view**

Append to `backend/assistant/views.py`:

```python
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
```

Add to the imports in `views.py`:

```python
from children.models import Child
```

**Note the order in `post`:** the gate runs before the lookup, so a switched-off
assistant returns 503 rather than leaking whether a child id exists.

- [ ] **Step 4: Add the route**

```python
    path("assistant/brief/child/<int:child_id>/", PreSessionBriefView.as_view(),
         name="assistant-brief"),
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && .venv/Scripts/python.exe manage.py test assistant -v 2`
Expected: PASS — zero failures, zero errors.

- [ ] **Step 6: Commit**

```bash
git add backend/assistant
git commit -m "Brief a psychologist on their own child, and nobody else's"
```

---

### Task 10: Serve today's brief instantly

**Files:**
- Modify: `backend/assistant/views.py`, `backend/assistant/urls.py`
- Modify: `backend/assistant/tests/test_briefs.py`

**Interfaces:**
- Consumes: `_visible_children` (Task 9), `AssistantJob`.
- Produces: `GET /api/assistant/brief/child/<int:child_id>/latest/` returning
  `{"draft", "job_id", "generated_at", "disclaimer"}`, or 404 when no `ok` brief
  for that child exists from today.

- [ ] **Step 1: Write the failing test**

Append to `backend/assistant/tests/test_briefs.py`:

```python
from datetime import timedelta

from django.utils import timezone


class LatestBriefTest(BriefTestBase):
    """Extends the fixture base, NOT BriefTest — inheriting BriefTest's cases
    would replay its POST tests against this read-only URL."""

    def _url(self, child):
        return f"/api/assistant/brief/child/{child.id}/latest/"

    def _make_brief(self, child, *, ok=True, days_ago=0):
        job = AssistantJob.objects.create(
            job_type="brief", input_ref=f"child:{child.id}",
            output_text="Yesterday's brief" if days_ago else "Today's brief",
            ok=ok, created_by=self.psy)
        if days_ago:
            AssistantJob.objects.filter(pk=job.pk).update(
                created_at=timezone.now() - timedelta(days=days_ago))
        return job

    def test_returns_todays_brief(self):
        self._make_brief(self.mine)
        self.client.force_authenticate(self.psy)
        res = self.client.get(self._url(self.mine))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["draft"], "Today's brief")

    def test_404_when_none_today(self):
        self._make_brief(self.mine, days_ago=1)
        self.client.force_authenticate(self.psy)
        self.assertEqual(self.client.get(self._url(self.mine)).status_code, 404)

    def test_ignores_failed_jobs(self):
        self._make_brief(self.mine, ok=False)
        self.client.force_authenticate(self.psy)
        self.assertEqual(self.client.get(self._url(self.mine)).status_code, 404)

    def test_another_psychologists_child_is_404(self):
        self._make_brief(self.theirs)
        self.client.force_authenticate(self.psy)
        self.assertEqual(self.client.get(self._url(self.theirs)).status_code, 404)

    def test_works_with_the_assistant_switched_off(self):
        """It only reads history, so it must not 503."""
        self._make_brief(self.mine)
        cfg = AssistantSetting.load()
        cfg.enabled = False
        cfg.save()
        self.client.force_authenticate(self.psy)
        self.assertEqual(self.client.get(self._url(self.mine)).status_code, 200)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python.exe manage.py test assistant.tests.test_briefs -v 2`
Expected: FAIL — 404 on the latest URL

- [ ] **Step 3: Add the view**

Append to `backend/assistant/views.py`:

```python
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
```

Add to the imports in `views.py`:

```python
from django.utils import timezone
```

`AssistantJob.Meta.ordering` is `["-created_at"]`, so `.first()` is the newest.

- [ ] **Step 4: Add the route**

```python
    path("assistant/brief/child/<int:child_id>/latest/", LatestBriefView.as_view(),
         name="assistant-brief-latest"),
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && .venv/Scripts/python.exe manage.py test assistant -v 2`
Expected: PASS — zero failures, zero errors.

- [ ] **Step 6: Commit**

```bash
git add backend/assistant
git commit -m "Serve this morning's brief instead of regenerating it"
```

---

### Task 11: Prefetch tomorrow's work

**Files:**
- Modify: `backend/assistant/views.py`, `backend/assistant/urls.py`
- Create: `backend/assistant/tests/test_prefetch.py`

**Interfaces:**
- Consumes: `_visible_children`, `prompts.build_brief_prompt`, `services.run_job`.
- Produces: `POST /api/assistant/prefetch-briefs/` returning
  `{"queued": [int], "skipped": [int]}` immediately;
  `_generate_briefs_now(child_ids, user)` — the worker body, called directly by
  tests instead of through a thread.

- [ ] **Step 1: Write the failing test**

Create `backend/assistant/tests/test_prefetch.py`:

```python
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import Role
from assistant import services, views
from assistant.models import AssistantJob, AssistantSetting
from children.models import Child
from scheduling.models import Appointment

User = get_user_model()
URL = "/api/assistant/prefetch-briefs/"


class PrefetchTest(APITestCase):
    def setUp(self):
        psy_role = Role.objects.create(role_name=Role.PSYCHOLOGIST)
        self.psy = User.objects.create_user(
            email="p@racco1.gov.ph", username="p", password="pass1234", role=psy_role)
        self.other = User.objects.create_user(
            email="q@racco1.gov.ph", username="q", password="pass1234", role=psy_role)
        self.mine = Child.objects.create(fullname="Maria", assigned_psychologist=self.psy)
        self.theirs = Child.objects.create(fullname="Juan", assigned_psychologist=self.other)
        cfg = AssistantSetting.load()
        cfg.enabled = True
        cfg.save()
        self.client.force_authenticate(self.psy)

    def _appointment(self, child, psychologist, *, days=0):
        start = timezone.now() + timedelta(days=days, hours=1)
        # Appointment has `start` + `duration_minutes` (default 60) — there is
        # no `end` field. Verified against backend/scheduling/models.py.
        return Appointment.objects.create(
            child=child, psychologist=psychologist, start=start,
            status=Appointment.SCHEDULED)

    def test_queues_todays_own_appointments(self):
        self._appointment(self.mine, self.psy)
        with patch.object(views, "_start_prefetch_thread") as spawn:
            res = self.client.post(URL)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["queued"], [self.mine.id])
        spawn.assert_called_once()

    def test_ignores_another_psychologists_appointments(self):
        self._appointment(self.theirs, self.other)
        with patch.object(views, "_start_prefetch_thread"):
            res = self.client.post(URL)
        self.assertEqual(res.data["queued"], [])

    def test_ignores_appointments_on_other_days(self):
        self._appointment(self.mine, self.psy, days=3)
        with patch.object(views, "_start_prefetch_thread"):
            res = self.client.post(URL)
        self.assertEqual(res.data["queued"], [])

    def test_skips_children_that_already_have_a_brief_today(self):
        self._appointment(self.mine, self.psy)
        AssistantJob.objects.create(
            job_type="brief", input_ref=f"child:{self.mine.id}", ok=True,
            output_text="already done")
        with patch.object(views, "_start_prefetch_thread"):
            res = self.client.post(URL)
        self.assertEqual(res.data["queued"], [])
        self.assertEqual(res.data["skipped"], [self.mine.id])

    def test_worker_generates_sequentially_and_audits(self):
        with patch.object(services.OllamaClient, "generate", return_value="Brief."):
            views._generate_briefs_now([self.mine.id], self.psy)
        job = AssistantJob.objects.get()
        self.assertEqual(job.input_ref, f"child:{self.mine.id}")
        self.assertEqual(job.created_by, self.psy)

    def test_worker_survives_a_failing_generation(self):
        """One unreachable call must not abandon the rest of the queue."""
        err = services.AIUnavailable("unreachable")
        with patch.object(services.OllamaClient, "generate", side_effect=err):
            views._generate_briefs_now([self.mine.id], self.psy)  # must not raise
        self.assertFalse(AssistantJob.objects.get().ok)

    def test_503_when_feature_flag_off(self):
        cfg = AssistantSetting.load()
        cfg.feature_brief = False
        cfg.save()
        self.assertEqual(self.client.post(URL).status_code, 503)
```

- [ ] **Step 2: Confirm the Appointment field names**

Run: `grep -n "child\|psychologist\|start\|end\|status\|SCHEDULED" backend/scheduling/models.py | head -20`
If `psychologist` is named differently, fix the test's `_appointment` helper to
match before continuing.

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python.exe manage.py test assistant.tests.test_prefetch -v 2`
Expected: FAIL — 404

- [ ] **Step 4: Add the worker and the view**

Append to `backend/assistant/views.py`:

```python
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
```

Add to the imports in `views.py`:

```python
import logging
import threading

from django.db import connection

from scheduling.models import Appointment

logger = logging.getLogger(__name__)
```

- [ ] **Step 5: Add the route**

```python
    path("assistant/prefetch-briefs/", PrefetchBriefsView.as_view(),
         name="assistant-prefetch-briefs"),
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && .venv/Scripts/python.exe manage.py test assistant -v 2`
Expected: PASS — zero failures, zero errors.

- [ ] **Step 7: Commit**

```bash
git add backend/assistant
git commit -m "Draft today's briefs before anyone asks for them"
```

---

### Task 12: Briefs in the UI

**Files:**
- Modify: `frontend/src/api/assistant.js`
- Modify: `frontend/src/pages/Schedule.jsx`
- Modify: `frontend/src/pages/ChildProgressReport.jsx`

**Interfaces:**
- Consumes: the three brief endpoints.
- Produces: `getLatestBrief(childId)`, `generateBrief(childId)`,
  `prefetchBriefs()` in `frontend/src/api/assistant.js`.

- [ ] **Step 1: Extend the API module**

Append to `frontend/src/api/assistant.js`:

```javascript
export const getLatestBrief = (childId) =>
  api.get(`/assistant/brief/child/${childId}/latest/`).then((r) => r.data);

export const generateBrief = (childId) =>
  api.post(`/assistant/brief/child/${childId}/`).then((r) => r.data);

// Fire and forget. Failures here are invisible on purpose: a schedule screen
// must not report that a background convenience did not happen.
export const prefetchBriefs = () =>
  api.post('/assistant/prefetch-briefs/').catch(() => null);
```

- [ ] **Step 2: Trigger the prefetch from Schedule**

In `frontend/src/pages/Schedule.jsx`, import `prefetchBriefs` from
`../api/assistant`, then fire it once after appointments first load. Place the
effect **with the other hooks, above any early return**:

```javascript
  useEffect(() => {
    prefetchBriefs();
    /* eslint-disable-next-line */
  }, []);
```

- [ ] **Step 3: Add the brief modal to the child report**

In `frontend/src/pages/ChildProgressReport.jsx`, import `getLatestBrief` and
`generateBrief`, add `Modal` to the `../ui` import, and add this state **with
the other hooks**:

```javascript
  const [brief, setBrief] = useState(null);   // { draft, generatedAt, jobId }
  const [briefBusy, setBriefBusy] = useState(false);
```

Add the handler:

```javascript
  const openBrief = async ({ regenerate = false } = {}) => {
    setBriefBusy(true);
    try {
      const data = regenerate
        ? await generateBrief(id)
        : await getLatestBrief(id).catch((err) => {
            // 404 just means nothing was drafted today — fall back to the slow path.
            if (err.response?.status === 404) return generateBrief(id);
            throw err;
          });
      setBrief({ draft: data.draft, generatedAt: data.generated_at, jobId: data.job_id });
    } catch (err) {
      toast.error(err.response?.status === 503
        ? 'The assistant is unavailable right now.'
        : 'Could not prepare the brief.');
    } finally {
      setBriefBusy(false);
    }
  };
```

Add the trigger button in the page header actions:

```jsx
  <Button variant="secondary" onClick={() => openBrief()} disabled={briefBusy}>
    {briefBusy ? 'Preparing…' : 'Pre-session brief'}
  </Button>
```

And the modal, rendered near the other dialogs at the end of the component:

```jsx
  {brief && (
    <Modal open onClose={() => setBrief(null)} title="Pre-session brief"
           subtitle={`Drafted ${new Date(brief.generatedAt).toLocaleTimeString()}`}
           width={560}>
      <Alert tone="info" disclaimer style={{ marginBottom: 12 }}>
        AI-drafted decision support, not a diagnosis. The licensed psychologist
        reviews, edits, and approves all content.
      </Alert>
      <div style={{ whiteSpace: 'pre-wrap', fontSize: 14, lineHeight: 1.6 }}>{brief.draft}</div>
      <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 16 }}>
        <Button variant="ghost" onClick={() => { sendFeedback(brief.jobId, 'discarded').catch(() => {}); setBrief(null); }}>
          Not useful
        </Button>
        <Button variant="ghost" onClick={() => openBrief({ regenerate: true })} disabled={briefBusy}>
          Regenerate (slow)
        </Button>
        <Button variant="primary" onClick={() => { sendFeedback(brief.jobId, 'accepted').catch(() => {}); setBrief(null); }}>
          Useful
        </Button>
      </div>
    </Modal>
  )}
```

- [ ] **Step 4: Lint and build**

Run: `cd frontend && npm run lint && npm run build`
Expected: both exit 0, no `rules-of-hooks` warning.

- [ ] **Step 5: Load both pages**

Open the schedule and a child report as a psychologist. Confirm the schedule
renders normally with the assistant **off** (the prefetch 503 must be invisible),
and that the brief button reports unavailability via a toast rather than a blank
modal.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/assistant.js frontend/src/pages/Schedule.jsx frontend/src/pages/ChildProgressReport.jsx
git commit -m "Open this morning's brief instantly, and say when it was drafted"
```

---

# Phase D — Document Summarization

Tasks 13–15. `PsychologicalReport` and `CaseReferral` already carry
`extracted_text`, `ai_summary`, and `ai_summary_confirmed` — **no migration is
needed.**

### Task 13: Summarize a report or a referral

**Files:**
- Modify: `backend/assistant/views.py`, `backend/assistant/urls.py`
- Create: `backend/assistant/tests/test_summaries.py`

**Interfaces:**
- Consumes: `prompts.build_summary_prompt`, `prompts.SUMMARY_SYSTEM`.
- Produces: `POST /api/assistant/summarize-report/<int:doc_id>/` and
  `POST /api/assistant/summarize-case-referral/<int:doc_id>/`, both returning
  `{"draft", "job_id", "disclaimer"}`; `_DOC_KINDS: dict` mapping a URL kind to
  `(model, job input_ref prefix)`.

- [ ] **Step 1: Write the failing test**

Create `backend/assistant/tests/test_summaries.py`:

```python
from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from accounts.models import Role
from assistant import services
from assistant.models import AssistantJob, AssistantSetting
from children.models import Child
from clinical.models import CaseReferral, PsychologicalReport

User = get_user_model()


class SummaryTestBase(APITestCase):
    """Shared fixtures only — no tests. Task 14 extends this too, and a
    subclass inheriting these tests would silently run them twice."""

    def setUp(self):
        psy_role = Role.objects.create(role_name=Role.PSYCHOLOGIST)
        staff_role = Role.objects.create(role_name=Role.STAFF)
        self.psy = User.objects.create_user(
            email="p@racco1.gov.ph", username="p", password="pass1234", role=psy_role)
        self.other = User.objects.create_user(
            email="q@racco1.gov.ph", username="q", password="pass1234", role=psy_role)
        self.staff = User.objects.create_user(
            email="s@racco1.gov.ph", username="s", password="pass1234", role=staff_role)
        self.child = Child.objects.create(fullname="Maria", assigned_psychologist=self.psy)
        self.report = PsychologicalReport.objects.create(
            child=self.child, author=self.psy, extracted_text="Full report text.")
        self.referral = CaseReferral.objects.create(
            child=self.child, uploaded_by=self.staff, extracted_text="Referral text.")
        cfg = AssistantSetting.load()
        cfg.enabled = True
        cfg.save()


class SummaryTest(SummaryTestBase):
    def test_assigned_psychologist_can_summarize_a_report(self):
        self.client.force_authenticate(self.psy)
        with patch.object(services.OllamaClient, "generate", return_value="Summary."):
            res = self.client.post(f"/api/assistant/summarize-report/{self.report.id}/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["draft"], "Summary.")
        self.report.refresh_from_db()
        self.assertEqual(self.report.ai_summary, "Summary.")
        self.assertFalse(self.report.ai_summary_confirmed)
        self.assertEqual(AssistantJob.objects.get().input_ref,
                         f"report:{self.report.id}")

    def test_staff_can_summarize_a_referral(self):
        self.client.force_authenticate(self.staff)
        with patch.object(services.OllamaClient, "generate", return_value="Summary."):
            res = self.client.post(
                f"/api/assistant/summarize-case-referral/{self.referral.id}/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(AssistantJob.objects.get().input_ref,
                         f"casereferral:{self.referral.id}")

    def test_unassigned_psychologist_gets_404(self):
        self.client.force_authenticate(self.other)
        res = self.client.post(f"/api/assistant/summarize-report/{self.report.id}/")
        self.assertEqual(res.status_code, 404)

    def test_400_when_no_extracted_text(self):
        empty = PsychologicalReport.objects.create(child=self.child, extracted_text="")
        self.client.force_authenticate(self.psy)
        res = self.client.post(f"/api/assistant/summarize-report/{empty.id}/")
        self.assertEqual(res.status_code, 400)

    def test_resummarizing_resets_the_confirmed_flag(self):
        PsychologicalReport.objects.filter(pk=self.report.pk).update(
            ai_summary="Old", ai_summary_confirmed=True)
        self.client.force_authenticate(self.psy)
        with patch.object(services.OllamaClient, "generate", return_value="New."):
            self.client.post(f"/api/assistant/summarize-report/{self.report.id}/")
        self.report.refresh_from_db()
        self.assertEqual(self.report.ai_summary, "New.")
        self.assertFalse(self.report.ai_summary_confirmed)

    def test_503_when_feature_flag_off(self):
        cfg = AssistantSetting.load()
        cfg.feature_doc_intelligence = False
        cfg.save()
        self.client.force_authenticate(self.psy)
        res = self.client.post(f"/api/assistant/summarize-report/{self.report.id}/")
        self.assertEqual(res.status_code, 503)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python.exe manage.py test assistant.tests.test_summaries -v 2`
Expected: FAIL — 404

- [ ] **Step 3: Add the view**

Append to `backend/assistant/views.py`:

```python
# kind -> (model, input_ref prefix, human label for the prompt)
_DOC_KINDS = {
    "report": (PsychologicalReport, "report", "psychological report"),
    "case-referral": (CaseReferral, "casereferral", "case referral"),
}


class DocumentSummaryView(AssistantBaseView):
    """Draft a summary of an uploaded document into its `ai_summary` column.

    The draft is saved unconfirmed. It only becomes clinical text when a human
    confirms it, at which point it is their words, not a draft.
    """
    kind = None

    def post(self, request, doc_id):
        gate("feature_doc_intelligence")
        model, prefix, label = _DOC_KINDS[self.kind]
        doc = model.objects.filter(
            pk=doc_id, child__in=_visible_children(request)).first()
        if not doc:
            return Response({"detail": "Not found."},
                            status=status.HTTP_404_NOT_FOUND)
        if not (doc.extracted_text or "").strip():
            return Response(
                {"detail": "No text could be extracted from this document."},
                status=status.HTTP_400_BAD_REQUEST)

        draft, job = run_job(
            "doc_intelligence",
            prompts.build_summary_prompt(doc.extracted_text, label),
            system=prompts.SUMMARY_SYSTEM,
            input_ref=f"{prefix}:{doc.id}",
            user=request.user)
        doc.ai_summary = draft
        doc.ai_summary_confirmed = False
        doc.save(update_fields=["ai_summary", "ai_summary_confirmed"])
        return Response({"draft": draft, "job_id": job.id,
                         "disclaimer": DISCLAIMER})
```

Add to the imports in `views.py`:

```python
from clinical.models import CaseReferral, PsychologicalReport
```

- [ ] **Step 4: Add the routes**

```python
    path("assistant/summarize-report/<int:doc_id>/",
         DocumentSummaryView.as_view(kind="report"),
         name="assistant-summarize-report"),
    path("assistant/summarize-case-referral/<int:doc_id>/",
         DocumentSummaryView.as_view(kind="case-referral"),
         name="assistant-summarize-case-referral"),
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && .venv/Scripts/python.exe manage.py test assistant -v 2`
Expected: PASS — zero failures, zero errors.

- [ ] **Step 6: Commit**

```bash
git add backend/assistant
git commit -m "Draft a summary of an uploaded document, unconfirmed"
```

---

### Task 14: Confirm a summary

**Files:**
- Modify: `backend/assistant/views.py`, `backend/assistant/urls.py`
- Modify: `backend/assistant/tests/test_summaries.py`

**Interfaces:**
- Consumes: `_DOC_KINDS`, `AssistantJob`.
- Produces: `POST /api/assistant/confirm-summary/<int:doc_id>/` and
  `POST /api/assistant/confirm-case-referral-summary/<int:doc_id>/`, body
  `{"text": str}`, returning `{"ai_summary", "ai_summary_confirmed"}`. Sets the
  matching job's `outcome` to `accepted` or `edited` by comparison.

- [ ] **Step 1: Write the failing test**

Append to `backend/assistant/tests/test_summaries.py`:

```python
class ConfirmSummaryTest(SummaryTestBase):
    """Extends the fixture base, NOT SummaryTest — inheriting its cases would
    run every summarize test a second time."""

    def _draft(self, text="Draft summary."):
        with patch.object(services.OllamaClient, "generate", return_value=text):
            self.client.post(f"/api/assistant/summarize-report/{self.report.id}/")
        return AssistantJob.objects.filter(input_ref=f"report:{self.report.id}").first()

    def test_confirming_unchanged_text_marks_the_job_accepted(self):
        self.client.force_authenticate(self.psy)
        job = self._draft()
        res = self.client.post(
            f"/api/assistant/confirm-summary/{self.report.id}/",
            {"text": "Draft summary."}, format="json")
        self.assertEqual(res.status_code, 200)
        self.report.refresh_from_db()
        job.refresh_from_db()
        self.assertTrue(self.report.ai_summary_confirmed)
        self.assertEqual(job.outcome, AssistantJob.ACCEPTED)

    def test_confirming_changed_text_marks_the_job_edited(self):
        self.client.force_authenticate(self.psy)
        job = self._draft()
        self.client.post(f"/api/assistant/confirm-summary/{self.report.id}/",
                         {"text": "My own words."}, format="json")
        self.report.refresh_from_db()
        job.refresh_from_db()
        self.assertEqual(self.report.ai_summary, "My own words.")
        self.assertEqual(job.outcome, AssistantJob.EDITED)

    def test_whitespace_only_difference_still_counts_as_accepted(self):
        self.client.force_authenticate(self.psy)
        job = self._draft()
        self.client.post(f"/api/assistant/confirm-summary/{self.report.id}/",
                         {"text": "  Draft summary.  "}, format="json")
        job.refresh_from_db()
        self.assertEqual(job.outcome, AssistantJob.ACCEPTED)

    def test_blank_confirmation_is_rejected(self):
        self.client.force_authenticate(self.psy)
        self._draft()
        res = self.client.post(f"/api/assistant/confirm-summary/{self.report.id}/",
                               {"text": "   "}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_unassigned_psychologist_cannot_confirm(self):
        self.client.force_authenticate(self.psy)
        self._draft()
        self.client.force_authenticate(self.other)
        res = self.client.post(f"/api/assistant/confirm-summary/{self.report.id}/",
                               {"text": "Anything."}, format="json")
        self.assertEqual(res.status_code, 404)

    def test_confirming_works_with_the_assistant_switched_off(self):
        """Confirming is the human's own act — it must not need the model."""
        self.client.force_authenticate(self.psy)
        self._draft()
        cfg = AssistantSetting.load()
        cfg.enabled = False
        cfg.save()
        res = self.client.post(f"/api/assistant/confirm-summary/{self.report.id}/",
                               {"text": "Mine."}, format="json")
        self.assertEqual(res.status_code, 200)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python.exe manage.py test assistant.tests.test_summaries -v 2`
Expected: FAIL — 404

- [ ] **Step 3: Add the view**

Append to `backend/assistant/views.py`:

```python
class ConfirmSummaryView(AssistantBaseView):
    """Confirm a summary as the human's own words.

    Not gated: confirming is the psychologist's act, and must keep working
    after an administrator switches the assistant off.
    """
    kind = None

    def post(self, request, doc_id):
        model, prefix, _ = _DOC_KINDS[self.kind]
        doc = model.objects.filter(
            pk=doc_id, child__in=_visible_children(request)).first()
        if not doc:
            return Response({"detail": "Not found."},
                            status=status.HTTP_404_NOT_FOUND)
        text = (request.data.get("text") or "").strip()
        if not text:
            return Response({"detail": "A confirmed summary cannot be empty."},
                            status=status.HTTP_400_BAD_REQUEST)

        doc.ai_summary = text
        doc.ai_summary_confirmed = True
        doc.save(update_fields=["ai_summary", "ai_summary_confirmed"])

        # Whether the human kept the draft verbatim is the evaluation signal.
        job = AssistantJob.objects.filter(
            job_type="doc_intelligence", input_ref=f"{prefix}:{doc.id}",
            ok=True).first()
        if job:
            job.outcome = (AssistantJob.ACCEPTED
                           if job.output_text.strip() == text
                           else AssistantJob.EDITED)
            job.save(update_fields=["outcome"])

        return Response({"ai_summary": doc.ai_summary,
                         "ai_summary_confirmed": doc.ai_summary_confirmed})
```

- [ ] **Step 4: Add the routes**

```python
    path("assistant/confirm-summary/<int:doc_id>/",
         ConfirmSummaryView.as_view(kind="report"),
         name="assistant-confirm-summary"),
    path("assistant/confirm-case-referral-summary/<int:doc_id>/",
         ConfirmSummaryView.as_view(kind="case-referral"),
         name="assistant-confirm-case-referral-summary"),
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && .venv/Scripts/python.exe manage.py test assistant -v 2`
Expected: PASS — zero failures, zero errors.

- [ ] **Step 6: Commit**

```bash
git add backend/assistant
git commit -m "Turn a confirmed summary into the psychologist's own words"
```

---

### Task 15: Summaries in the UI

**Files:**
- Modify: `frontend/src/api/assistant.js`
- Modify: `frontend/src/pages/ChildProgressReport.jsx` (documents area)

**Interfaces:**
- Produces: `summarizeDocument(kind, id)`, `confirmSummary(kind, id, text)` where
  `kind` is `'report' | 'case-referral'`.

- [ ] **Step 1: Extend the API module**

Append to `frontend/src/api/assistant.js`:

```javascript
const SUMMARIZE = { report: 'summarize-report', 'case-referral': 'summarize-case-referral' };
const CONFIRM = { report: 'confirm-summary', 'case-referral': 'confirm-case-referral-summary' };

export const summarizeDocument = (kind, id) =>
  api.post(`/assistant/${SUMMARIZE[kind]}/${id}/`).then((r) => r.data);

export const confirmSummary = (kind, id, text) =>
  api.post(`/assistant/${CONFIRM[kind]}/${id}/`, { text }).then((r) => r.data);
```

- [ ] **Step 2: Find the documents area**

Run: `grep -n "psych_reports\|case_referrals\|ai_summary" frontend/src/pages/ChildProgressReport.jsx`
Note the line numbers — the summary controls attach to each document row there.

- [ ] **Step 3: Add state and handlers**

With the other hooks in `ChildProgressReport.jsx`:

```javascript
  const [summary, setSummary] = useState(null); // { kind, id, text, confirmed }
  const [summaryBusy, setSummaryBusy] = useState(false);
```

```javascript
  const draftSummary = async (kind, docId) => {
    setSummaryBusy(true);
    try {
      const { draft } = await summarizeDocument(kind, docId);
      setSummary({ kind, id: docId, text: draft, confirmed: false });
    } catch (err) {
      toast.error(err.response?.status === 503
        ? 'The assistant is unavailable right now.'
        : err.response?.data?.detail || 'Could not summarise this document.');
    } finally {
      setSummaryBusy(false);
    }
  };

  const saveSummary = async () => {
    try {
      await confirmSummary(summary.kind, summary.id, summary.text);
      setSummary(null); load(); toast.success('Summary confirmed');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Could not confirm the summary.');
    }
  };
```

- [ ] **Step 4: Add the per-document control**

On each report and referral row, beside the existing actions:

```jsx
  <Button variant="ghost" size="sm" disabled={summaryBusy}
          onClick={() => draftSummary('report', doc.id)}>
    {doc.ai_summary ? 'Re-summarise' : 'AI summary'}
  </Button>
  {doc.ai_summary && (
    <Badge tone={doc.ai_summary_confirmed ? 'success' : 'amber'} size="sm">
      {doc.ai_summary_confirmed ? 'Confirmed' : 'Draft (unconfirmed)'}
    </Badge>
  )}
```

Use `'case-referral'` as the first argument on referral rows.

- [ ] **Step 5: Add the editable confirm modal**

Near the other dialogs:

```jsx
  {summary && (
    <Modal open onClose={() => setSummary(null)} title="Document summary" width={620}>
      <Alert tone="info" disclaimer style={{ marginBottom: 12 }}>
        AI-drafted decision support, not a diagnosis. Edit freely — confirming
        makes this your own clinical text.
      </Alert>
      <textarea rows={14} style={textarea} value={summary.text}
                onChange={(e) => setSummary({ ...summary, text: e.target.value })} />
      <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 14 }}>
        <Button variant="ghost" onClick={() => setSummary(null)}>Cancel</Button>
        <Button variant="primary" onClick={saveSummary} disabled={!summary.text.trim()}>
          Confirm summary
        </Button>
      </div>
    </Modal>
  )}
```

- [ ] **Step 6: Confirm the serializers expose the fields**

Run: `grep -n "ai_summary" backend/clinical/serializers.py`
If `ai_summary` and `ai_summary_confirmed` are missing from
`PsychologicalReportSerializer` or `CaseReferralSerializer`, add them to
`fields`, then re-run `cd backend && .venv/Scripts/python.exe manage.py test`.

- [ ] **Step 7: Lint, build, and load**

Run: `cd frontend && npm run lint && npm run build`
Then open a child report with an uploaded document and exercise draft → edit →
confirm, checking the badge flips from "Draft (unconfirmed)" to "Confirmed".

- [ ] **Step 8: Commit**

```bash
git add frontend/src backend/clinical/serializers.py
git commit -m "Summarise a document, then let the psychologist make it theirs"
```

---

# Phase E — Census Narrative

### Task 16: The census endpoint

**Files:**
- Modify: `backend/assistant/views.py`, `backend/assistant/urls.py`
- Create: `backend/assistant/tests/test_census.py`

**Interfaces:**
- Consumes: `prompts.build_census_prompt`, `prompts.CENSUS_SYSTEM`.
- Produces: `POST /api/assistant/census-narrative/` with body
  `{"figures": {str: number}}`, returning `{"draft", "job_id", "disclaimer"}`.
  Administrator and staff only.

The figures come **from the caller**, already computed by
`clinical/reports.py:summary()`. The model restates them and computes nothing.

- [ ] **Step 1: Write the failing test**

Create `backend/assistant/tests/test_census.py`:

```python
from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from accounts.models import Role
from assistant import services
from assistant.models import AssistantJob, AssistantSetting

User = get_user_model()
URL = "/api/assistant/census-narrative/"
FIGURES = {"active_children": 40, "completed_sessions": 112}


class CensusTest(APITestCase):
    def setUp(self):
        admin_role = Role.objects.create(role_name=Role.ADMINISTRATOR)
        staff_role = Role.objects.create(role_name=Role.STAFF)
        psy_role = Role.objects.create(role_name=Role.PSYCHOLOGIST)
        self.admin = User.objects.create_user(
            email="a@racco1.gov.ph", username="a", password="pass1234", role=admin_role)
        self.staff = User.objects.create_user(
            email="s@racco1.gov.ph", username="s", password="pass1234", role=staff_role)
        self.psy = User.objects.create_user(
            email="p@racco1.gov.ph", username="p", password="pass1234", role=psy_role)
        cfg = AssistantSetting.load()
        cfg.enabled = True
        cfg.save()

    def test_administrator_gets_a_narrative(self):
        self.client.force_authenticate(self.admin)
        with patch.object(services.OllamaClient, "generate", return_value="Narrative."):
            res = self.client.post(URL, {"figures": FIGURES}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["draft"], "Narrative.")
        self.assertEqual(AssistantJob.objects.get().job_type, "census_narrative")

    def test_staff_may_also_generate_one(self):
        self.client.force_authenticate(self.staff)
        with patch.object(services.OllamaClient, "generate", return_value="Narrative."):
            self.assertEqual(
                self.client.post(URL, {"figures": FIGURES}, format="json").status_code, 200)

    def test_psychologist_is_refused(self):
        self.client.force_authenticate(self.psy)
        self.assertEqual(
            self.client.post(URL, {"figures": FIGURES}, format="json").status_code, 403)

    def test_empty_figures_are_rejected(self):
        self.client.force_authenticate(self.admin)
        self.assertEqual(
            self.client.post(URL, {"figures": {}}, format="json").status_code, 400)

    def test_non_object_figures_are_rejected(self):
        self.client.force_authenticate(self.admin)
        self.assertEqual(
            self.client.post(URL, {"figures": "lots"}, format="json").status_code, 400)

    def test_503_when_feature_flag_off(self):
        cfg = AssistantSetting.load()
        cfg.feature_census_narrative = False
        cfg.save()
        self.client.force_authenticate(self.admin)
        self.assertEqual(
            self.client.post(URL, {"figures": FIGURES}, format="json").status_code, 503)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python.exe manage.py test assistant.tests.test_census -v 2`
Expected: FAIL — 404

- [ ] **Step 3: Add the view**

Append to `backend/assistant/views.py`:

```python
class CensusNarrativeView(AssistantBaseView):
    """Narrate figures the caller already computed.

    The model receives finished numbers and is told to restate them. It never
    counts anything: a wrong caseload figure in an agency report is far worse
    than no narrative at all.
    """
    permission_classes = [IsAdminOrStaff]

    def post(self, request):
        gate("feature_census_narrative")
        figures = request.data.get("figures")
        if not isinstance(figures, dict) or not figures:
            return Response({"detail": "figures must be a non-empty object."},
                            status=status.HTTP_400_BAD_REQUEST)
        draft, job = run_job(
            "census_narrative",
            prompts.build_census_prompt(figures),
            system=prompts.CENSUS_SYSTEM,
            input_ref="agency:summary",
            user=request.user)
        return Response({"draft": draft, "job_id": job.id,
                         "disclaimer": DISCLAIMER})
```

Add `IsAdminOrStaff` to the `accounts.permissions` import in `views.py`.

- [ ] **Step 4: Add the route**

```python
    path("assistant/census-narrative/", CensusNarrativeView.as_view(),
         name="assistant-census-narrative"),
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && .venv/Scripts/python.exe manage.py test assistant -v 2`
Expected: PASS — zero failures, zero errors.

- [ ] **Step 6: Commit**

```bash
git add backend/assistant
git commit -m "Narrate the caseload figures without recomputing them"
```

---

### Task 17: The census narrative in the UI

**Files:**
- Modify: `frontend/src/api/assistant.js`
- Modify: `frontend/src/pages/AgencySummary.jsx`

**Interfaces:**
- Produces: `censusNarrative(figures)`.

- [ ] **Step 1: Extend the API module**

```javascript
export const censusNarrative = (figures) =>
  api.post('/assistant/census-narrative/', { figures }).then((r) => r.data);
```

- [ ] **Step 2: Add state and the figures builder**

`AgencySummary.jsx` already holds every rendered figure in `d` (the `data ||
EMPTY` fallback at line 28) and the period in `range`. The narrative is built
from **that same object**, so it can never disagree with the numbers on screen.

Add `sendFeedback` and `censusNarrative` to the `../api/assistant` import, then
add with the other hooks:

```javascript
  const [narrative, setNarrative] = useState(null); // { text, jobId }
  const [narrativeBusy, setNarrativeBusy] = useState(false);
```

- [ ] **Step 3: Add the handler**

Place this after `const caseMix = ...`, so `d` is already in scope:

```javascript
  const writeNarrative = async () => {
    setNarrativeBusy(true);
    try {
      // Only finished figures — the model restates these and computes nothing.
      const { draft, job_id } = await censusNarrative({
        period: range,
        completed_pre_assessments: d.total,
        children_seen: d.children,
        pending_pre_assessments: d.pending_pre_assessments,
        psychologists_reporting: (d.per_psychologist || []).length,
        ...Object.fromEntries(
          Object.entries(d.by_case_type || {}).map(([k, v]) => [`case_type_${k}`, v])),
      });
      setNarrative({ text: draft, jobId: job_id });
    } catch (err) {
      toast.error(err.response?.status === 503
        ? 'The assistant is unavailable right now.'
        : 'Could not write the narrative.');
    } finally {
      setNarrativeBusy(false);
    }
  };
```

- [ ] **Step 4: Render the panel**

Add its own card below the stat row:

```jsx
  <Card eyebrow="Assistant" title="Narrative summary" padding="20px"
        actions={<Button variant="ghost" onClick={writeNarrative} disabled={narrativeBusy}>
                   {narrativeBusy ? 'Writing…' : 'Draft narrative'}
                 </Button>}>
    {narrative ? (
      <>
        <Alert tone="info" disclaimer style={{ marginBottom: 12 }}>
          AI-drafted from the figures above. Review before using in any report.
        </Alert>
        <div style={{ whiteSpace: 'pre-wrap', fontSize: 14, lineHeight: 1.6 }}>{narrative.text}</div>
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 12 }}>
          <Button variant="ghost" size="sm"
                  onClick={() => { sendFeedback(narrative.jobId, 'discarded').catch(() => {}); setNarrative(null); }}>
            Not useful
          </Button>
          <Button variant="ghost" size="sm"
                  onClick={() => sendFeedback(narrative.jobId, 'accepted').catch(() => {})}>
            Useful
          </Button>
        </div>
      </>
    ) : (
      <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>
        No narrative drafted yet.
      </div>
    )}
  </Card>
```

- [ ] **Step 5: Lint, build, and load**

Run: `cd frontend && npm run lint && npm run build`
Then open the agency summary as an administrator and confirm the page renders
identically with the assistant off.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/assistant.js frontend/src/pages/AgencySummary.jsx
git commit -m "Offer a narrative built from the figures already on screen"
```

---

# Phase F — Settings and Metrics

### Task 18: The metrics endpoint

**Files:**
- Modify: `backend/assistant/views.py`, `backend/assistant/urls.py`
- Create: `backend/assistant/tests/test_metrics.py`

**Interfaces:**
- Consumes: `AssistantJob`.
- Produces: `GET /api/assistant/metrics/` (administrator only) returning
  `{"window_days": 30, "features": [{job_type, runs, ok, errors, avg_latency_ms,
  accepted, edited, discarded, pending}]}` for the last 30 days.

- [ ] **Step 1: Write the failing test**

Create `backend/assistant/tests/test_metrics.py`:

```python
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import Role
from assistant.models import AssistantJob

User = get_user_model()
URL = "/api/assistant/metrics/"


class MetricsTest(APITestCase):
    def setUp(self):
        admin_role = Role.objects.create(role_name=Role.ADMINISTRATOR)
        psy_role = Role.objects.create(role_name=Role.PSYCHOLOGIST)
        self.admin = User.objects.create_user(
            email="a@racco1.gov.ph", username="a", password="pass1234", role=admin_role)
        self.psy = User.objects.create_user(
            email="p@racco1.gov.ph", username="p", password="pass1234", role=psy_role)

    def _job(self, **kw):
        kw.setdefault("job_type", "remark_polish")
        kw.setdefault("latency_ms", 1000)
        aged = kw.pop("days_ago", 0)
        job = AssistantJob.objects.create(**kw)
        if aged:
            AssistantJob.objects.filter(pk=job.pk).update(
                created_at=timezone.now() - timedelta(days=aged))
        return job

    def _row(self, data, job_type):
        return next(r for r in data["features"] if r["job_type"] == job_type)

    def test_psychologist_is_refused(self):
        self.client.force_authenticate(self.psy)
        self.assertEqual(self.client.get(URL).status_code, 403)

    def test_counts_runs_errors_and_outcomes(self):
        self._job(ok=True, outcome=AssistantJob.ACCEPTED, latency_ms=1000)
        self._job(ok=True, outcome=AssistantJob.EDITED, latency_ms=3000)
        self._job(ok=False, error="unreachable", latency_ms=500)
        self.client.force_authenticate(self.admin)
        row = self._row(self.client.get(URL).data, "remark_polish")
        self.assertEqual(row["runs"], 3)
        self.assertEqual(row["ok"], 2)
        self.assertEqual(row["errors"], 1)
        self.assertEqual(row["accepted"], 1)
        self.assertEqual(row["edited"], 1)
        self.assertEqual(row["avg_latency_ms"], 1500)

    def test_excludes_jobs_older_than_the_window(self):
        self._job(ok=True, days_ago=45)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self._row(self.client.get(URL).data, "remark_polish")["runs"], 0)

    def test_every_feature_appears_even_with_no_runs(self):
        self.client.force_authenticate(self.admin)
        types = {r["job_type"] for r in self.client.get(URL).data["features"]}
        self.assertEqual(types, {"brief", "doc_intelligence", "remark_polish",
                                 "census_narrative"})

    def test_works_with_the_assistant_switched_off(self):
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get(URL).status_code, 200)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python.exe manage.py test assistant.tests.test_metrics -v 2`
Expected: FAIL — 404

- [ ] **Step 3: Add the view**

Append to `backend/assistant/views.py`:

```python
WINDOW_DAYS = 30


class AssistantMetricsView(AssistantBaseView):
    """Per-feature usage over the last 30 days.

    Reads history only, so it is not gated — an administrator deciding whether
    to switch the assistant back on needs exactly this while it is off.
    """
    permission_classes = [IsAdministrator]

    def get(self, request):
        since = timezone.now() - timedelta(days=WINDOW_DAYS)
        rows = []
        for job_type, _label in AssistantJob.TYPE_CHOICES:
            qs = AssistantJob.objects.filter(job_type=job_type, created_at__gte=since)
            agg = qs.aggregate(
                runs=Count("id"),
                ok=Count("id", filter=Q(ok=True)),
                errors=Count("id", filter=Q(ok=False)),
                avg_latency_ms=Avg("latency_ms"),
                accepted=Count("id", filter=Q(outcome=AssistantJob.ACCEPTED)),
                edited=Count("id", filter=Q(outcome=AssistantJob.EDITED)),
                discarded=Count("id", filter=Q(outcome=AssistantJob.DISCARDED)),
                pending=Count("id", filter=Q(outcome=AssistantJob.PENDING)),
            )
            avg = agg["avg_latency_ms"]
            agg["avg_latency_ms"] = int(avg) if avg is not None else None
            rows.append({"job_type": job_type, **agg})
        return Response({"window_days": WINDOW_DAYS, "features": rows})
```

Add to the imports in `views.py` (`IsAdministrator` is already imported from
Task 4 — do not add it twice):

```python
from datetime import timedelta

from django.db.models import Avg, Count, Q
```

- [ ] **Step 4: Add the route**

```python
    path("assistant/metrics/", AssistantMetricsView.as_view(),
         name="assistant-metrics"),
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && .venv/Scripts/python.exe manage.py test assistant -v 2`
Expected: PASS — zero failures, zero errors.

- [ ] **Step 6: Commit**

```bash
git add backend/assistant
git commit -m "Report how often each draft was kept"
```

---

### Task 19: The Settings panel

**Files:**
- Modify: `backend/assistant/views.py`, `backend/assistant/urls.py`
- Create: `backend/assistant/tests/test_check_api.py`
- Modify: `frontend/src/api/assistant.js`
- Modify: `frontend/src/pages/Settings.jsx`

**Interfaces:**
- Consumes: `getAssistantSettings`, `saveAssistantSettings` (Task 8),
  `GET /api/assistant/metrics/` (Task 18), `services.get_ai_client`.
- Produces: `POST /api/assistant/check/` (administrator only) returning
  `{"ok": bool, "detail": str, "latency_ms": int|null}`;
  `getAssistantMetrics()`, `checkAssistant()`.

The Settings screen is the only place an administrator can act on a broken
runtime, and Render's Shell tab is paid-only — so the check has to be reachable
from the UI, not only from `manage.py ai_check`.

- [ ] **Step 1: Write the failing test for the check endpoint**

Create `backend/assistant/tests/test_check_api.py`:

```python
from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from accounts.models import Role
from assistant import services
from assistant.models import AssistantSetting

User = get_user_model()
URL = "/api/assistant/check/"


class CheckApiTest(APITestCase):
    def setUp(self):
        admin_role = Role.objects.create(role_name=Role.ADMINISTRATOR)
        psy_role = Role.objects.create(role_name=Role.PSYCHOLOGIST)
        self.admin = User.objects.create_user(
            email="a@racco1.gov.ph", username="a", password="pass1234", role=admin_role)
        self.psy = User.objects.create_user(
            email="p@racco1.gov.ph", username="p", password="pass1234", role=psy_role)

    def test_psychologist_is_refused(self):
        self.client.force_authenticate(self.psy)
        self.assertEqual(self.client.post(URL).status_code, 403)

    def test_reports_not_ok_when_switched_off(self):
        self.client.force_authenticate(self.admin)
        res = self.client.post(URL)
        self.assertEqual(res.status_code, 200)  # a 200 describing a false, not a 503
        self.assertFalse(res.data["ok"])

    def test_reports_ok_with_latency_when_reachable(self):
        cfg = AssistantSetting.load()
        cfg.enabled = True
        cfg.save()
        self.client.force_authenticate(self.admin)
        with patch.object(services.OllamaClient, "generate", return_value="OK"):
            res = self.client.post(URL)
        self.assertTrue(res.data["ok"])
        self.assertIsNotNone(res.data["latency_ms"])

    def test_reports_the_error_when_unreachable(self):
        cfg = AssistantSetting.load()
        cfg.enabled = True
        cfg.save()
        self.client.force_authenticate(self.admin)
        err = services.AIUnavailable("Local AI runtime unreachable: refused")
        with patch.object(services.OllamaClient, "generate", side_effect=err):
            res = self.client.post(URL)
        self.assertFalse(res.data["ok"])
        self.assertIn("unreachable", res.data["detail"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python.exe manage.py test assistant.tests.test_check_api -v 2`
Expected: FAIL — 404

- [ ] **Step 3: Add the check view and route**

Append to `backend/assistant/views.py`:

```python
class AssistantCheckView(AssistantBaseView):
    """Probe the runtime and describe what happened.

    Returns 200 with ok=false rather than 503: the administrator asked a
    question about the runtime, and "it is unreachable" is a successful answer
    to that question. It also does not write an AssistantJob — a connection
    test is not clinical work and would skew the usage table.
    """
    permission_classes = [IsAdministrator]

    def post(self, request):
        cfg = AssistantSetting.load()
        if not cfg.enabled:
            return Response({"ok": False, "latency_ms": None,
                             "detail": "The assistant is switched off."})
        started = time.monotonic()
        try:
            get_ai_client().generate("Reply with the single word: OK.")
        except AIUnavailable as exc:
            return Response({"ok": False, "latency_ms": None, "detail": str(exc)})
        elapsed = int((time.monotonic() - started) * 1000)
        return Response({"ok": True, "latency_ms": elapsed,
                         "detail": f"{cfg.model_name} answered in {elapsed} ms."})
```

Add to the imports in `views.py`:

```python
import time

from assistant.services import get_ai_client
```

In `backend/assistant/urls.py`, import `AssistantCheckView` and add:

```python
    path("assistant/check/", AssistantCheckView.as_view(), name="assistant-check"),
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/Scripts/python.exe manage.py test assistant -v 2`
Expected: PASS — zero failures, zero errors.

- [ ] **Step 5: Extend the API module**

```javascript
export const getAssistantMetrics = () =>
  api.get('/assistant/metrics/').then((r) => r.data);

export const checkAssistant = () =>
  api.post('/assistant/check/').then((r) => r.data);
```

- [ ] **Step 6: Rewrite Settings.jsx**

Replace `frontend/src/pages/Settings.jsx` entirely:

```jsx
import React, { useEffect, useState } from 'react';
import { Card, Badge, Input, FormField, Switch, Button, Alert, PAGE } from '../ui';
import { useToast } from '../context/ToastContext';
import { getAssistantSettings, saveAssistantSettings, getAssistantMetrics, checkAssistant } from '../api/assistant';

const FEATURE_LABELS = {
  brief: 'Pre-session briefs',
  doc_intelligence: 'Document summaries',
  remark_polish: 'Remark polishing',
  census_narrative: 'Census narrative',
};

const th = { textAlign: 'left', padding: '8px 10px', fontSize: 12, color: 'var(--text-muted)', fontWeight: 600 };
const td = { padding: '8px 10px', fontSize: 13, color: 'var(--text-body)' };

export default function Settings() {
  const toast = useToast();
  const [agency] = useState('St. Joseph Orphanage');
  const [sync, setSync] = useState(true);
  const [cfg, setCfg] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [saving, setSaving] = useState(false);
  const [check, setCheck] = useState(null);   // { ok, detail }
  const [checking, setChecking] = useState(false);

  useEffect(() => {
    getAssistantSettings().then(setCfg).catch(() => setCfg('error'));
    getAssistantMetrics().then(setMetrics).catch(() => setMetrics(null));
  }, []);

  const save = async (patch) => {
    const next = { ...cfg, ...patch };
    setCfg(next);
    setSaving(true);
    try {
      setCfg(await saveAssistantSettings(next));
      toast.success('Assistant settings saved');
    } catch {
      toast.error('Could not save the assistant settings.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ ...PAGE, maxWidth: 760 }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
        <Card eyebrow="Agency" title="Configuration" padding="22px">
          {/* Display-only. These have never had a backend. */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <FormField label="RCPC" hint="Set by the national office — not editable here yet."><Input value={agency} disabled /></FormField>
            <FormField label="NACC API Endpoint" hint="Managed by the national office.">
              <Input value="https://api.nacc.gov.ph/v1/sync" disabled trailing={<Badge tone="success" size="sm">PROD</Badge>} />
            </FormField>
            <Switch checked={sync} onChange={setSync} disabled label="Auto-sync signed reports to NACC" />
          </div>
        </Card>

        <Card eyebrow="Assistant" title="Local writing assistant" padding="22px">
          {cfg === 'error' && <Alert tone="warning">Could not load the assistant settings.</Alert>}
          {cfg && cfg !== 'error' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <Alert tone="info">
                Drafts are produced by a model running on this machine. Case text
                is never sent to an outside service. Every draft is reviewed and
                approved by a person before it becomes clinical text.
              </Alert>
              <Switch checked={cfg.enabled} disabled={saving}
                      onChange={(v) => save({ enabled: v })}
                      label="Assistant enabled" />
              {Object.entries(FEATURE_LABELS).map(([key, label]) => (
                <Switch key={key} checked={cfg[`feature_${key}`]}
                        disabled={saving || !cfg.enabled}
                        onChange={(v) => save({ [`feature_${key}`]: v })}
                        label={label} />
              ))}
              <FormField label="Runtime URL" hint="The local model runtime. Loopback only.">
                <Input value={cfg.ollama_url} disabled={saving}
                       onChange={(e) => setCfg({ ...cfg, ollama_url: e.target.value })} />
              </FormField>
              <FormField label="Model" hint="Must already be pulled on this machine.">
                <Input value={cfg.model_name} disabled={saving}
                       onChange={(e) => setCfg({ ...cfg, model_name: e.target.value })} />
              </FormField>
              <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                <Button variant="ghost" disabled={checking}
                        onClick={async () => {
                          setChecking(true);
                          try { setCheck(await checkAssistant()); }
                          catch { setCheck({ ok: false, detail: 'The check could not be run.' }); }
                          finally { setChecking(false); }
                        }}>
                  {checking ? 'Checking…' : 'Test connection'}
                </Button>
                <Button variant="primary" disabled={saving}
                        onClick={() => save({})}>Save runtime settings</Button>
              </div>
              {check && (
                <Alert tone={check.ok ? 'success' : 'warning'}>{check.detail}</Alert>
              )}
            </div>
          )}
        </Card>

        {metrics && (
          <Card eyebrow="Assistant" title={`Usage — last ${metrics.window_days} days`} padding="22px">
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr>
                    <th style={th}>Feature</th><th style={th}>Runs</th>
                    <th style={th}>Errors</th><th style={th}>Avg</th>
                    <th style={th}>Kept</th><th style={th}>Edited</th>
                    <th style={th}>Discarded</th>
                  </tr>
                </thead>
                <tbody>
                  {metrics.features.map((f) => (
                    <tr key={f.job_type}>
                      <td style={td}>{FEATURE_LABELS[f.job_type] || f.job_type}</td>
                      <td style={td}>{f.runs}</td>
                      <td style={td}>{f.errors}</td>
                      <td style={td}>{f.avg_latency_ms === null ? '—' : `${(f.avg_latency_ms / 1000).toFixed(1)}s`}</td>
                      <td style={td}>{f.accepted}</td>
                      <td style={td}>{f.edited}</td>
                      <td style={td}>{f.discarded}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 7: Lint and build**

Run: `cd frontend && npm run lint && npm run build`
Expected: both exit 0.

- [ ] **Step 8: Load the page as an administrator**

Toggle the master switch and confirm the feature switches disable when it is
off, the values persist across a reload, and the usage table renders with zero
rows for every feature on a fresh database. Press **Test connection** with
Ollama stopped and confirm it reports the failure in a warning rather than
throwing.

- [ ] **Step 9: Commit**

```bash
git add backend/assistant frontend/src/api/assistant.js frontend/src/pages/Settings.jsx
git commit -m "Give administrators the assistant switch, a connection test, and its usage record"
```

---

### Task 20: Documentation

**Files:**
- Modify: `README.md:151-170` (the "No AI layer" section)
- Modify: `CLAUDE.md`
- Modify: `docs/LOCAL-SETUP.md`

- [ ] **Step 1: Replace the README section**

Replace the whole "No AI layer" section (`README.md:151-170`) with:

```markdown
## The writing assistant

An optional writing assistant drafts pre-session briefs, document summaries,
polished remarks, and a census narrative. It is **off by default** and the
system is fully functional with it off — every feature degrades to a 503 that
the screens absorb.

The model runs **on this machine**, through Ollama on loopback. Case text is
never sent to an outside service, which is what makes the Data Privacy Act
story work: there is no additional processor. There is deliberately no hosted
provider — adding one would mean sending clinical interview narratives and
psychologist remarks, the most sensitive free text in the system, to a
processor outside the agency's data-processing agreements.

Everything it produces is a **draft**. Nothing is auto-applied, and a summary
only becomes clinical text when a psychologist confirms it — at which point it
is their words, not the model's. Every call is audited, and Settings shows how
often drafts were kept, edited, or discarded.

It does not score, rate, or classify children, and it never computes a figure:
deterministic code supplies every number, and the model only writes prose
around it.

Setup is in `docs/LOCAL-SETUP.md`. `manage.py ai_check`, or **Test connection**
in Settings, reports whether the runtime is answering.

**Care-gap alerts are unaffected.** They were always deterministic rules over
dates and case state, and never involved a model.
```

Then update the summary table row at `README.md:19` from
`| AI runtime | Ollama, loopback-only | **Removed** — see below |` to
`| AI runtime | Ollama, loopback-only | Ollama, loopback-only — off by default |`.

- [ ] **Step 2: Add a local setup section**

In `docs/LOCAL-SETUP.md`, document: install Ollama, `ollama pull
qwen2.5:3b-instruct`, set `OLLAMA_KEEP_ALIVE=-1`, `OLLAMA_NUM_PARALLEL=1`,
`OLLAMA_MAX_LOADED_MODELS=1`, then switch the assistant on in Settings and run
`manage.py ai_check` to confirm. Record the measured expectation: ~5 s for a
short draft, ~40 s for a brief, and that briefs are prefetched so the button is
normally instant.

- [ ] **Step 3: Fix the test command in CLAUDE.md**

CLAUDE.md's "Before bundling anything" section says
`cd backend && .venv/bin/python manage.py test`. This machine's venv is
`.venv/Scripts/python.exe`. Correct it, and update the test count from 379.

- [ ] **Step 4: Add an assistant section to CLAUDE.md**

Record the facts that cost time to rediscover: the app is `assistant` and **must
never be renamed to `ai`** (stale `django_migrations` rows); prompts are
static-prefix-first; no per-request model options; `qwen3.5:2b` does not load on
8 GB.

- [ ] **Step 5: Run the full suite one last time**

Run: `cd backend && .venv/Scripts/python.exe manage.py test`
Then: `cd frontend && npm run lint && npm run build`
Expected: both green.

- [ ] **Step 6: Commit**

```bash
git add README.md CLAUDE.md docs/LOCAL-SETUP.md
git commit -m "Say that the assistant is back, and what it will and will not do"
```

---

## Notes for the executor

- **Never rename the app to `ai`.** See Global Constraints.
- **Every new hook goes above every early return** in a React component.
  `ChildProgressReport.jsx` has already crashed in production this exact way.
- **Every frontend AI call must degrade silently or with a toast.** A 503 is a
  normal state of this system, not an error the user caused.
- **No test may require a running Ollama.** Patch `services.OllamaClient.generate`.
- Run the whole backend suite, not just `assistant`, before each commit that
  touches shared files (`config/settings.py`, `config/urls.py`,
  `clinical/serializers.py`).
