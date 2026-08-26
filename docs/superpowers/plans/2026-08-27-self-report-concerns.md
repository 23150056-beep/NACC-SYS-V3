# Self-Report Concerns Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Flag distress in a child's own self-report words so it is noticed, without ever reading or judging the psychologist's notes.

**Architecture:** Two independent detectors run over the (question, answer) pair. A deterministic lexicon runs synchronously on submission and is the floor; the local model runs in a background thread and can only add flags, never clear them. Flags persist as rows, so `compute_alerts()` reads them cheaply on page load and the existing Monitoring screen and chatbot surface them with no new permission surface.

**Tech Stack:** Django 5.1, DRF, SQLite locally, React 18 + Vite, Ollama `qwen2.5:3b-instruct` via the existing `assistant` client seam.

**Spec:** `docs/superpowers/specs/2026-08-27-self-report-concerns-design.md`

## Global Constraints

- **Commit authorship:** every commit is authored **and** committed by `Reynold <jreynoldcanedo@gmail.com>`. No Claude attribution, no `Co-Authored-By`, no model name in any commit message, PR body, or code comment.
- **Python:** always `backend/.venv/Scripts/python.exe`, never `.venv/bin/python`.
- **Never rename the `assistant` app to `ai`** — stale `django_migrations` rows would make a recreated `ai.0001_initial` be skipped as already applied.
- **Prompts are assembled static-prefix-first**: a fixed module-constant instruction block, then the dynamic facts. Never the other order.
- **No per-request model options.** `generate()` sends `model`, `prompt`, `stream`, `system` only.
- **Fixtures use strings the live database actually contains.** Never invent fixture text that agrees with the assumption being tested.
- **No recall or precision figure may be quoted from demo data** — 366 answers are only 17 distinct strings.
- **Nothing leaves the machine.** Local Ollama only.
- **The psychologist's notes are never read** by any code in this feature.
- Before any commit: `cd backend && .venv/Scripts/python.exe manage.py test` and `cd frontend && npm run lint && npm run build`.

---

## File Structure

| File | Responsibility |
|---|---|
| `backend/clinical/self_report_detection.py` | **Create.** The lexicon (data) and `detect_concerns()` (logic). Pure functions, no Django models. |
| `backend/clinical/models.py` | **Modify.** Add `SelfReportFlag`. |
| `backend/clinical/migrations/000X_selfreportflag.py` | **Create.** Generated. |
| `backend/clinical/views.py:475-497` | **Modify.** `PublicOpinionnaireView.submit` runs the lexicon synchronously and starts the model thread. |
| `backend/clinical/self_report_model_check.py` | **Create.** The background model detector and its thread starter. Kept out of `views.py` so the view stays readable. |
| `backend/assistant/prompts.py` | **Modify.** Add `SELF_REPORT_SYSTEM` and `SELF_REPORT_INSTRUCTIONS`, plus `build_self_report_prompt()`. |
| `backend/clinical/care_gaps.py` | **Modify.** New alert type reading persisted flags. |
| `backend/clinical/serializers.py` | **Modify.** `SelfReportFlagSerializer`. |
| `backend/clinical/views.py` | **Modify.** `SelfReportFlagViewSet` (list + acknowledge). |
| `backend/clinical/urls.py` | **Modify.** Register the route. |
| `backend/clinical/reports_views.py` | **Modify.** Include flags in the child report payload, exempt from carry-history. |
| `backend/clinical/management/commands/scan_self_reports.py` | **Create.** Idempotent backfill. |
| `backend/assistant/management/commands/ai_eval.py` | **Modify.** `--feature self_report`. |
| `frontend/src/pages/ChildProgressReport.jsx` | **Modify.** Flagged answers expanded beside remarks; the carry-history note. |
| `frontend/src/api/clinical.js` (or existing API module) | **Modify.** Acknowledge call. |

---

### Task 1: The lexicon and the detector

Pure functions over text. No Django, no database, no model. This is the floor the whole feature stands on, so it is built and proved first.

**Files:**
- Create: `backend/clinical/self_report_detection.py`
- Test: `backend/clinical/tests/test_self_report_detection.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `detect_concerns(question: str, answer: str) -> list[dict]` where each dict is `{"phrase": str, "rule": str}`. `rule` is `"phrase"` or `"isolation"`.
  - `DISTRESS_PHRASES: dict[str, tuple[str, ...]]` keyed by language `"tl" | "ilo" | "en"`.
  - `ISOLATION_ANSWERS: tuple[str, ...]`
  - `ISOLATION_QUESTION_HINTS: tuple[str, ...]`
  - `LEXICON_REVIEWED: dict[str, bool]` — `{"tl": True, "ilo": False, "en": True}`.

- [ ] **Step 1: Write the failing tests**

Create `backend/clinical/tests/test_self_report_detection.py`. Every string below is copied from the live database — do not paraphrase them.

```python
"""Detector tests over the (question, answer) pair.

Every fixture string is one that appears in the live local database. On
26 Aug a search feature shipped green because its test invented text that
agreed with the assumption; the strings here are copied, not imagined.
"""
from django.test import SimpleTestCase

from clinical.self_report_detection import detect_concerns

FEELING = "How are you feeling this week?"
WORRY = "Is there anything worrying you?"
ISOLATION = "Who do you talk to when you are sad?"


class DistressTest(SimpleTestCase):
    def test_flags_crying_and_wanting_to_go_home(self):
        hits = detect_concerns(FEELING, "Gusto ko na umuwi. Lagi akong umiiyak sa gabi.")
        self.assertTrue(hits)

    def test_flags_being_unable_to_speak_and_somatic_pain(self):
        hits = detect_concerns(WORRY, "Hindi ko masabi kasi baka magalit sila. Masakit ang dibdib ko.")
        self.assertTrue(hits)

    def test_flags_feeling_alone_and_wanting_to_sleep(self):
        hits = detect_concerns(FEELING, "I feel alone. Ayaw ko na dito, gusto ko na lang matulog.")
        self.assertTrue(hits)

    def test_flags_nobody_listening(self):
        hits = detect_concerns(WORRY, "Nobody listens to me here. Wala akong makausap.")
        self.assertTrue(hits)

    def test_reports_which_phrase_fired(self):
        hits = detect_concerns(FEELING, "Lagi akong umiiyak sa gabi.")
        self.assertIn("umiiyak", [h["phrase"] for h in hits])


class IlocanoTest(SimpleTestCase):
    """The children are in Ilocos. A Tagalog-only list passes both of these."""

    def test_flags_mabutbuteng(self):
        hits = detect_concerns(FEELING, "Mabutbuteng. I am scared but I don't tell them.")
        self.assertTrue(hits)

    def test_flags_adda_problema(self):
        hits = detect_concerns(WORRY, "Adda met bassit nga problema but I don't want to say.")
        self.assertTrue(hits)

    def test_does_not_flag_the_calm_ilocano_line(self):
        # "Naimbag met" — it is good. This is the Ilocano control.
        hits = detect_concerns(FEELING, "Naimbag met. I can sleep at night now.")
        self.assertEqual([], hits)


class CalmTest(SimpleTestCase):
    """Without these a lexicon can score perfectly by flagging everything."""

    def test_does_not_flag_feeling_safe(self):
        self.assertEqual([], detect_concerns(FEELING, "I feel safe. Ang bait ng nag-aalaga sa akin."))

    def test_does_not_flag_liking_the_food(self):
        self.assertEqual([], detect_concerns(FEELING, "Okay lang. I like the food and my bed."))

    def test_does_not_flag_having_a_friend(self):
        self.assertEqual([], detect_concerns(FEELING, "Masaya naman ako dito. May kaibigan na ako."))

    def test_does_not_flag_missing_a_sibling_with_kind_carers(self):
        self.assertEqual([], detect_concerns(FEELING, "I miss my sister. But the people here are kind."))


class IsolationQuestionTest(SimpleTestCase):
    """62 of 122 reports answer the isolation question with a word meaning
    'no one'. Those words are unremarkable anywhere else, which is why
    detection reads the question and not just the answer."""

    def test_nobody_flags_against_the_isolation_question(self):
        hits = detect_concerns(ISOLATION, "Nobody")
        self.assertEqual("isolation", hits[0]["rule"])

    def test_ako_lang_flags_against_the_isolation_question(self):
        self.assertTrue(detect_concerns(ISOLATION, "Ako lang"))

    def test_nobody_does_not_flag_against_another_question(self):
        self.assertEqual([], detect_concerns(FEELING, "Nobody"))

    def test_naming_a_person_does_not_flag(self):
        self.assertEqual([], detect_concerns(ISOLATION, "My sister"))
        self.assertEqual([], detect_concerns(ISOLATION, "Ate sa bahay"))

    def test_an_unknown_question_falls_back_to_phrases(self):
        # A template can be edited. An unrecognised question must still detect
        # phrases rather than failing shut.
        hits = detect_concerns("Some new question?", "Lagi akong umiiyak sa gabi.")
        self.assertTrue(hits)


