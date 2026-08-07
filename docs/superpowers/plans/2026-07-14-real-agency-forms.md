# Real Agency Forms Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Digitize the agency's two real documents — the Adoption Informed Consent and the two Adoption Pre-Assessment Questionnaires (Custodian/PAP + Child) — as seeded `AgencyFormTemplate`s wired into the pre-assessment wizard and printable blank forms.

**Architecture:** Light model extension (`body` prose field on templates, `respondent` label on interviews, `section` field type convention), agency-wide shared templates (`owner=None`), an idempotent seed command carrying the full document content, and frontend rendering/print support.

**Tech Stack:** Django 5 + DRF (backend, SQLite dev DB), React 18 + Vite (frontend). No new dependencies.

**Spec:** `docs/superpowers/specs/2026-07-14-real-agency-forms-design.md` — read it first.

## Global Constraints

- Everything happens inside the **NACC-V2 repo** (`C:\Users\User\Desktop\NACC SYS\NACC-V2`). All paths below are relative to that root. Never touch the outer v1 repo.
- **Commits: NO Claude co-author trailer, no "Generated with" line.** Sole author is the user (Reynold). Plain conventional-commit messages only.
- Do NOT commit `frontend/src/components/Sidebar.jsx` — it has an unrelated pre-existing local change. Stage files explicitly by path; never `git add -A`.
- Backend tests run from `backend/`: `./venv/Scripts/python.exe manage.py test <target> -v 1` (Git Bash) — the venv python must be used.
- The full backend suite (`./venv/Scripts/python.exe manage.py test`) has **208 passing tests** before this work; it must stay green.
- Frontend check is `npm run build` from `frontend/` (no frontend test suite exists).
- Template titles use the em dash `—` exactly as written (e.g. `Adoption Pre-Assessment Questionnaire — Custodian/PAP`).
- `## ` at the start of a `body` line marks a section heading; blank lines separate paragraphs (spec §2.1).

---

### Task 1: Backend — `body` + `respondent` fields (models, migration, serializers)

**Files:**
- Modify: `backend/clinical/models.py` (AgencyFormTemplate ~line 70, ClinicalInterviewRecord ~line 128)
- Modify: `backend/clinical/serializers.py` (AgencyFormTemplateSerializer lines 24–51, ClinicalInterviewRecordSerializer lines 67–80, PreAssessmentSerializer lines 80–96)
- Create: `backend/clinical/migrations/0007_*.py` (via makemigrations)
- Test: `backend/clinical/tests/test_agency_forms.py` (new)

**Interfaces:**
- Consumes: existing `AgencyFormTemplate`, `ClinicalInterviewRecord`, `PreAssessment` models.
- Produces: `AgencyFormTemplate.body: str` (blank ok), `ClinicalInterviewRecord.respondent: str` (blank ok), serializer fields `body`, `respondent`, and read-only `PreAssessmentSerializer.interview_respondent`. Task 3 seeds `body`; Tasks 6–8 read all three from the API.

- [ ] **Step 1: Write the failing tests**

Create `backend/clinical/tests/test_agency_forms.py`:

```python
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from accounts.models import Role
from children.models import Child
from clinical.models import AgencyFormTemplate

User = get_user_model()


class AgencyFormsBase(APITestCase):
    def setUp(self):
        self.admin_role = Role.objects.create(role_name=Role.ADMINISTRATOR)
        self.psy_role = Role.objects.create(role_name=Role.PSYCHOLOGIST)
        self.admin = User.objects.create_user(
            email="a@racco1.gov.ph", username="a", password="pass1234", role=self.admin_role)
        self.psy = User.objects.create_user(
            email="p@racco1.gov.ph", username="p", password="pass1234", role=self.psy_role)
        self.other = User.objects.create_user(
            email="o@racco1.gov.ph", username="o", password="pass1234", role=self.psy_role)
        self.child = Child.objects.create(
            fullname="Ana", case_type="Foster Care", assigned_psychologist=self.psy)

    def _auth(self, email):
        token = self.client.post("/api/auth/login/", {
            "email": email, "password": "pass1234"}).data["access"]
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + token)


class TemplateBodyTest(AgencyFormsBase):
    def test_body_roundtrips_through_api(self):
        self._auth("a@racco1.gov.ph")
        resp = self.client.post("/api/form-templates/", {
            "form_type": "consent", "title": "Consent X",
            "body": "Intro paragraph.\n\n## I. PURPOSE\nBody text.",
            "fields": [], "attestation": True}, format="json")
        self.assertEqual(resp.status_code, 201)
        self.assertIn("## I. PURPOSE", resp.data["body"])
        self.assertEqual(AgencyFormTemplate.objects.get(pk=resp.data["id"]).body,
                         "Intro paragraph.\n\n## I. PURPOSE\nBody text.")

    def test_body_edit_bumps_version(self):
        self._auth("a@racco1.gov.ph")
        created = self.client.post("/api/form-templates/", {
            "form_type": "consent", "title": "Consent X", "body": "v1 text",
            "fields": [], "attestation": True}, format="json")
        resp = self.client.patch(f"/api/form-templates/{created.data['id']}/", {
            "body": "v2 text", "attestation": True}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["version"], 2)


class InterviewRespondentTest(AgencyFormsBase):
    def test_respondent_roundtrips_through_api(self):
        self._auth("p@racco1.gov.ph")
        resp = self.client.post("/api/interviews/", {
            "child": self.child.id, "answers": {"Q": "A"},
            "respondent": "Custodian/PAP"}, format="json")
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data["respondent"], "Custodian/PAP")
        listed = self.client.get(f"/api/interviews/?child={self.child.id}")
        self.assertEqual(listed.data[0]["respondent"], "Custodian/PAP")
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `backend/`): `./venv/Scripts/python.exe manage.py test clinical.tests.test_agency_forms -v 1`
Expected: ERRORS — `body` not a model/serializer field (400 or KeyError), `respondent` KeyError.

- [ ] **Step 3: Add the model fields**

In `backend/clinical/models.py`, inside `AgencyFormTemplate`, directly under the `title` line:

```python
    title = models.CharField(max_length=200)
    # Document prose shown before the fields (on screen and in print).
    # Lines starting with "## " render as section headings.
    body = models.TextField(blank=True, default="")