class RobustnessTest(SimpleTestCase):
    def test_is_case_insensitive(self):
        self.assertTrue(detect_concerns(ISOLATION, "NOBODY"))

    def test_handles_blank_and_none(self):
        self.assertEqual([], detect_concerns(FEELING, ""))
        self.assertEqual([], detect_concerns(FEELING, None))
        self.assertEqual([], detect_concerns(None, "Lagi akong umiiyak"))

    def test_does_not_match_a_phrase_inside_an_unrelated_word(self):
        # "wala" must not fire inside "walang-hanggan" style compounds picked
        # up mid-word; matching is on word boundaries.
        self.assertEqual([], detect_concerns(FEELING, "Walang problema, masaya ako."))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && ./.venv/Scripts/python.exe manage.py test clinical.tests.test_self_report_detection`
Expected: FAIL — `ModuleNotFoundError: No module named 'clinical.self_report_detection'`

- [ ] **Step 3: Write the detector**

Create `backend/clinical/self_report_detection.py`:

```python
"""Distress detection over a child's self-report.

Deterministic, sub-millisecond, no runtime dependency. This is the floor: if
Ollama is down, swapped, or drifting, flagging continues unchanged. A
child-safety signal must not depend on a 3B model running on a laptop.

Detection reads the (question, answer) PAIR, never the answer alone. In the
live data, 62 of 122 reports answer "Who do you talk to when you are sad?"
with "Nobody" or "Ako lang" — the largest signal present, and invisible to
anything reading answer text on its own.

The list is assumed incomplete. It is supplemented by the model detector, and
unflagged reports stay visible on the child's page, so a miss is unhighlighted
rather than hidden.
"""
import re

# Phrases in the three languages the children actually write. Adding one is a
# one-line change, which is the point — the list is tuned from real use via
# the `phrase` recorded on every flag.
DISTRESS_PHRASES = {
    "tl": (
        "umiiyak", "iyak", "gusto ko na umuwi", "gusto ko umuwi",
        "hindi ko masabi", "ayaw ko na", "ayaw ko dito", "ayaw ko na dito",
        "takot", "natatakot", "masakit", "nasasaktan", "walang kausap",
        "wala akong makausap", "wala akong kaibigan", "nag-iisa",
        "malungkot", "lungkot", "gusto ko na lang matulog", "binubugbog",
        "sinasaktan", "galit sila", "baka magalit",
    ),
    # NOT REVIEWED BY AN ILOCANO SPEAKER — see LEXICON_REVIEWED below.
    "ilo": (
        "mabutbuteng", "buteng", "agsangsangit", "sangit",
        "adda problema", "adda met bassit nga problema", "adda parikut",
        "kayat ko nga agawid", "maladingit", "saan ko kayat",
    ),
    "en": (
        "i feel alone", "feel alone", "nobody listens", "no one listens",
        "i am scared", "i'm scared", "scared", "afraid",
        "cannot sleep", "can't sleep", "cry", "crying",
        "want to go home", "hurts", "hurting", "hit me", "nobody helps",
    ),
}

# Which language lists have been read by a speaker of that language. An
# invented entry is worse than a missing one because it looks authoritative.
LEXICON_REVIEWED = {"tl": True, "ilo": False, "en": True}

# The isolation rule. "Nobody" is an unremarkable word; against this question
# it is the single largest distress signal in the dataset.
ISOLATION_QUESTION_HINTS = ("talk to when you are sad", "talk to when sad",
                            "kausap", "kinakausap")
ISOLATION_ANSWERS = ("nobody", "no one", "none", "ako lang", "wala",
                     "walang", "awan", "wala akong makausap", "sarili ko",
                     "myself", "just me", "no body")


def _norm(text):
    return " ".join(str(text or "").lower().split())


def _contains_word(haystack, needle):
    """Word-boundary match, so 'wala' does not fire inside 'walang problema'."""
    return re.search(rf"(?<!\w){re.escape(needle)}(?!\w)", haystack) is not None


def _is_isolation_question(question):
    q = _norm(question)
    return any(h in q for h in ISOLATION_QUESTION_HINTS)


def detect_concerns(question, answer):
    """Return the list of matches for one (question, answer) pair.

    Each match is {"phrase": <what fired>, "rule": "phrase" | "isolation"}.
    An empty list means nothing fired — which is never a claim that the child
    is fine, only that this list did not recognise anything.
    """
    text = _norm(answer)
    if not text:
        return []

    hits = []

    if _is_isolation_question(question):
        for candidate in ISOLATION_ANSWERS:
            if text == candidate or _contains_word(text, candidate):
                hits.append({"phrase": candidate, "rule": "isolation"})
                break

    for phrases in DISTRESS_PHRASES.values():
        for phrase in phrases:
            if _contains_word(text, phrase):
                hits.append({"phrase": phrase, "rule": "phrase"})

    # De-duplicate while keeping the first occurrence order.
    seen, unique = set(), []
    for h in hits:
        if h["phrase"] not in seen:
            seen.add(h["phrase"])
            unique.append(h)
    return unique
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && ./.venv/Scripts/python.exe manage.py test clinical.tests.test_self_report_detection`
Expected: PASS.

If `test_does_not_match_a_phrase_inside_an_unrelated_word` fails, the fix is the word-boundary regex, **not** deleting the test. If a calm-control test fails, a phrase in the list is too broad — narrow it. Never widen a control test to make a list pass.

- [ ] **Step 5: Verify against every string in the live database**

Run this and read the output. It is not an automated assertion — it is the human check that the list behaves on real data:

```bash
cd backend && ./.venv/Scripts/python.exe manage.py shell -c "
from clinical.models import OpinionnaireInvite as OI
from clinical.self_report_detection import detect_concerns
import collections
seen = collections.OrderedDict()
for i in OI.objects.filter(status='submitted'):
    for q, a in (i.answers or {}).items():
        if isinstance(a, str) and a.strip():
            seen.setdefault((q, a.strip()), 0)
            seen[(q, a.strip())] += 1
for (q, a), n in sorted(seen.items(), key=lambda kv: -kv[1]):
    hits = detect_concerns(q, a)
    mark = 'FLAG' if hits else '  . '
    why = ','.join(h['phrase'] for h in hits)
    print(f'{mark} {n:4}  {a[:62]:64} {why}')
"
```

Expected: the four calm strings show `.`, the distress and Ilocano strings show `FLAG`, and "Nobody"/"Ako lang" show `FLAG` only against the isolation question.

**Do not record a recall percentage from this.** 366 answers are 17 distinct strings; a number from it measures the seeder.

- [ ] **Step 6: Commit**

```bash
git add backend/clinical/self_report_detection.py backend/clinical/tests/test_self_report_detection.py
git -c user.email=jreynoldcanedo@gmail.com commit --author="Reynold <jreynoldcanedo@gmail.com>" -m "Detect distress in a child's self-report by phrase and by question

Reads the (question, answer) pair, never the answer alone: 62 of 122 reports
answer the isolation question with 'Nobody' or 'Ako lang', which is the
largest signal in the data and invisible to anything reading answers on their
own.

Covers Tagalog, Ilocano and English. The Ilocano entries are marked unreviewed
in LEXICON_REVIEWED — they were seeded from phrases observed in the database
and need a speaker to read them before launch, because an invented entry looks
authoritative.

Tests include the calm controls. Without them a list can score perfectly by
flagging everything."
```

---

### Task 2: Persist a flag

**Files:**
- Modify: `backend/clinical/models.py` (append after `ProblemEntry`)
- Create: `backend/clinical/migrations/000X_selfreportflag.py` (generated)
- Test: `backend/clinical/tests/test_self_report_flags.py`

**Interfaces:**
- Consumes: `detect_concerns()` from Task 1.
- Produces: `clinical.models.SelfReportFlag` with fields `invite`, `child`, `question`, `answer`, `source` (`"lexicon" | "model"`), `matched`, `created_at`, `reviewed_by`, `reviewed_at`, `review_note`; constants `SelfReportFlag.LEXICON`, `SelfReportFlag.MODEL`; property `is_reviewed`.

- [ ] **Step 1: Write the failing test**

Create `backend/clinical/tests/test_self_report_flags.py`:

```python
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from accounts.models import Role
from children.models import Child
from clinical.models import AgencyFormTemplate, OpinionnaireInvite, SelfReportFlag

User = get_user_model()


class SelfReportFlagModelTest(TestCase):
    def setUp(self):
        role = Role.objects.create(role_name=Role.PSYCHOLOGIST)
        self.psy = User.objects.create_user(
            email="p@racco1.gov.ph", username="p", password="pass1234", role=role)
        self.child = Child.objects.create(
            fullname="Maria Santos", assigned_psychologist=self.psy)
        self.template = AgencyFormTemplate.objects.create(
            title="Self-report", fields=[{"label": "How are you feeling this week?"}])
        self.invite = OpinionnaireInvite.objects.create(
            child=self.child, template=self.template,
            expires_at=timezone.now() + timedelta(days=7))

    def _flag(self, **kw):
        return SelfReportFlag.objects.create(
            invite=self.invite, child=self.child,
            question="How are you feeling this week?",
            answer="Lagi akong umiiyak sa gabi.",
            source=SelfReportFlag.LEXICON, matched="umiiyak", **kw)

    def test_stores_a_snapshot_of_the_question_and_answer(self):
        flag = self._flag()
        # Editing the template later must not rewrite history.
        self.template.fields = [{"label": "Something else entirely"}]
        self.template.save()
        flag.refresh_from_db()
        self.assertEqual("How are you feeling this week?", flag.question)
        self.assertEqual("Lagi akong umiiyak sa gabi.", flag.answer)

    def test_starts_unreviewed(self):
        self.assertFalse(self._flag().is_reviewed)

    def test_becomes_reviewed_when_acknowledged(self):
        flag = self._flag()
        flag.reviewed_by = self.psy
        flag.reviewed_at = timezone.now()
        flag.save()
        self.assertTrue(flag.is_reviewed)

    def test_records_which_detector_fired(self):
        self.assertEqual(SelfReportFlag.LEXICON, self._flag().source)

    def test_survives_the_reviewer_being_deleted(self):
        flag = self._flag(reviewed_by=self.psy, reviewed_at=timezone.now())
        self.psy.delete()
        flag.refresh_from_db()
        self.assertIsNone(flag.reviewed_by)
        self.assertIsNotNone(flag.reviewed_at)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd backend && ./.venv/Scripts/python.exe manage.py test clinical.tests.test_self_report_flags`
Expected: FAIL — `ImportError: cannot import name 'SelfReportFlag'`

- [ ] **Step 3: Add the model**

Append to `backend/clinical/models.py`:

```python
class SelfReportFlag(models.Model):
    """A child's own words, flagged as worth reading.

    It asserts exactly one thing: this child said something worth reading. It
    is never a claim that anyone missed anything, that a case is mishandled, or
    that the child is at risk — those are conclusions for a human who has read
    the record, and a system that matched a phrase has not read the record.

    The question and answer are snapshotted rather than followed by reference,
    so editing a form template later cannot rewrite what a child was asked.
    """
    LEXICON = "lexicon"
    MODEL = "model"
    SOURCE_CHOICES = [(LEXICON, "Phrase list"), (MODEL, "Local model")]

    invite = models.ForeignKey(
        OpinionnaireInvite, on_delete=models.CASCADE, related_name="flags")
    # Denormalised and indexed: every query here is "flags for these children".
    child = models.ForeignKey(
        Child, on_delete=models.CASCADE, related_name="self_report_flags")
    question = models.TextField()
    answer = models.TextField()
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    matched = models.CharField(
        max_length=255, blank=True,
        help_text="The phrase that fired, or the model's one-line reason")
    created_at = models.DateTimeField(auto_now_add=True)

    # Acknowledgement. Without it flags accumulate, the list stops being read,
    # and the feature becomes decoration.
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        blank=True, related_name="self_report_flags_reviewed")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)

    class Meta:
        db_table = "tbl_self_report_flag"
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["child", "reviewed_at"])]
        # One row per (invite, question, source) — re-scanning is idempotent.
        constraints = [
            models.UniqueConstraint(
                fields=["invite", "question", "source"],
                name="uniq_self_report_flag_per_question_source"),
        ]

    @property
    def is_reviewed(self):
        return self.reviewed_at is not None
```

- [ ] **Step 4: Generate and apply the migration**

```bash
cd backend
./.venv/Scripts/python.exe manage.py makemigrations clinical
./.venv/Scripts/python.exe manage.py migrate
```

Expected: one new migration creating `tbl_self_report_flag`.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && ./.venv/Scripts/python.exe manage.py test clinical.tests.test_self_report_flags`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/clinical/models.py backend/clinical/migrations/ backend/clinical/tests/test_self_report_flags.py
git -c user.email=jreynoldcanedo@gmail.com commit --author="Reynold <jreynoldcanedo@gmail.com>" -m "Persist a self-report flag with its question and answer

Snapshots the question and answer rather than following the template by
reference, so editing a form later cannot rewrite what a child was asked.

Carries acknowledgement from the start. Without it flags accumulate forever,
the list stops being read, and the feature becomes decoration.

A unique constraint on (invite, question, source) makes re-scanning idempotent."
```

---

### Task 3: Flag on submission, synchronously

The lexicon runs inside the request. A child submitting from her own device must never wait on a model call.

**Files:**
- Modify: `backend/clinical/views.py` — `PublicOpinionnaireView.submit`
- Test: `backend/clinical/tests/test_self_report_submit.py`

**Interfaces:**
- Consumes: `detect_concerns()` (Task 1), `SelfReportFlag` (Task 2).
- Produces: flags created as a side effect of `POST /api/opinionnaire/<token>/submit/`.

- [ ] **Step 1: Write the failing test**

Create `backend/clinical/tests/test_self_report_submit.py`:

```python
"""The public survey endpoint creates flags as a side effect.

This endpoint is unauthenticated and token-gated — it is reached from a
child's own device. It must stay fast and must never fail because of flagging.
"""
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import Role
from children.models import Child
from clinical.models import AgencyFormTemplate, OpinionnaireInvite, SelfReportFlag

User = get_user_model()

FEELING = "How are you feeling this week?"
ISOLATION = "Who do you talk to when you are sad?"


class SubmitFlaggingTest(APITestCase):
    def setUp(self):
        role = Role.objects.create(role_name=Role.PSYCHOLOGIST)
        psy = User.objects.create_user(
            email="p@racco1.gov.ph", username="p", password="pass1234", role=role)
        self.child = Child.objects.create(fullname="Maria Santos",
                                          assigned_psychologist=psy)
        self.template = AgencyFormTemplate.objects.create(
            title="Self-report",
            fields=[{"label": FEELING}, {"label": ISOLATION}])
        self.invite = OpinionnaireInvite.objects.create(
            child=self.child, template=self.template,
            expires_at=timezone.now() + timedelta(days=7))
        self.url = f"/api/opinionnaire/{self.invite.token}/submit/"

    def _submit(self, answers):
        # The model detector is patched out everywhere in this file: it runs in
        # a thread and this task is only about the synchronous path.
        with patch("clinical.self_report_model_check.start_model_check"):
            return self.client.post(self.url, {"answers": answers}, format="json")

    def test_a_distress_answer_creates_a_flag(self):
        res = self._submit({FEELING: "Lagi akong umiiyak sa gabi."})
        self.assertEqual(200, res.status_code)
        flag = SelfReportFlag.objects.get()
        self.assertEqual(self.child, flag.child)
        self.assertEqual(SelfReportFlag.LEXICON, flag.source)
        self.assertEqual("umiiyak", flag.matched)

    def test_the_flag_snapshots_the_question_and_answer(self):
        self._submit({FEELING: "Lagi akong umiiyak sa gabi."})
        flag = SelfReportFlag.objects.get()
        self.assertEqual(FEELING, flag.question)
        self.assertEqual("Lagi akong umiiyak sa gabi.", flag.answer)

    def test_a_calm_answer_creates_no_flag(self):
        self._submit({FEELING: "I feel safe. Ang bait ng nag-aalaga sa akin."})
        self.assertEqual(0, SelfReportFlag.objects.count())

    def test_nobody_flags_only_against_the_isolation_question(self):
        self._submit({FEELING: "Nobody", ISOLATION: "Nobody"})
        flags = SelfReportFlag.objects.all()
        self.assertEqual(1, flags.count())
        self.assertEqual(ISOLATION, flags[0].question)

    def test_the_submission_still_succeeds_when_flagging_raises(self):
        # Flagging must never cost a child her submission.
        with patch("clinical.views.detect_concerns", side_effect=RuntimeError("boom")):
            with patch("clinical.self_report_model_check.start_model_check"):
                res = self.client.post(
                    self.url, {"answers": {FEELING: "Lagi akong umiiyak"}}, format="json")
        self.assertEqual(200, res.status_code)
        self.invite.refresh_from_db()
        self.assertEqual(OpinionnaireInvite.SUBMITTED, self.invite.status)

    def test_the_answers_are_still_saved(self):
        self._submit({FEELING: "Lagi akong umiiyak sa gabi."})
        self.invite.refresh_from_db()
        self.assertEqual("Lagi akong umiiyak sa gabi.", self.invite.answers[FEELING])
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd backend && ./.venv/Scripts/python.exe manage.py test clinical.tests.test_self_report_submit`
Expected: FAIL — `ModuleNotFoundError: No module named 'clinical.self_report_model_check'` (created in Task 4) or `SelfReportFlag.DoesNotExist`.

To keep this task self-contained, create the stub module now — Task 4 fills it in:

```python
# backend/clinical/self_report_model_check.py
"""The model detector. Filled in by Task 4."""


def start_model_check(invite_id):
    """Start the background model pass. No-op until Task 4."""
    return None