```

Inside `ClinicalInterviewRecord`, directly under the `template` field:

```python
    # Who answered this interview (e.g. "Custodian/PAP", "Child", "Guardian").
    respondent = models.CharField(max_length=100, blank=True, default="")
```

- [ ] **Step 4: Make the migration**

Run (from `backend/`): `./venv/Scripts/python.exe manage.py makemigrations clinical`
Expected: creates `0007_agencyformtemplate_body_clinicalinterviewrecord_respondent.py` (name may vary slightly; must be 0007).
Then: `./venv/Scripts/python.exe manage.py migrate` — applies cleanly.

- [ ] **Step 5: Update the serializers**

In `backend/clinical/serializers.py`:

`AgencyFormTemplateSerializer.Meta.fields` — add `"body"` after `"title"`:

```python
        fields = ["id", "form_type", "title", "body", "fields", "version",
                  "owner", "owner_name", "attestation", "attested_at",
                  "active", "updated_at"]
```

`AgencyFormTemplateSerializer.update()` — body changes bump the version too:

```python
    def update(self, instance, validated_data):
        # Any content edit bumps the version; re-attestation is enforced by the field validator.
        content_changed = (
            ("fields" in validated_data and validated_data["fields"] != instance.fields)
            or ("body" in validated_data and validated_data["body"] != instance.body))
        if content_changed:
            instance.version += 1
            validated_data["attested_at"] = timezone.now()
        return super().update(instance, validated_data)
```

`ClinicalInterviewRecordSerializer.Meta.fields` — add `"respondent"` after `"answers"`:

```python
        fields = ["id", "child", "child_name", "template", "template_title",
                  "answers", "respondent", "interviewer", "interviewer_name",
                  "date", "created_at"]
```

`PreAssessmentSerializer` — add a read-only respondent passthrough (declare with the other read-only fields, and add to `Meta.fields` after `"interview"`):

```python
    interview_respondent = serializers.CharField(
        source="interview.respondent", read_only=True, default=None)
```

```python
        fields = ["id", "child", "child_name", "psychologist", "psychologist_name",
                  "date", "status", "instruments", "instrument_titles",
                  "consent", "consent_status", "interview", "interview_respondent",
                  "notes", "completed_at", "created_at"]