```

Re-run: the failure should now be about the missing flag.

- [ ] **Step 3: Wire it into the view**

In `backend/clinical/views.py`, add the imports near the other clinical imports:

```python
from clinical.self_report_detection import detect_concerns
from clinical.self_report_model_check import start_model_check
```

Replace the tail of `PublicOpinionnaireView.submit` (currently ending at `return Response({"status": "submitted"})`) with:

```python
        invite.answers = cleaned
        invite.status = OpinionnaireInvite.SUBMITTED
        invite.submitted_at = timezone.now()
        invite.save(update_fields=["answers", "status", "submitted_at"])

        # The lexicon runs here: deterministic, sub-millisecond, and the floor
        # that holds when the model is unavailable. It must never cost a child
        # her submission, so nothing it does can fail the request.
        try:
            _flag_self_report(invite, cleaned)
        except Exception:                      # noqa: BLE001 - see above
            logger.exception("Self-report flagging failed for invite %s", invite.pk)

        # The model runs out of band. A child on her own device does not wait.
        try:
            start_model_check(invite.pk)
        except Exception:                      # noqa: BLE001
            logger.exception("Self-report model check could not start")

        return Response({"status": "submitted"})
```

Add the helper above the class:

```python
def _flag_self_report(invite, answers):
    """Create a lexicon flag for every (question, answer) pair that fires."""
    for question, answer in (answers or {}).items():
        for hit in detect_concerns(question, answer):
            SelfReportFlag.objects.get_or_create(
                invite=invite, question=question,
                source=SelfReportFlag.LEXICON,
                defaults={"child": invite.child, "answer": answer,
                          "matched": hit["phrase"]})
            break      # one flag per question; `matched` names the first hit
```

Ensure `logger` exists at module scope (`logger = logging.getLogger(__name__)`) and that `SelfReportFlag` is in the models import list at the top of `views.py`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && ./.venv/Scripts/python.exe manage.py test clinical.tests.test_self_report_submit`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/clinical/views.py backend/clinical/self_report_model_check.py backend/clinical/tests/test_self_report_submit.py
git -c user.email=jreynoldcanedo@gmail.com commit --author="Reynold <jreynoldcanedo@gmail.com>" -m "Flag a self-report the moment it is submitted

The lexicon runs inside the request because it is sub-millisecond and because
it is the floor that holds when the model is unavailable. The model pass is
started out of band: the survey endpoint is reached from a child's own device
and she must never wait on a model call.

Flagging cannot fail a submission. Both calls are wrapped and logged, because
losing a child's answers to a detector bug would be far worse than missing a
flag."
```

---

### Task 4: The model as a second detector

**Files:**
- Modify: `backend/assistant/prompts.py`
- Rewrite: `backend/clinical/self_report_model_check.py`
- Test: `backend/clinical/tests/test_self_report_model_check.py`

**Interfaces:**
- Consumes: `SelfReportFlag` (Task 2); `assistant.services.get_ai_client`, `services_lock`, `AIUnavailable`; `assistant.models.AssistantJob`.
- Produces: `start_model_check(invite_id)`, `run_model_check(invite_id)` (synchronous, used by tests and by the backfill command in Task 5), `assistant.prompts.build_self_report_prompt(question, answer)`, `assistant.prompts.SELF_REPORT_SYSTEM`.

- [ ] **Step 1: Add the prompt, static-prefix-first**

Append to `backend/assistant/prompts.py`:

```python
SELF_REPORT_SYSTEM = (
    "You read short self-reports written by children in a child protection "
    "agency in the Philippines. They write in English, Tagalog, Ilocano, or a "
    "mix. You judge only whether the child expresses distress."
)

SELF_REPORT_INSTRUCTIONS = (
    "Does this child's answer express distress, fear, sadness, pain, or being "
    "alone?\n"
    "Answer with one word, YES or NO, then a dash and at most eight words "
    "saying why.\n"
    "Judge only the answer given. Do not infer anything not written.\n\n"
    "EXCHANGE:\n"
)


def build_self_report_prompt(question, answer):
    # Static block first, dynamic facts last — keeps the prefix cache warm.
    return SELF_REPORT_INSTRUCTIONS + f"Q: {question}\nA: {answer}"
```

- [ ] **Step 2: Write the failing test**

Create `backend/clinical/tests/test_self_report_model_check.py`:

```python
"""The model is a second detector. It can only add flags, never clear one."""
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from accounts.models import Role
from assistant.models import AssistantSetting
from assistant.services import AIUnavailable
from children.models import Child
from clinical.models import AgencyFormTemplate, OpinionnaireInvite, SelfReportFlag
from clinical.self_report_model_check import run_model_check

User = get_user_model()
FEELING = "How are you feeling this week?"


class ModelCheckTest(TestCase):
    def setUp(self):
        role = Role.objects.create(role_name=Role.PSYCHOLOGIST)
        psy = User.objects.create_user(
            email="p@racco1.gov.ph", username="p", password="pass1234", role=role)
        self.child = Child.objects.create(fullname="Maria Santos",
                                          assigned_psychologist=psy)
        template = AgencyFormTemplate.objects.create(
            title="Self-report", fields=[{"label": FEELING}])
        self.invite = OpinionnaireInvite.objects.create(
            child=self.child, template=template,
            status=OpinionnaireInvite.SUBMITTED,
            submitted_at=timezone.now(),
            answers={FEELING: "Kasla nagbaliw ti riknak."},
            expires_at=timezone.now() + timedelta(days=7))
        cfg = AssistantSetting.load()
        cfg.enabled = True
        cfg.save()

    def _run(self, reply):
        with patch("assistant.services.OllamaClient.generate", return_value=reply):
            run_model_check(self.invite.pk)

    def test_a_yes_creates_a_model_flag(self):
        self._run("YES - the child sounds overwhelmed")
        flag = SelfReportFlag.objects.get()
        self.assertEqual(SelfReportFlag.MODEL, flag.source)
        self.assertIn("overwhelmed", flag.matched)

    def test_a_no_creates_nothing(self):
        self._run("NO - the child sounds settled")
        self.assertEqual(0, SelfReportFlag.objects.count())

    def test_an_unparseable_reply_creates_nothing(self):
        # Never flag on a reply we did not understand.
        self._run("I think perhaps maybe")
        self.assertEqual(0, SelfReportFlag.objects.count())

    def test_it_never_removes_a_lexicon_flag(self):
        SelfReportFlag.objects.create(
            invite=self.invite, child=self.child, question=FEELING,
            answer="Kasla nagbaliw ti riknak.",
            source=SelfReportFlag.LEXICON, matched="riknak")
        self._run("NO - the child sounds settled")
        self.assertEqual(1, SelfReportFlag.objects.count())
        self.assertEqual(SelfReportFlag.LEXICON, SelfReportFlag.objects.get().source)

    def test_the_runtime_being_down_is_not_an_error(self):
        with patch("assistant.services.OllamaClient.generate",
                   side_effect=AIUnavailable("refused")):
            run_model_check(self.invite.pk)          # must not raise
        self.assertEqual(0, SelfReportFlag.objects.count())

    def test_it_does_nothing_when_the_assistant_is_off(self):
        cfg = AssistantSetting.load()
        cfg.enabled = False
        cfg.save()
        with patch("assistant.services.OllamaClient.generate") as gen:
            run_model_check(self.invite.pk)
        gen.assert_not_called()

    def test_running_twice_does_not_duplicate(self):
        self._run("YES - sounds distressed")
        self._run("YES - sounds distressed")
        self.assertEqual(1, SelfReportFlag.objects.count())
```

- [ ] **Step 3: Run it to verify it fails**

Run: `cd backend && ./.venv/Scripts/python.exe manage.py test clinical.tests.test_self_report_model_check`
Expected: FAIL — `ImportError: cannot import name 'run_model_check'`

- [ ] **Step 4: Write the model detector**

Replace `backend/clinical/self_report_model_check.py` entirely:

```python
"""The second detector: the local model reads the same (question, answer) pair.

It exists to catch phrasing nobody thought to list — precisely where the
Ilocano entries will be weakest. It can only ADD a flag. It is never consulted
about removing one, and its unavailability degrades silently to the lexicon.

Its accuracy on Ilocano is unmeasured. qwen2.5:3b was measured on Taglish, not
on a low-resource Philippine language, and there is no reason to assume the
result transfers. That is why it supplements the lexicon rather than replacing
it.
"""
import logging
import re
import threading
import time

from django.db import connection

logger = logging.getLogger(__name__)

_YES = re.compile(r"^\s*(yes|oo)\b", re.IGNORECASE)


def _parse(reply):
    """Return the reason if the reply is a YES, else None.

    An unparseable reply yields None. Never flag on something we did not
    understand — a flag nobody can explain is worse than no flag.
    """
    text = " ".join(str(reply or "").split())
    if not _YES.match(text):
        return None
    reason = re.sub(r"^\s*(yes|oo)\b[\s\-–—:,.]*", "", text, flags=re.IGNORECASE)
    return (reason or "flagged by the local model")[:255]


def run_model_check(invite_id):
    """Synchronous. Safe to call from a thread, a command, or a test."""
    from assistant import prompts
    from assistant.models import AssistantJob, AssistantSetting
    from assistant.services import AIUnavailable, get_ai_client, services_lock
    from clinical.models import OpinionnaireInvite, SelfReportFlag

    if not AssistantSetting.load().enabled:
        return

    invite = (OpinionnaireInvite.objects
              .select_related("child").filter(pk=invite_id).first())
    if invite is None:
        return

    client = get_ai_client()
    for question, answer in (invite.answers or {}).items():
        if not str(answer or "").strip():
            continue
        if SelfReportFlag.objects.filter(
                invite=invite, question=question,
                source=SelfReportFlag.MODEL).exists():
            continue

        started = time.monotonic()
        try:
            with services_lock():
                reply = client.generate(
                    prompts.build_self_report_prompt(question, answer),
                    system=prompts.SELF_REPORT_SYSTEM)
        except AIUnavailable as exc:
            # Expected, not exceptional. The lexicon has already run.
            AssistantJob.objects.create(
                job_type="self_report", input_ref=f"invite:{invite.pk}",
                ok=False, error=str(exc)[:255],
                model_used=getattr(client, "model", ""),
                latency_ms=int((time.monotonic() - started) * 1000))
            return

        reason = _parse(reply)
        AssistantJob.objects.create(
            job_type="self_report", input_ref=f"invite:{invite.pk}",
            output_text=str(reply)[:2000], model_used=client.model, ok=True,
            latency_ms=int((time.monotonic() - started) * 1000))

        if reason:
            SelfReportFlag.objects.get_or_create(
                invite=invite, question=question, source=SelfReportFlag.MODEL,
                defaults={"child": invite.child, "answer": answer,
                          "matched": reason})


def start_model_check(invite_id):
    """Fire and forget. The caller is a child's device; it does not wait."""
    def worker():
        try:
            run_model_check(invite_id)
        except Exception:                       # noqa: BLE001
            logger.exception("Self-report model check failed for %s", invite_id)
        finally:
            # A thread owns its own connection and must hand it back.
            connection.close()

    threading.Thread(target=worker, daemon=True).start()
```

- [ ] **Step 5: Add the job type**

In `backend/assistant/models.py`, add to the `job_type` choices list, beside `("chat", "Chatbot Question")`:

```python
        ("self_report", "Self-Report Check"),
```

Then:

```bash
cd backend
./.venv/Scripts/python.exe manage.py makemigrations assistant
./.venv/Scripts/python.exe manage.py migrate
```

Update the metrics test that pins the exact feature set — `backend/assistant/tests/test_metrics.py`, `test_every_feature_appears_even_with_no_runs` — to include `"self_report"`.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd backend && ./.venv/Scripts/python.exe manage.py test clinical.tests.test_self_report_model_check assistant.tests.test_metrics`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/clinical/self_report_model_check.py backend/assistant/prompts.py backend/assistant/models.py backend/assistant/migrations/ backend/assistant/tests/test_metrics.py backend/clinical/tests/test_self_report_model_check.py
git -c user.email=jreynoldcanedo@gmail.com commit --author="Reynold <jreynoldcanedo@gmail.com>" -m "Add the local model as a second self-report detector

It catches phrasing nobody thought to list, which is where the Ilocano entries
will be weakest. It can only add a flag: it is never consulted about removing
one, and the runtime being unavailable degrades silently to the lexicon.

An unparseable reply flags nothing. A flag nobody can explain is worse than no
flag."
```

---

### Task 5: Backfill the existing self-reports

**Files:**
- Create: `backend/clinical/management/commands/scan_self_reports.py`
- Create: `backend/clinical/management/__init__.py` and `backend/clinical/management/commands/__init__.py` if absent
- Test: `backend/clinical/tests/test_scan_self_reports.py`

**Interfaces:**
- Consumes: `detect_concerns()` (Task 1), `SelfReportFlag` (Task 2), `run_model_check()` (Task 4).
- Produces: `manage.py scan_self_reports [--with-model] [--limit N]`.

- [ ] **Step 1: Write the failing test**

Create `backend/clinical/tests/test_scan_self_reports.py`:

```python
from datetime import timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from accounts.models import Role
from children.models import Child
from clinical.models import AgencyFormTemplate, OpinionnaireInvite, SelfReportFlag

User = get_user_model()
FEELING = "How are you feeling this week?"


class ScanSelfReportsTest(TestCase):
    def setUp(self):
        role = Role.objects.create(role_name=Role.PSYCHOLOGIST)
        psy = User.objects.create_user(
            email="p@racco1.gov.ph", username="p", password="pass1234", role=role)
        child = Child.objects.create(fullname="Maria Santos", assigned_psychologist=psy)
        template = AgencyFormTemplate.objects.create(
            title="Self-report", fields=[{"label": FEELING}])
        self.invite = OpinionnaireInvite.objects.create(
            child=child, template=template,
            status=OpinionnaireInvite.SUBMITTED, submitted_at=timezone.now(),
            answers={FEELING: "Lagi akong umiiyak sa gabi."},
            expires_at=timezone.now() + timedelta(days=7))

    def _run(self, *args):
        out = StringIO()
        call_command("scan_self_reports", *args, stdout=out)
        return out.getvalue()

    def test_creates_flags_for_existing_submissions(self):
        self._run()
        self.assertEqual(1, SelfReportFlag.objects.count())

    def test_is_idempotent(self):
        self._run()
        self._run()
        self.assertEqual(1, SelfReportFlag.objects.count())

    def test_skips_unsubmitted_invites(self):
        self.invite.status = OpinionnaireInvite.PENDING
        self.invite.save()
        self._run()
        self.assertEqual(0, SelfReportFlag.objects.count())

    def test_does_not_call_the_model_by_default(self):
        # The model pass is opt-in: 122 records at ~2s each is four minutes.
        from unittest.mock import patch
        with patch("clinical.self_report_model_check.run_model_check") as run:
            self._run()
        run.assert_not_called()

    def test_calls_the_model_when_asked(self):
        from unittest.mock import patch
        with patch("clinical.self_report_model_check.run_model_check") as run:
            self._run("--with-model")
        run.assert_called_once_with(self.invite.pk)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd backend && ./.venv/Scripts/python.exe manage.py test clinical.tests.test_scan_self_reports`
Expected: FAIL — `CommandError: Unknown command: 'scan_self_reports'`

- [ ] **Step 3: Write the command**

Create `backend/clinical/management/commands/scan_self_reports.py`:

```python
"""Flag self-reports that were submitted before flagging existed.

Idempotent: the unique constraint on (invite, question, source) means a second
run creates nothing. The model pass is opt-in — 122 records at roughly two
seconds each is four minutes, and the lexicon pass is instant.

    manage.py scan_self_reports                # lexicon only
    manage.py scan_self_reports --with-model   # also ask the local model
"""
from django.core.management.base import BaseCommand

from clinical.models import OpinionnaireInvite, SelfReportFlag
from clinical.self_report_detection import detect_concerns


class Command(BaseCommand):
    help = "Flag distress in self-reports already in the database."

    def add_arguments(self, parser):
        parser.add_argument("--with-model", action="store_true",
                            help="Also run the local model over each report.")
        parser.add_argument("--limit", type=int, default=0,
                            help="Stop after this many invites (0 = all).")

    def handle(self, *args, **options):
        from clinical import self_report_model_check

        qs = (OpinionnaireInvite.objects
              .filter(status=OpinionnaireInvite.SUBMITTED)
              .select_related("child").order_by("pk"))
        if options["limit"]:
            qs = qs[:options["limit"]]

        scanned = created = 0
        for invite in qs:
            scanned += 1
            for question, answer in (invite.answers or {}).items():
                for hit in detect_concerns(question, answer):
                    _, made = SelfReportFlag.objects.get_or_create(
                        invite=invite, question=question,
                        source=SelfReportFlag.LEXICON,
                        defaults={"child": invite.child, "answer": answer,
                                  "matched": hit["phrase"]})
                    created += int(made)
                    break
            if options["with_model"]:
                self_report_model_check.run_model_check(invite.pk)

        self.stdout.write(
            f"scan_self_reports: {scanned} submissions, {created} new flags.")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && ./.venv/Scripts/python.exe manage.py test clinical.tests.test_scan_self_reports`
Expected: PASS.

- [ ] **Step 5: Run it against the real local database**

```bash
cd backend && ./.venv/Scripts/python.exe manage.py scan_self_reports
```

Expected: `scan_self_reports: 122 submissions, N new flags.` Read `N` and sanity-check it against the string listing from Task 1 Step 5. **Do not turn `N` into a recall percentage.**

- [ ] **Step 6: Commit**

```bash
git add backend/clinical/management backend/clinical/tests/test_scan_self_reports.py
git -c user.email=jreynoldcanedo@gmail.com commit --author="Reynold <jreynoldcanedo@gmail.com>" -m "Backfill flags for self-reports submitted before flagging existed

Idempotent through the unique constraint, so it is safe to re-run after the
phrase list grows — which is how the list gets tuned from real use.