```

- [ ] **Step 6: Run the new tests — pass; then the full suite**

Run: `./venv/Scripts/python.exe manage.py test clinical.tests.test_agency_forms -v 1` → OK (3 tests).
Run: `./venv/Scripts/python.exe manage.py test` → OK, 211 tests.

- [ ] **Step 7: Commit**

```bash
git add backend/clinical/models.py backend/clinical/serializers.py backend/clinical/migrations backend/clinical/tests/test_agency_forms.py
git commit -m "feat(clinical): template body text + interview respondent fields"
```

---

### Task 2: Backend — shared agency-wide templates (visibility + write protection)

**Files:**
- Modify: `backend/clinical/views.py` (`AgencyFormTemplateViewSet`, lines 81–120)
- Test: `backend/clinical/tests/test_agency_forms.py` (append)

**Interfaces:**
- Consumes: `AgencyFormTemplate.owner` (nullable FK), `_role()` helper and `Role` import already present in `views.py`.
- Produces: psychologists' template queryset = own + `owner=None`; unsafe methods on non-owned templates → 403 `PermissionDenied("Official agency forms can only be edited by an administrator.")`. Task 3's seeded templates rely on this to be visible in the wizard.

- [ ] **Step 1: Write the failing tests**

Append to `backend/clinical/tests/test_agency_forms.py`:

```python
class SharedTemplateAccessTest(AgencyFormsBase):
    def setUp(self):
        super().setUp()
        self.shared = AgencyFormTemplate.objects.create(
            form_type="consent", title="Official Consent", owner=None,
            attestation=True, active=True)
        self.own = AgencyFormTemplate.objects.create(
            form_type="consent", title="My Consent", owner=self.psy,
            attestation=True, active=True)
        self.others = AgencyFormTemplate.objects.create(
            form_type="consent", title="Other Consent", owner=self.other,
            attestation=True, active=True)

    def test_psychologist_sees_own_and_shared_only(self):
        self._auth("p@racco1.gov.ph")
        resp = self.client.get("/api/form-templates/")
        self.assertEqual({t["title"] for t in resp.data},
                         {"Official Consent", "My Consent"})

    def test_psychologist_cannot_edit_shared_template(self):
        self._auth("p@racco1.gov.ph")
        resp = self.client.patch(f"/api/form-templates/{self.shared.id}/", {
            "title": "Renamed", "attestation": True}, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_psychologist_cannot_deactivate_shared_template(self):
        self._auth("p@racco1.gov.ph")
        resp = self.client.post(f"/api/form-templates/{self.shared.id}/deactivate/")
        self.assertEqual(resp.status_code, 403)

    def test_admin_can_edit_shared_template(self):
        self._auth("a@racco1.gov.ph")
        resp = self.client.patch(f"/api/form-templates/{self.shared.id}/", {
            "title": "Official Consent (2025)", "attestation": True}, format="json")
        self.assertEqual(resp.status_code, 200)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/Scripts/python.exe manage.py test clinical.tests.test_agency_forms.SharedTemplateAccessTest -v 1`
Expected: `test_psychologist_sees_own_and_shared_only` fails (shared missing from list); the two 403 tests fail (currently 404 — shared is filtered out of the queryset entirely; after the queryset fix they'd be 200 without the write guard).

- [ ] **Step 3: Implement queryset + write guard**

In `backend/clinical/views.py`, ensure imports include `Q` and `PermissionDenied`:

```python
from django.db.models import Q
from rest_framework.exceptions import PermissionDenied
```

(Check first — `Q` may already be imported; don't duplicate.)

In `AgencyFormTemplateViewSet.get_queryset()`, replace the psychologist filter line:

```python
        if _role(self.request) == Role.PSYCHOLOGIST:
            qs = qs.filter(Q(owner=self.request.user) | Q(owner__isnull=True))
```

Add the guard method and wire it into every unsafe path:

```python
    def _assert_can_write(self, obj):
        # Shared (owner=None) official forms are admin-managed; psychologists
        # may only modify templates they own.
        if _role(self.request) == Role.PSYCHOLOGIST and obj.owner_id != self.request.user.id:
            raise PermissionDenied(
                "Official agency forms can only be edited by an administrator.")

    def perform_update(self, serializer):
        self._assert_can_write(serializer.instance)
        self._log(serializer.save(), ActivityLog.UPDATED)

    def perform_destroy(self, instance):
        self._assert_can_write(instance)
        instance.delete()
```

In the existing `deactivate` action, add the guard right after `obj = self.get_object()`:

```python
        obj = self.get_object()
        self._assert_can_write(obj)
```

- [ ] **Step 4: Run the tests — pass; then the full suite**

Run: `./venv/Scripts/python.exe manage.py test clinical.tests.test_agency_forms -v 1` → OK (7 tests).
Run: `./venv/Scripts/python.exe manage.py test` → OK, 215 tests. (If an existing test asserted the old psychologist-only filtering, read it and update it to the new shared-visibility rule — the spec supersedes it.)

- [ ] **Step 5: Commit**

```bash
git add backend/clinical/views.py backend/clinical/tests/test_agency_forms.py
git commit -m "feat(clinical): agency-wide shared form templates, admin-only edits"
```

---

### Task 3: Backend — `seed_agency_forms` management command

**Files:**
- Create: `backend/clinical/management/__init__.py` (empty)
- Create: `backend/clinical/management/commands/__init__.py` (empty)
- Create: `backend/clinical/management/commands/seed_agency_forms.py`
- Test: `backend/clinical/tests/test_agency_forms.py` (append)

**Interfaces:**
- Consumes: `AgencyFormTemplate` model with `body` (Task 1).
- Produces: `python manage.py seed_agency_forms` → exactly 3 templates, `owner=None`, `attestation=True`, titles exactly:
  - `Informed Consent for Psychological Evaluation (Adoption)` (consent)
  - `Adoption Pre-Assessment Questionnaire — Custodian/PAP` (clinical_interview)
  - `Adoption Pre-Assessment Questionnaire — Child` (clinical_interview)

- [ ] **Step 1: Write the failing test**

Append to `backend/clinical/tests/test_agency_forms.py` (add `from django.core.management import call_command` to the imports at the top):

```python
class SeedAgencyFormsTest(APITestCase):
    def test_seed_creates_three_templates_idempotently(self):
        call_command("seed_agency_forms")
        self.assertEqual(AgencyFormTemplate.objects.count(), 3)

        consent = AgencyFormTemplate.objects.get(form_type="consent")
        self.assertEqual(consent.title,
                         "Informed Consent for Psychological Evaluation (Adoption)")
        self.assertEqual(consent.fields, [])
        for heading in ["## I. PURPOSE", "## II. NATURE", "## III. VOLUNTARY",
                        "## IV. CONFIDENTIALITY", "## V. RISKS", "## VI. BENEFITS",
                        "## VII. FEES", "## VIII. ACCURACY", "## IX. QUESTIONS",
                        "## X. CONSENT"]:
            self.assertIn(heading, consent.body)

        pap = AgencyFormTemplate.objects.get(
            title="Adoption Pre-Assessment Questionnaire — Custodian/PAP")
        self.assertEqual(
            len([f for f in pap.fields if f["field_type"] == "section"]), 9)
        self.assertEqual(
            len([f for f in pap.fields if f["field_type"] == "long_text"]), 42)

        kid = AgencyFormTemplate.objects.get(
            title="Adoption Pre-Assessment Questionnaire — Child")
        self.assertEqual(
            len([f for f in kid.fields if f["field_type"] == "section"]), 8)
        self.assertEqual(
            len([f for f in kid.fields if f["field_type"] == "long_text"]), 38)
        self.assertIn("age", kid.body)

        for t in AgencyFormTemplate.objects.all():
            self.assertIsNone(t.owner)
            self.assertTrue(t.attestation)
            self.assertIsNotNone(t.attested_at)

        # Re-run: no duplicates, and in-app edits are preserved.
        consent.body = "EDITED"
        consent.save()
        call_command("seed_agency_forms")
        self.assertEqual(AgencyFormTemplate.objects.count(), 3)
        consent.refresh_from_db()
        self.assertEqual(consent.body, "EDITED")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/Scripts/python.exe manage.py test clinical.tests.test_agency_forms.SeedAgencyFormsTest -v 1`
Expected: FAIL — `Unknown command: 'seed_agency_forms'`.

- [ ] **Step 3: Write the command**

Create the two empty `__init__.py` files, then `backend/clinical/management/commands/seed_agency_forms.py`:

```python
"""Seed the official agency-authored forms (idempotent).

Content transcribed from the real documents in docs/agency-forms/
(agency-authored — inside the copyright boundary; see the 2026-07-14 spec).
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from clinical.models import AgencyFormTemplate


def _sec(label):
    return {"label": label, "field_type": "section", "options": []}


def _q(label):
    return {"label": label, "field_type": "long_text", "options": []}


CONSENT_TITLE = "Informed Consent for Psychological Evaluation (Adoption)"

# Verbatim body: copy the text between the <!-- BODY BEGIN --> and
# <!-- BODY END --> markers in docs/agency-forms/informed-consent-adoption-extracted.md
# (WITHOUT the marker lines themselves, and without the parenthesized intro
# scaffolding — the file's content between the markers IS the body).
CONSENT_BODY = """<PASTE THE MARKED BODY TEXT HERE VERBATIM>"""

PAP_TITLE = "Adoption Pre-Assessment Questionnaire — Custodian/PAP"
PAP_FIELDS = [
    _sec("I. Background Information"),
    _q("Please tell me about yourself and your relationship with the child."),
    _q("How long has the child been under your care?"),
    _q("Can you describe how the child came into your custody?"),
    _q("What were the circumstances that led to the proposed adoption?"),
    _sec("II. Developmental History"),
    _q("What do you know about the child's pregnancy and birth?"),
    _q("Were there any medical or developmental concerns during infancy or early childhood?"),
    _q("Did the child reach developmental milestones (walking, talking, toilet training) on time?"),
    _q("Has the child experienced any serious illness, hospitalization, or disability?"),
    _sec("III. Family History"),
    _q("What can you tell me about the child's birth parents?"),
    _q("How often did the child have contact with his/her birth parents?"),
    _q("What was the quality of their relationship?"),
    _q("Does the child ask about his/her biological parents?"),
    _q("How does the child react when they are mentioned?"),
    _sec("IV. Emotional and Behavioral Functioning"),
    _q("How would you describe the child's personality?"),
    _q("What are the child's strengths?"),
    _q("What behaviors concern you?"),
    _q("How does the child express happiness, sadness, anger, or fear?"),
    _q("How does the child cope with disappointment or frustration?"),
    _q("Has the child experienced any traumatic events?"),
    _q("How did the child respond to these experiences?"),
    _sec("V. Social Functioning"),
    _q("How does the child interact with family members?"),
    _q("How does the child interact with peers?"),
    _q("Does the child easily make friends?"),
    _q("Does the child have difficulty trusting adults or other children?"),
    _q("How does the child respond to authority figures?"),
    _sec("VI. Academic Functioning"),
    _q("How is the child performing in school?"),
    _q("What are the child's favorite subjects?"),
    _q("Has the child experienced behavioral or learning difficulties in school?"),
    _q("How do teachers describe the child?"),
    _sec("VII. Daily Living Skills"),
    _q("Can the child independently perform age-appropriate self-care activities?"),
    _q("What household responsibilities does the child have?"),
    _q("How does the child spend free time?"),
    _sec("VIII. Relationship with Prospective Adoptive Parent(s)"),
    _q("How did the child first meet the prospective adoptive parent(s)?"),
    _q("Describe their relationship."),
    _q("How does the child behave when around them?"),
    _q("Does the child seek comfort from them?"),
    _q("Have you noticed positive changes since they became involved?"),
    _q("Has the child expressed feelings about the planned adoption?"),
    _sec("IX. Adjustment and Readiness"),
    _q("How do you think the child will adjust to the adoptive family?"),
    _q("What challenges do you anticipate?"),
    _q("What support do you believe the child will need?"),
    _q("Is there anything else you think is important for me to know about the child?"),
]

CHILD_TITLE = "Adoption Pre-Assessment Questionnaire — Child"
CHILD_BODY = "Some questions may not be answered depending on the child's age."
CHILD_FIELDS = [
    _sec("I. Home and Family"),
    _q("Who do you live with?"),
    _q("Tell me about the people at home."),
    _q("Who takes care of you?"),
    _q("What do you like most about living with them?"),
    _q("Is there anything you don't like?"),
    _sec("II. School"),
    _q("What grade are you in?"),
    _q("What do you like about school?"),
    _q("What subjects do you enjoy and least enjoy?"),
    _q("Who are your friends in school?"),
    _sec("III. Feelings"),
    _q("What makes you happy?"),
    _q("What makes you sad?"),
    _q("What makes you angry?"),
    _q("When you are upset, what do you usually do?"),
    _q("Who do you talk to when you have problems?"),
    _sec("IV. Relationships"),
    _q("Who are the people you feel closest to?"),
    _q("Who makes you feel safe?"),
    _q("Who do you enjoy spending time with?"),
    _q("Is there someone you miss?"),
    _sec("V. Biological Parents (if developmentally appropriate)"),
    _q("What do you know about your mother?"),
    _q("What do you know about your father?"),
    _q("Do you remember them?"),
    _q("How do you feel when you think about them?"),
    _q("Do you have any questions about them?"),
    _sec("VI. Prospective Adoptive Parent(s)"),
    _q("Can you tell me about (name of adoptive parent)?"),
    _q("What do you like doing together?"),
    _q("How do they make you feel?"),
    _q("Do you feel safe with them?"),
    _q("If you are sick or scared, would you go to them?"),
    _q("What do you think about living with them?"),
    _sec("VII. Understanding of Adoption (if adoption has already been disclosed)"),
    _q("Has anyone talked to you about adoption?"),
    _q("What do you think adoption means?"),
    _q("How do you feel about being adopted?"),
    _q("Is there anything that worries you?"),
    _q("What are you hoping for in your future family?"),
    _sec("VIII. Self-Concept"),
    _q("Can you tell me three things you like about yourself?"),
    _q("What are you good at?"),
    _q("What do you want to be when you grow up?"),
    _q("If you could wish for three things, what would they be?"),
]

TEMPLATES = [
    (AgencyFormTemplate.CONSENT, CONSENT_TITLE, CONSENT_BODY, []),
    (AgencyFormTemplate.CLINICAL_INTERVIEW, PAP_TITLE, "", PAP_FIELDS),
    (AgencyFormTemplate.CLINICAL_INTERVIEW, CHILD_TITLE, CHILD_BODY, CHILD_FIELDS),
]


class Command(BaseCommand):
    help = "Seed the official agency-authored forms (idempotent; never overwrites edits)."

    def handle(self, *args, **options):
        for form_type, title, body, fields in TEMPLATES:
            obj, created = AgencyFormTemplate.objects.get_or_create(
                form_type=form_type, title=title,
                defaults={
                    "body": body, "fields": fields, "owner": None,
                    "attestation": True, "attested_at": timezone.now(),
                    "active": True,
                })
            self.stdout.write(
                ("Created: " if created else "Exists, skipped: ") + title)
```

**Then replace the `CONSENT_BODY` placeholder:** open `docs/agency-forms/informed-consent-adoption-extracted.md`, copy everything between `<!-- BODY BEGIN -->` and `<!-- BODY END -->` (excluding the marker lines), and paste it verbatim inside the triple-quoted string. The pasted text must start with `This Informed Consent Form is executed…` and end with `…in relation to adoption proceedings.` and contain all ten `## ` headings. This is a hard requirement — the test checks the headings, and the seeded body is the legal document.

- [ ] **Step 4: Run the test — pass; then the full suite**

Run: `./venv/Scripts/python.exe manage.py test clinical.tests.test_agency_forms.SeedAgencyFormsTest -v 1` → OK.
Run: `./venv/Scripts/python.exe manage.py test` → OK, 216 tests.

- [ ] **Step 5: Seed the dev database**

Run: `./venv/Scripts/python.exe manage.py seed_agency_forms`
Expected output: three `Created: …` lines. Run again → three `Exists, skipped: …` lines.

- [ ] **Step 6: Commit**

```bash
git add backend/clinical/management backend/clinical/tests/test_agency_forms.py
git commit -m "feat(clinical): seed_agency_forms command with the real adoption forms"
```

---

### Task 4: Frontend — shared print utility with body, sections, consent signature blocks

**Files:**
- Create: `frontend/src/utils/printForm.js`
- Modify: `frontend/src/pages/Instruments.jsx` (delete local `printBlank` lines 102–129; import + use the util at the printer-button callsite ~line 208)

**Interfaces:**
- Consumes: template objects from `GET /api/form-templates/` (`{title, version, form_type, body, fields:[{label, field_type, options}]}`).
- Produces: `printBlankForm(template)` — named export. Tasks 6 uses it from the Consent step; Instruments keeps using it for the printer button.

- [ ] **Step 1: Create `frontend/src/utils/printForm.js`**

```js
// Print a blank copy of an agency form (e.g. for the guardian or examinee to
// sign on paper). Client-side only — opens a print-friendly window.
// `body` prose renders first ("## " lines become headings); consent forms get
// the document's dual signature blocks (Client/Examinee + Licensed Psychologist).
export function printBlankForm(t) {
  const w = window.open('', '_blank', 'width=800,height=900');
  if (!w) return;
  const bodyHtml = (t.body || '').split('\n').map((line) => {
    const s = line.trim();
    if (!s) return '';
    if (s.startsWith('## ')) return `<h2>${s.slice(3)}</h2>`;
    return `<p>${s}</p>`;
  }).join('');
  const lines = (t.fields || []).map((f) => {
    if (f.field_type === 'section') return `<h2>${f.label}</h2>`;
    if (f.field_type === 'yes_no') return `<div class="q">${f.label} &nbsp;&nbsp; ☐ Yes &nbsp;&nbsp; ☐ No</div>`;
    if (f.field_type === 'choice') return `<div class="q">${f.label}<br/>${(f.options || []).map((o) => `☐ ${o}`).join(' &nbsp;&nbsp; ')}</div>`;
    if (f.field_type === 'long_text') return `<div class="q">${f.label}<div class="box"></div></div>`;
    return `<div class="q">${f.label}: <span class="line"></span></div>`;
  }).join('');
  const sig = t.form_type === 'consent'
    ? `<div class="sigblock"><div class="sigtitle">CLIENT / EXAMINEE</div>
         <div class="q">Name: <span class="line"></span></div>
         <div class="q">Signature: <span class="line"></span></div>
         <div class="q">Date: <span class="line"></span></div></div>
       <div class="sigblock"><div class="sigtitle">LICENSED PSYCHOLOGIST / EXAMINER</div>
         <div class="q">Name: <span class="line"></span></div>
         <div class="q">License No.: <span class="line"></span></div>
         <div class="q">Signature: <span class="line"></span></div>
         <div class="q">Date: <span class="line"></span></div></div>`
    : `<div class="sig"><div>Signature over printed name</div><div>Date</div></div>`;
  w.document.write(`<!doctype html><html><head><title>${t.title}</title><style>
    body{font-family:Georgia,serif;max-width:680px;margin:40px auto;color:#111;line-height:1.6}
    h1{font-size:20px;text-align:center} .sub{text-align:center;font-size:12px;color:#555;margin-bottom:28px}
    h2{font-size:14px;margin:22px 0 6px} p{font-size:13px;margin:8px 0;text-align:justify}
    .q{margin:18px 0;font-size:14px} .line{display:inline-block;border-bottom:1px solid #111;min-width:320px}
    .box{border:1px solid #111;height:90px;margin-top:6px}
    .sig{margin-top:48px;display:flex;justify-content:space-between;font-size:13px}
    .sig div{border-top:1px solid #111;padding-top:4px;width:44%;text-align:center}
    .sigblock{margin-top:36px;font-size:13px} .sigtitle{font-weight:bold;margin-bottom:8px}
  </style></head><body>
    <h1>${t.title}</h1>
    <div class="sub">NACC – Regional Alternative Child Care Office I · Agency-authored form (v${t.version})</div>
    ${bodyHtml}
    ${lines}
    ${sig}
    <script>window.print();</` + `script></body></html>`);
  w.document.close();
}
```

- [ ] **Step 2: Switch Instruments.jsx to the util**

In `frontend/src/pages/Instruments.jsx`:
1. Add import near the other imports: `import { printBlankForm } from '../utils/printForm';`
2. Delete the whole local `printBlank` function (the block starting with the comment `// Print a blank copy of an agency form` through its closing `};`).
3. At the printer button (~line 208) change `onClick={() => printBlank(t)}` to `onClick={() => printBlankForm(t)}`.

- [ ] **Step 3: Verify the build**

Run (from `frontend/`): `npm run build`
Expected: builds with no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/utils/printForm.js frontend/src/pages/Instruments.jsx
git commit -m "feat(forms): shared blank-form print with body text, sections, consent signature blocks"
```

---

### Task 5: Frontend — builder support for `body` and `section` fields

**Files:**
- Modify: `frontend/src/pages/Instruments.jsx` (constants lines 23–33, template editor drawer ~lines 268–300, `saveTemplate` payload ~line 85)

**Interfaces:**
- Consumes: `body` on the template API (Task 1).
- Produces: the Agency Form editor can author exactly what Task 3 seeds (prose body + section headings), so admins can maintain the official forms in-app.

- [ ] **Step 1: Add the `section` field type and `body` to the empty template**

In `frontend/src/pages/Instruments.jsx`:

`FIELD_TYPES` (line 23) — add a first entry:

```js
const FIELD_TYPES = [
  { v: 'section', label: 'Section heading' },
  { v: 'text', label: 'Short text' },
  { v: 'long_text', label: 'Long text' },
  { v: 'date', label: 'Date' },
  { v: 'yes_no', label: 'Yes / No' },
  { v: 'choice', label: 'Choice list' },
];
```

`EMPTY_TEMPLATE` (line 33):

```js
const EMPTY_TEMPLATE = { form_type: 'consent', title: '', body: '', fields: [blankField()], attestation: false };
```

- [ ] **Step 2: Add the Document text textarea to the editor drawer**

Directly after the Title `FormField` in the template drawer (after the line `<FormField label="Title" required>…</FormField>`), insert:

```jsx
              <FormField label="Document text" hint="Optional. Shown before the fields on screen and in print. Lines starting with '## ' become section headings.">
                <textarea value={tpl.body || ''} onChange={(e) => setTpl({ ...tpl, body: e.target.value })} rows={8}
                  style={{ width: '100%', resize: 'vertical', padding: '11px 13px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-strong)', fontFamily: 'var(--font-sans)', fontSize: 13.5, lineHeight: 1.55 }} />
              </FormField>
```

- [ ] **Step 3: Send `body` on save**

In `saveTemplate` (~line 85), add `body` to the payload:

```js
    const payload = {
      form_type: tpl.form_type, title: tpl.title, body: tpl.body || '', attestation: true,
```

(keep the rest of the existing payload lines unchanged).

- [ ] **Step 4: Verify the build**

Run (from `frontend/`): `npm run build` → no errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Instruments.jsx
git commit -m "feat(forms): builder support for document text and section headings"
```

---

### Task 6: Frontend — Consent step shows the document + print button

**Files:**
- Modify: `frontend/src/pages/PreAssessment.jsx` (imports line ~3–5, add `FormBody` helper component near the top, `ConsentStep` component lines ~230–306)

**Interfaces:**
- Consumes: `printBlankForm` (Task 4), template `body` from the API (Task 1).
- Produces: `FormBody({ body })` component — Task 7 reuses it in the Interview step. Keep it a top-level function in this same file.

- [ ] **Step 1: Add import + `FormBody` helper**

In `frontend/src/pages/PreAssessment.jsx`, add to the imports:

```js
import { printBlankForm } from '../utils/printForm';
```

Add this top-level component after the `textarea` style const (line ~9):

```jsx
function FormBody({ body }) {
  if (!body) return null;
  return (
    <div className="racco-scroll" style={{ maxHeight: 260, overflowY: 'auto', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: '14px 16px', background: 'var(--ink-50)', marginBottom: 14 }}>
      {body.split('\n').map((line, i) => {
        const s = line.trim();
        if (!s) return null;
        if (s.startsWith('## ')) return <div key={i} style={{ fontWeight: 800, fontSize: 12.5, color: 'var(--text-strong)', margin: '12px 0 4px', letterSpacing: '0.02em' }}>{s.slice(3)}</div>;
        return <p key={i} style={{ fontSize: 12.5, color: 'var(--text-muted)', margin: '0 0 8px', lineHeight: 1.6 }}>{s}</p>;
      })}
    </div>
  );
}
```

- [ ] **Step 2: Show the selected consent document + print button in `ConsentStep`**

In `ConsentStep` ("Record new" mode), the template picker currently reads:

```jsx
          <FormField label="Consent form template" hint="Your agency-authored consent form.">
```

Directly **after** that entire `FormField` (its closing tag), insert:

```jsx
          {form.template && (() => {
            const sel = templates.find((t) => String(t.id) === String(form.template));
            if (!sel) return null;
            return (
              <div style={{ marginBottom: 4 }}>
                <FormBody body={sel.body} />
                <Button variant="ghost" onClick={() => printBlankForm(sel)} iconLeft={<Icon name="printer" size={15} />}>
                  Print blank form
                </Button>
              </div>
            );
          })()}
```

- [ ] **Step 3: Verify the build**

Run (from `frontend/`): `npm run build` → no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/PreAssessment.jsx
git commit -m "feat(pre-assessment): show consent document text + print blank form"
```

---

### Task 7: Frontend — Interview step: sections, respondent, multi-respondent saves

**Files:**
- Modify: `frontend/src/pages/PreAssessment.jsx` (`InterviewStep` component, lines ~308–364)

**Interfaces:**
- Consumes: `FormBody` (Task 6), `respondent` on `POST /api/interviews/` (Task 1), `section` field type in template `fields` (Task 3 seeds them).
- Produces: interview records with `respondent` set; the pre-assessment links the FIRST saved interview id via the existing `onDone(id)` callback (parent behavior unchanged).

- [ ] **Step 1: Replace the `InterviewStep` component**

Replace the entire existing `InterviewStep` function with:

```jsx
const RESPONDENT_OPTIONS = ['Custodian/PAP', 'Child', 'Guardian', 'Other…'];

function InterviewStep({ child, templates, onDone, setError }) {
  const [templateId, setTemplateId] = useState('');
  const [answers, setAnswers] = useState({});
  const [respondent, setRespondent] = useState('');
  const [respondentOther, setRespondentOther] = useState('');
  const [firstSavedId, setFirstSavedId] = useState(null);
  const [savedCount, setSavedCount] = useState(0);
  const tpl = templates.find((t) => String(t.id) === String(templateId));

  const respondentValue = respondent === 'Other…' ? respondentOther.trim() : respondent;

  const saveRecord = async () => {
    const { data } = await api.post('/interviews/', {
      child: child.id, template: templateId || null, answers,
      respondent: respondentValue,
    });
    if (firstSavedId === null) setFirstSavedId(data.id);
    setSavedCount((n) => n + 1);
    return data;
  };

  const resetForm = () => { setTemplateId(''); setAnswers({}); setRespondent(''); setRespondentOther(''); };

  const saveAndAnother = async () => {
    setError('');
    try { await saveRecord(); resetForm(); }
    catch (err) { setError(JSON.stringify(err.response?.data || 'Could not save the interview.')); }
  };

  const saveAndContinue = async () => {
    setError('');
    try {
      const data = await saveRecord();
      onDone(firstSavedId ?? data.id);
    } catch (err) {
      setError(JSON.stringify(err.response?.data || 'Could not save the interview.'));
    }
  };

  return (
    <Card eyebrow="Step 3" title="Clinical interview" padding="22px">
      <p style={{ fontSize: 13, color: 'var(--text-muted)', margin: '0 0 14px' }}>
        Record the answers to your own Clinical Interview form, or skip if not conducted today.
        {savedCount > 0 && <strong> {savedCount} interview{savedCount > 1 ? 's' : ''} saved this session.</strong>}
      </p>
      <FormField label="Interview form template">
        <Select value={templateId} onChange={(e) => { setTemplateId(e.target.value); setAnswers({}); }}>
          <option value="">— Select template —</option>
          {templates.map((t) => <option key={t.id} value={t.id}>{t.title} (v{t.version})</option>)}
        </Select>
      </FormField>
      {tpl && (
        <>
          <FormBody body={tpl.body} />
          <FormField label="Respondent" hint="Who is answering this interview.">
            <Select value={respondent} onChange={(e) => setRespondent(e.target.value)}>
              <option value="">—</option>
              {RESPONDENT_OPTIONS.map((r) => <option key={r}>{r}</option>)}
            </Select>
          </FormField>
          {respondent === 'Other…' && (
            <FormField label="Respondent (other)">
              <Input value={respondentOther} onChange={(e) => setRespondentOther(e.target.value)} placeholder="e.g. Teacher" />
            </FormField>
          )}
        </>
      )}
      {tpl && (tpl.fields || []).map((f, idx) => (
        f.field_type === 'section' ? (
          <div key={`${f.label}-${idx}`} style={{ fontWeight: 800, fontSize: 12.5, color: 'var(--text-strong)', margin: '18px 0 6px', letterSpacing: '0.03em', textTransform: 'uppercase' }}>{f.label}</div>
        ) : (
        <FormField key={`${f.label}-${idx}`} label={f.label}>
          {f.field_type === 'long_text' ? (
            <textarea value={answers[f.label] || ''} onChange={(e) => setAnswers({ ...answers, [f.label]: e.target.value })} rows={3} style={textarea} />
          ) : f.field_type === 'date' ? (
            <Input type="date" value={answers[f.label] || ''} onChange={(e) => setAnswers({ ...answers, [f.label]: e.target.value })} />
          ) : f.field_type === 'yes_no' ? (
            <Select value={answers[f.label] || ''} onChange={(e) => setAnswers({ ...answers, [f.label]: e.target.value })}>
              <option value="">—</option><option>Yes</option><option>No</option>
            </Select>
          ) : f.field_type === 'choice' ? (
            <Select value={answers[f.label] || ''} onChange={(e) => setAnswers({ ...answers, [f.label]: e.target.value })}>
              <option value="">—</option>
              {(f.options || []).map((o) => <option key={o}>{o}</option>)}
            </Select>
          ) : (
            <Input value={answers[f.label] || ''} onChange={(e) => setAnswers({ ...answers, [f.label]: e.target.value })} />
          )}
        </FormField>
        )
      ))}
      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 14 }}>
        <Button variant="ghost" onClick={() => onDone(firstSavedId)}>
          {savedCount > 0 ? 'Continue' : 'Skip for now'}
        </Button>
        <Button variant="ghost" onClick={saveAndAnother} disabled={!templateId}>
          Save & interview another respondent
        </Button>
        <Button variant="primary" onClick={saveAndContinue} disabled={!templateId} iconLeft={<Icon name="save" size={16} />}>
          Save interview & continue
        </Button>
      </div>
    </Card>
  );
}
```

Notes on intent: `onDone(firstSavedId)` on the ghost button means "skip" (`null`) when nothing was saved, and "continue, linking the first interview" after "Save & interview another respondent" was used. The parent's `onDone` handler already handles both `null` and an id — do not change it. The `${f.label}-${idx}` keys replace the old `f.label` keys because section headings may repeat label text.

- [ ] **Step 2: Verify the build**

Run (from `frontend/`): `npm run build` → no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/PreAssessment.jsx
git commit -m "feat(pre-assessment): sectioned interviews, respondent label, multi-respondent saves"
```

---

### Task 8: Chart respondent column + full verification

**Files:**
- Modify: `frontend/src/pages/ChildProgressReport.jsx` (pre-assessments table, lines ~244–259)
- Verify: whole backend suite + frontend build + seeded dev DB

**Interfaces:**
- Consumes: `interview_respondent` on `PreAssessmentSerializer` (Task 1), seeded templates in the dev DB (Task 3 Step 5).
- Produces: the child chart's pre-assessment table shows an Interview column with the respondent label.

- [ ] **Step 1: Add the Interview column**

In `frontend/src/pages/ChildProgressReport.jsx`, the pre-assessments table header currently reads:

```jsx
                {['Date', 'Status', 'Consent', 'Instrument Titles', 'Psychologist'].map((h) => (
```

Change the array to:

```jsx
                {['Date', 'Status', 'Consent', 'Interview', 'Instrument Titles', 'Psychologist'].map((h) => (
```

In the body row, after the consent cell (`<td style={td}>{p.consent ? (p.consent_status || 'linked') : '—'}</td>`), insert:

```jsx
                    <td style={td}>{p.interview ? (p.interview_respondent || 'recorded') : '—'}</td>
```

- [ ] **Step 2: Full backend suite**

Run (from `backend/`): `./venv/Scripts/python.exe manage.py test`
Expected: OK — 216 tests (208 pre-existing + 8 new), 0 failures.

- [ ] **Step 3: Frontend build**

Run (from `frontend/`): `npm run build` → no errors.

- [ ] **Step 4: Confirm the dev DB is seeded**

Run (from `backend/`): `./venv/Scripts/python.exe manage.py seed_agency_forms`
Expected: three `Exists, skipped: …` lines (created in Task 3 Step 5).

- [ ] **Step 5: Commit + push**

```bash
git add frontend/src/pages/ChildProgressReport.jsx
git commit -m "feat(chart): interview respondent column on pre-assessment history"
git push origin main
```