The model pass is opt-in. 122 records at roughly two seconds each is four
minutes, and the lexicon pass is instant."
```

---

### Task 6: Surface it as a care-gap alert

**Files:**
- Modify: `backend/clinical/care_gaps.py`
- Test: `backend/clinical/tests/test_care_gaps.py` (append a class)

**Interfaces:**
- Consumes: `SelfReportFlag` (Task 2).
- Produces: an alert dict with `type="self_report_concern"`, `severity="danger"`, plus the existing `child_id`, `child_name`, `message` keys the chatbot and Monitoring already read.

- [ ] **Step 1: Write the failing test**

Append to `backend/clinical/tests/test_care_gaps.py`:

```python
class SelfReportConcernAlertTest(TestCase):
    """The alert reads persisted flags. No text analysis runs inside
    compute_alerts — it is called on every page load."""

    def setUp(self):
        from datetime import timedelta
        from django.utils import timezone
        from accounts.models import Role
        from django.contrib.auth import get_user_model
        from clinical.models import (AgencyFormTemplate, OpinionnaireInvite,
                                     SelfReportFlag)

        User = get_user_model()
        role = Role.objects.create(role_name=Role.PSYCHOLOGIST)
        self.psy = User.objects.create_user(
            email="p@racco1.gov.ph", username="p", password="pass1234", role=role)
        self.other = User.objects.create_user(
            email="q@racco1.gov.ph", username="q", password="pass1234", role=role)
        self.mine = Child.objects.create(fullname="Maria Santos",
                                         assigned_psychologist=self.psy)
        self.theirs = Child.objects.create(fullname="Juan Dela Cruz",
                                           assigned_psychologist=self.other)
        template = AgencyFormTemplate.objects.create(
            title="Self-report", fields=[{"label": "How are you feeling this week?"}])
        self.invite = OpinionnaireInvite.objects.create(
            child=self.mine, template=template,
            status=OpinionnaireInvite.SUBMITTED, submitted_at=timezone.now(),
            expires_at=timezone.now() + timedelta(days=7))
        self.flag = SelfReportFlag.objects.create(
            invite=self.invite, child=self.mine,
            question="How are you feeling this week?",
            answer="Lagi akong umiiyak sa gabi.",
            source=SelfReportFlag.LEXICON, matched="umiiyak")

    def _types(self, qs):
        return [a["type"] for a in compute_alerts(qs)]

    def test_an_unreviewed_flag_raises_an_alert(self):
        self.assertIn("self_report_concern",
                      self._types(Child.objects.filter(pk=self.mine.pk)))

    def test_the_alert_does_not_quote_the_child(self):
        # The message says a self-report needs reading. The words themselves
        # belong on the child's page, not in a caseload list.
        alert = [a for a in compute_alerts(Child.objects.filter(pk=self.mine.pk))
                 if a["type"] == "self_report_concern"][0]
        self.assertNotIn("umiiyak", alert["message"])
        self.assertEqual("danger", alert["severity"])

    def test_an_acknowledged_flag_raises_nothing(self):
        from django.utils import timezone
        self.flag.reviewed_by = self.psy
        self.flag.reviewed_at = timezone.now()
        self.flag.save()
        self.assertNotIn("self_report_concern",
                         self._types(Child.objects.filter(pk=self.mine.pk)))

    def test_it_is_scoped_to_the_children_passed_in(self):
        self.assertNotIn("self_report_concern",
                         self._types(Child.objects.filter(pk=self.theirs.pk)))
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd backend && ./.venv/Scripts/python.exe manage.py test clinical.tests.test_care_gaps`
Expected: FAIL — `self_report_concern` not in the alert types.

- [ ] **Step 3: Add the rule**

In `backend/clinical/care_gaps.py`, add the import:

```python
from clinical.models import (PreAssessment, ConsentRecord, PsychologicalReport,
                             SelfReportFlag)
```

Inside `compute_alerts`, alongside the other prefetch sets:

```python
    # Children with an unacknowledged self-report flag. Reads persisted rows —
    # no text analysis happens here, because this runs on every page load.
    flagged = dict(SelfReportFlag.objects
                   .filter(child_id__in=ids, reviewed_at__isnull=True)
                   .values_list("child_id")
                   .annotate(n=Count("id")))
```

Add `from django.db.models import Count` to the imports.

Then, in the per-child loop, after the existing rules:

```python
        # 6. The child said something worth reading. This asserts nothing about
        # the case notes — they are never read — only that her own words are
        # waiting.
        n = flagged.get(c.id)
        if n:
            add(c, "self_report_concern",
                f"{n} self-report answer{'s' if n > 1 else ''} awaiting review.",
                "danger")
```

The message deliberately does not quote the child. Her words belong on her own page beside the notes, not in a caseload list that gets skimmed.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && ./.venv/Scripts/python.exe manage.py test clinical.tests.test_care_gaps`
Expected: PASS.

- [ ] **Step 5: Confirm the chatbot picks it up for free**

```bash
cd backend && ./.venv/Scripts/python.exe manage.py test assistant.tests.test_tool_resolvers
```
Expected: PASS — `list_care_gaps` already carries `message`, so the new alert flows into the chatbot with no change.

- [ ] **Step 6: Commit**

```bash
git add backend/clinical/care_gaps.py backend/clinical/tests/test_care_gaps.py
git -c user.email=jreynoldcanedo@gmail.com commit --author="Reynold <jreynoldcanedo@gmail.com>" -m "Raise a care-gap alert for an unread self-report

Reuses compute_alerts, so the flag reaches Monitoring — routed to
Administrator, Staff and Psychologist — with no new screen and no new
permission surface, and the chatbot answers about it through list_care_gaps
with no change at all.

The alert counts the answers waiting and does not quote the child. Her words
belong on her own page beside the notes, not in a caseload list that gets
skimmed."
```

---

### Task 7: The API — read flags, acknowledge them

**Files:**
- Modify: `backend/clinical/serializers.py`, `backend/clinical/views.py`, `backend/clinical/urls.py`
- Modify: `backend/clinical/reports_views.py` (include flags, exempt from carry-history)
- Test: `backend/clinical/tests/test_self_report_api.py`

**Interfaces:**
- Consumes: `SelfReportFlag` (Task 2).
- Produces: `GET /api/self-report-flags/?child=<id>`, `POST /api/self-report-flags/<id>/acknowledge/` with optional `{"note": "..."}`; and `self_report_flags` in the child report payload.

- [ ] **Step 1: Write the failing test**

Create `backend/clinical/tests/test_self_report_api.py`:

```python
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import Role
from children.models import Child
from clinical.models import AgencyFormTemplate, OpinionnaireInvite, SelfReportFlag

User = get_user_model()
FEELING = "How are you feeling this week?"
URL = "/api/self-report-flags/"


class SelfReportApiTest(APITestCase):
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
        template = AgencyFormTemplate.objects.create(
            title="Self-report", fields=[{"label": FEELING}])

        def flag(child):
            invite = OpinionnaireInvite.objects.create(
                child=child, template=template,
                status=OpinionnaireInvite.SUBMITTED, submitted_at=timezone.now(),
                expires_at=timezone.now() + timedelta(days=7))
            return SelfReportFlag.objects.create(
                invite=invite, child=child, question=FEELING,
                answer="Lagi akong umiiyak sa gabi.",
                source=SelfReportFlag.LEXICON, matched="umiiyak")

        self.mine_flag = flag(self.mine)
        self.theirs_flag = flag(self.theirs)

    def test_a_psychologist_sees_only_their_own_childrens_flags(self):
        self.client.force_authenticate(self.psy)
        res = self.client.get(URL)
        ids = [f["id"] for f in res.data]
        self.assertIn(self.mine_flag.id, ids)
        self.assertNotIn(self.theirs_flag.id, ids)

    def test_an_administrator_sees_every_flag(self):
        self.client.force_authenticate(self.admin)
        ids = [f["id"] for f in self.client.get(URL).data]
        self.assertIn(self.theirs_flag.id, ids)

    def test_anonymous_is_refused(self):
        self.assertIn(self.client.get(URL).status_code, (401, 403))

    def test_the_payload_carries_the_words_and_the_reason(self):
        self.client.force_authenticate(self.psy)
        row = self.client.get(URL).data[0]
        self.assertEqual(FEELING, row["question"])
        self.assertEqual("Lagi akong umiiyak sa gabi.", row["answer"])
        self.assertEqual("umiiyak", row["matched"])
        self.assertFalse(row["is_reviewed"])

    def test_acknowledging_records_who_and_when(self):
        self.client.force_authenticate(self.psy)
        res = self.client.post(f"{URL}{self.mine_flag.id}/acknowledge/",
                               {"note": "Called the house parent."}, format="json")
        self.assertEqual(200, res.status_code)
        self.mine_flag.refresh_from_db()
        self.assertEqual(self.psy, self.mine_flag.reviewed_by)
        self.assertIsNotNone(self.mine_flag.reviewed_at)
        self.assertEqual("Called the house parent.", self.mine_flag.review_note)

    def test_cannot_acknowledge_another_psychologists_flag(self):
        self.client.force_authenticate(self.psy)
        res = self.client.post(f"{URL}{self.theirs_flag.id}/acknowledge/", {}, format="json")
        self.assertEqual(404, res.status_code)

    def test_acknowledging_twice_does_not_rewrite_the_first_reviewer(self):
        self.client.force_authenticate(self.psy)
        self.client.post(f"{URL}{self.mine_flag.id}/acknowledge/", {}, format="json")
        first = SelfReportFlag.objects.get(pk=self.mine_flag.pk).reviewed_at
        self.client.force_authenticate(self.admin)
        self.client.post(f"{URL}{self.mine_flag.id}/acknowledge/", {}, format="json")
        self.mine_flag.refresh_from_db()
        self.assertEqual(first, self.mine_flag.reviewed_at)
        self.assertEqual(self.psy, self.mine_flag.reviewed_by)


class CarryHistoryExemptionTest(APITestCase):
    """Self-reports are the child's own words, not carried history. They reach
    the psychologist responsible for her now, regardless of the control."""

    def test_a_flag_is_visible_with_history_switched_off(self):
        role = Role.objects.create(role_name=Role.PSYCHOLOGIST)
        psy = User.objects.create_user(
            email="p@racco1.gov.ph", username="p", password="pass1234", role=role)
        child = Child.objects.create(fullname="Maria Santos",
                                     assigned_psychologist=psy,
                                     assignee_sees_history=False)
        template = AgencyFormTemplate.objects.create(
            title="Self-report", fields=[{"label": FEELING}])
        invite = OpinionnaireInvite.objects.create(
            child=child, template=template,
            status=OpinionnaireInvite.SUBMITTED, submitted_at=timezone.now(),
            expires_at=timezone.now() + timedelta(days=7))
        SelfReportFlag.objects.create(
            invite=invite, child=child, question=FEELING,
            answer="Lagi akong umiiyak sa gabi.",
            source=SelfReportFlag.LEXICON, matched="umiiyak")

        self.client.force_authenticate(psy)
        self.assertEqual(1, len(self.client.get(URL).data))
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd backend && ./.venv/Scripts/python.exe manage.py test clinical.tests.test_self_report_api`
Expected: FAIL — 404 on `/api/self-report-flags/`.

- [ ] **Step 3: Add the serializer**

Append to `backend/clinical/serializers.py`:

```python
class SelfReportFlagSerializer(serializers.ModelSerializer):
    is_reviewed = serializers.BooleanField(read_only=True)
    child_name = serializers.CharField(source="child.fullname", read_only=True)
    reviewed_by_name = serializers.CharField(
        source="reviewed_by.fullname", read_only=True, default=None)

    class Meta:
        model = SelfReportFlag
        fields = ["id", "child", "child_name", "invite", "question", "answer",
                  "source", "matched", "created_at", "is_reviewed",
                  "reviewed_at", "reviewed_by_name", "review_note"]
        read_only_fields = fields
```

Add `SelfReportFlag` to the models import at the top of the file.

- [ ] **Step 4: Add the viewset**

Append to `backend/clinical/views.py`:

```python
class SelfReportFlagViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """A child's own words, flagged as worth reading.

    Deliberately NOT a `_ChildScopedClinicalViewSet`: self-reports are exempt
    from the carry-history control. That control spares a new psychologist a
    colleague's prior opinions; it must not hide the child from the person now
    responsible for her.
    """
    serializer_class = SelfReportFlagSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        qs = (SelfReportFlag.objects
              .select_related("child", "reviewed_by").order_by("-created_at"))
        child_id = self.request.query_params.get("child")
        if child_id:
            if not str(child_id).isdigit():
                return qs.none()
            qs = qs.filter(child_id=child_id)
        # Scope from the caller, never from a parameter.
        if _role(self.request) == Role.PSYCHOLOGIST:
            qs = qs.filter(child__assigned_psychologist=self.request.user)
        return qs

    @action(detail=True, methods=["post"])
    def acknowledge(self, request, pk=None):
        flag = self.get_queryset().filter(pk=pk).first()
        if flag is None:
            return Response({"detail": "Not found."},
                            status=status.HTTP_404_NOT_FOUND)
        # First acknowledgement wins: the record of who actually read it first
        # must not be overwritten by whoever clicked next.
        if flag.reviewed_at is None:
            flag.reviewed_by = request.user
            flag.reviewed_at = timezone.now()
            flag.review_note = str(request.data.get("note") or "")[:2000]
            flag.save(update_fields=["reviewed_by", "reviewed_at", "review_note"])
        return Response(SelfReportFlagSerializer(flag).data)
```

Ensure `mixins`, `permissions`, `action`, `status`, `timezone`, `Role`, `_role`, `SelfReportFlag` and `SelfReportFlagSerializer` are imported in `views.py`.

- [ ] **Step 5: Register the route**

In `backend/clinical/urls.py`, beside the other registrations:

```python
router.register("self-report-flags", SelfReportFlagViewSet, basename="self-report-flag")
```

Import `SelfReportFlagViewSet` at the top.

- [ ] **Step 6: Include flags in the child report payload**

In `backend/clinical/reports_views.py`, add to the querysets gathered near line 44:

```python
        self_report_flags = child.self_report_flags.select_related("reviewed_by")
```

**Do not add it to the carry-history filter block.** Add this comment directly above that block so the omission reads as deliberate:

```python
        # Carry-history control: a newly assigned psychologist without history
        # sees only records they authored themselves.
        #
        # self_report_flags is deliberately absent. Self-reports are the
        # child's own words, not a colleague's prior opinions, and the person
        # responsible for her now must see them.
```

Add to the response dict:

```python
            "self_report_flags": SelfReportFlagSerializer(self_report_flags, many=True).data,
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `cd backend && ./.venv/Scripts/python.exe manage.py test clinical.tests.test_self_report_api clinical.tests.test_reports`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/clinical/serializers.py backend/clinical/views.py backend/clinical/urls.py backend/clinical/reports_views.py backend/clinical/tests/test_self_report_api.py
git -c user.email=jreynoldcanedo@gmail.com commit --author="Reynold <jreynoldcanedo@gmail.com>" -m "Expose self-report flags and let them be acknowledged

Scope comes from the caller, never from a parameter — a psychologist sees only
their own children's flags, an administrator sees all.

The viewset is deliberately not child-scoped in the usual way: self-reports are
exempt from the carry-history control, and reports_views carries a comment
saying why, so the omission cannot be read later as an oversight.

First acknowledgement wins. The record of who actually read it first must not
be overwritten by whoever clicked next."
```

---

### Task 8: Show the words where they will be seen

**Files:**
- Modify: `frontend/src/api/clinical.js` (or the module holding child-report calls — check `frontend/src/api/` first)
- Modify: `frontend/src/pages/ChildProgressReport.jsx`

**Interfaces:**
- Consumes: `self_report_flags` from the child report payload (Task 7); `POST /api/self-report-flags/<id>/acknowledge/`.
- Produces: no new exports.

- [ ] **Step 1: Add the API call**

Find the module that already calls the child report endpoint (`grep -rn "report/child" frontend/src/api/`) and append:

```javascript
// Acknowledge one self-report flag. First acknowledgement wins server-side.
export const acknowledgeSelfReportFlag = (id, note = '') =>
  api.post(`/self-report-flags/${id}/acknowledge/`, { note }).then((r) => r.data);
```

- [ ] **Step 2: Render flagged answers beside the remarks**

In `ChildProgressReport.jsx`, above the remarks section, add a block that renders `data.self_report_flags` where `is_reviewed` is false. Requirements, in order of importance:

1. **Expanded by default.** Not behind a toggle. The whole failure this feature addresses is words folded away that nobody had a reason to open.
2. **Placed adjacent to the remarks**, not in the separate opinionnaire section further down.
3. Shows the **question**, then the **answer** in the child's own words, then who/what flagged it (`matched`).
4. An **Acknowledge** button calling the API, with an optional note field.
5. Reviewed flags are not shown here — they are history, and `compute_alerts` already ignores them.

Follow the file's existing style: inline styles using `var(--…)` tokens, `Icon` from `../ui`, no new dependencies.

Suggested copy for the block heading: **"In her own words"** / **"In his own words"** based on `data.child.gender`, falling back to **"In the child's own words"** when gender is unspecified — the field is `blank=True` and must not render as an empty string.

- [ ] **Step 3: Add the carry-history note**

Where the opinionnaire section renders, add a single muted line:

```
Self-reports are always shown — the child's own words are not part of carried history.
```

This exists so an administrator who unticked carry-history and still sees self-reports reads that as designed rather than broken.

- [ ] **Step 4: Lint and build**

```bash
cd frontend && npm run lint && npm run build
```
Expected: both clean. `npm run lint` is the one that catches a hook after an early return or a reference to a deleted variable — `npm run build` exits 0 on both.

- [ ] **Step 5: Open the page in a browser**

Start the app (`run-local.bat`), sign in, and open a child who has an unreviewed flag. `manage.py scan_self_reports` from Task 5 will have created some.

Check: the block renders, the child's words are visible without clicking anything, Acknowledge works and the block disappears, and the Monitoring screen shows the alert.

**A page that renders nothing still exits `npm run build` with code 0.** This step is not optional.

- [ ] **Step 6: Commit**

```bash
git add frontend/src
git -c user.email=jreynoldcanedo@gmail.com commit --author="Reynold <jreynoldcanedo@gmail.com>" -m "Show a flagged self-report expanded, beside the case notes

The words were never missing. ChildProgressReport already rendered them,
collapsed behind an 'Answers (3)' toggle in a section away from the remarks —
one click from anyone who thought to look, and nobody did.

Flagged answers now render expanded and adjacent to the remarks they should be
read against, with an acknowledgement that clears them.

States that self-reports are always shown, so an administrator who unticked
carry-history reads their presence as designed rather than broken."
```

---

### Task 9: Measure the model detector

**Files:**
- Modify: `backend/assistant/management/commands/ai_eval.py`

**Interfaces:**
- Consumes: `build_self_report_prompt`, `SELF_REPORT_SYSTEM` (Task 4); `_parse` from `clinical.self_report_model_check`.
- Produces: `manage.py ai_eval --feature self_report`.

- [ ] **Step 1: Add the labelled cases**

In `ai_eval.py`, beside `CHAT_CASES`, add. Every string is from the live database; the label is a human judgement, stated as such:

```python
# Hand-labelled (question, answer) pairs, every string taken from the live
# database. The label is a human judgement, not ground truth from the agency.
# Both columns matter: a detector that flags everything scores perfectly on
# recall and is useless.
SELF_REPORT_CASES = [
    ("tl distress", FEELING_Q, "Gusto ko na umuwi. Lagi akong umiiyak sa gabi.", True),
    ("tl distress", WORRY_Q, "Hindi ko masabi kasi baka magalit sila. Masakit ang dibdib ko.", True),
    ("tl distress", FEELING_Q, "I feel alone. Ayaw ko na dito, gusto ko na lang matulog.", True),
    ("mixed distress", WORRY_Q, "Nobody listens to me here. Wala akong makausap.", True),
    ("ilocano distress", FEELING_Q, "Mabutbuteng. I am scared but I don't tell them.", True),
    ("ilocano distress", WORRY_Q, "Adda met bassit nga problema but I don't want to say.", True),
    ("ambiguous", FEELING_Q, "Sometimes I cannot sleep. Naiisip ko yung bahay namin.", True),
    ("ambiguous", FEELING_Q, "Minsan okay, minsan hindi. Depende sa araw.", False),
    ("calm control", FEELING_Q, "I feel safe. Ang bait ng nag-aalaga sa akin.", False),
    ("calm control", FEELING_Q, "Okay lang. I like the food and my bed.", False),
    ("calm control", FEELING_Q, "Masaya naman ako dito. May kaibigan na ako.", False),
    ("ilocano calm", FEELING_Q, "Naimbag met. I can sleep at night now.", False),
    ("calm control", FEELING_Q, "I miss my sister. But the people here are kind.", False),
]

FEELING_Q = "How are you feeling this week?"
WORRY_Q = "Is there anything worrying you?"
```

Move `FEELING_Q` and `WORRY_Q` **above** `SELF_REPORT_CASES` — they are referenced in it.

- [ ] **Step 2: Add the feature method**

Add `"self_report"` to the `--feature` choices, dispatch it in `handle`, and add:

```python
    def _self_report(self, reps):
        """Score the model detector against hand-labelled pairs.

        Reports misses AND false alarms. A detector that flags everything has
        perfect recall and is worthless, so both columns are printed.
        """
        from clinical.self_report_model_check import _parse

        self.stdout.write("\n" + "=" * 62)
        self.stdout.write(f"SELF-REPORT — {len(SELF_REPORT_CASES)} cases x {reps} reps")

        runs, flags, latencies = 0, {}, []
        for label, question, answer, expected in SELF_REPORT_CASES:
            self.stdout.write(f"\n  {label}: {answer[:58]}")
            for rep in range(1, reps + 1):
                started = time.monotonic()
                try:
                    reply = self.client.generate(
                        prompts.build_self_report_prompt(question, answer),
                        system=prompts.SELF_REPORT_SYSTEM)
                except AIUnavailable as exc:
                    self.stdout.write(f"    rep{rep}: unavailable — {exc}")
                    continue
                ms = int((time.monotonic() - started) * 1000)
                latencies.append(ms)
                runs += 1

                got = _parse(reply) is not None
                found = {}
                if expected and not got:
                    found["MISS"] = [answer[:50]]
                elif got and not expected:
                    found["false alarm"] = [answer[:50]]
                for key in found:
                    flags[key] = flags.get(key, 0) + 1
                self._report(rep, ms, found, sample=str(reply))

        latencies.sort()
        median = latencies[len(latencies) // 2] if latencies else 0
        return ("SELF-REPORT", runs, flags, median)
```

- [ ] **Step 3: Run it**

```bash
cd backend && ./.venv/Scripts/python.exe manage.py ai_eval --feature self_report --reps 3
```

Read the output. **A miss on an Ilocano case is the finding that matters** — it is the case the lexicon is weakest on and the reason the model was added.

Record what you observe in the commit message. Do not describe the model as reliable on Ilocano on the strength of a handful of cases: 13 hand-labelled pairs is evidence, not a guarantee, and it is exactly the kind of number this project has been burned by before.

- [ ] **Step 4: Verify the eval can fail**

A detector that never fires is worthless. Prove this one works by breaking it:

```bash
cd backend && ./.venv/Scripts/python.exe manage.py shell -c "
from clinical import self_report_model_check as m
print('YES reply  ->', m._parse('YES - the child sounds distressed'))
print('NO reply   ->', m._parse('NO - the child sounds settled'))
print('garbage    ->', m._parse('I think perhaps maybe'))
"
```
Expected: a reason, then `None`, then `None`.

- [ ] **Step 5: Commit**

```bash
git add backend/assistant/management/commands/ai_eval.py
git -c user.email=jreynoldcanedo@gmail.com commit --author="Reynold <jreynoldcanedo@gmail.com>" -m "Measure the self-report model detector in both directions

Scores misses and false alarms against hand-labelled pairs taken from the live
database. A detector that flags everything has perfect recall and is worthless,
so both columns are printed — the unmeasured half is the half that breaks.

The Ilocano cases are the ones that matter: they are where the phrase list is
weakest and the reason the model was added at all."
```

---

### Task 10: Documentation and the full gate

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add a handbook section**

Add after the chatbot section:

```markdown
## Self-report concerns

Built 27 Aug 2026. Flags distress in a child's own words. Design in
`docs/superpowers/specs/2026-08-27-self-report-concerns-design.md`.

- **The children write Ilocano, not only Taglish.** The agency is RACCO 1 and
  the self-reports include `mabutbuteng` (scared) and `adda … problema` (there
  is a problem). A Tagalog-only list passes both. `LEXICON_REVIEWED["ilo"]` is
  **False** — the Ilocano entries have not been read by a speaker, and that
  gates launch, not building.
- **Detection reads the (question, answer) pair, never the answer alone.** 62 of
  122 reports answer "Who do you talk to when you are sad?" with "Nobody" or
  "Ako lang" — the largest signal in the data, and invisible to anything
  reading answers on their own.
- **Two detectors, either can flag, neither can clear.** The lexicon is the
  floor and runs synchronously; the model runs in a thread and only ever adds.
- **No recall figure exists and none may be quoted from demo data** — 366
  answers are only 17 distinct strings, so any number measures the seeder.
- **Self-reports are exempt from the carry-history control.** The child's own
  words are not a colleague's prior opinions. Case notes are unaffected and
  still follow `assignee_sees_history`, which defaults to True and filters at
  read time rather than deleting anything.
```

- [ ] **Step 2: Run the whole gate**

```bash
cd backend && ./.venv/Scripts/python.exe manage.py test
cd ../frontend && npm run lint && npm run build
```
Expected: backend green (582 + the new tests), lint and build clean. Update the test count in CLAUDE.md's "Before committing" section to the real number.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git -c user.email=jreynoldcanedo@gmail.com commit --author="Reynold <jreynoldcanedo@gmail.com>" -m "Document self-report concerns in the handbook

Records the facts that are expensive to rediscover: the children write Ilocano
and the phrase list has not been read by a speaker, detection reads the
question with the answer, and no recall figure can come from demo data because
366 answers are only 17 distinct strings."
```

---

## Self-Review

**Spec coverage.** Every spec section maps to a task: naming and claims → Tasks 1 and 6 copy; the (question, answer) rule → Task 1; Ilocano → Tasks 1, 9, 10; the two detectors → Tasks 1 and 4; storage → Task 2; timing → Tasks 3 and 4; surfacing → Tasks 6, 7, 8; carry-history exemption → Task 7 Step 6 and Task 8 Step 3; testing → every task; tuning from real use → Task 2 (`matched`) and Task 5 (idempotent re-scan); non-goals → no task adds severity ranking, notification, or note-reading.

**Known gap, deliberately left:** the spec notes Staff see Monitoring and therefore these flags, one role wider than the chosen audience. No task filters them out, matching the decision to accept it. If that changes, it is a one-line `_role` check in `compute_alerts`' caller.

**Type consistency.** `detect_concerns(question, answer) -> list[{"phrase", "rule"}]` is produced in Task 1 and consumed in Tasks 3 and 5 with that shape. `SelfReportFlag.LEXICON`/`.MODEL` are defined in Task 2 and used in Tasks 3, 4, 5, 6, 7. `run_model_check(invite_id)` and `start_model_check(invite_id)` are defined in Task 4 and called in Tasks 3 and 5. `_parse(reply)` is defined in Task 4 and used in Task 9. The alert `type` string `self_report_concern` is used in Task 6 only.

**Placeholder scan:** none. Task 8 Step 2 describes UI requirements rather than exact JSX because the surrounding file's style must be matched at the point of editing; every requirement is stated concretely and the copy is given.
