# Real Agency Forms: Adoption Informed Consent + Pre-Assessment Questionnaires

**Date:** 2026-07-14
**Status:** Approved (approach B — light model extension + faithful seeds)
**Source documents (agency-authored, provided by the partner psychologist):**
- `Adoption-INFORMED-CONSENT-FOR-PSYCHOLOGICAL-EVALUATION (1).docx`
- `Pre-assessment (1).docx` (contains TWO questionnaires: Custodian/PAP + Child)

Copies of both source documents are stored in `docs/agency-forms/` for provenance.

---

## 1. Goal

Integrate the agency's two real documents into the clinical workflow where they
naturally belong:

| Document | Becomes | Used in |
|---|---|---|
| Informed Consent for Psychological Evaluation (Adoption) | one `AgencyFormTemplate` with `form_type="consent"` | Pre-assessment wizard → Consent step; printable blank from `/instruments` |
| Adoption Pre-Assessment Questionnaire — Custodian/PAP | one `AgencyFormTemplate` with `form_type="clinical_interview"` | Pre-assessment wizard → Interview step |
| Adoption Pre-Assessment Questionnaire — Child | one `AgencyFormTemplate` with `form_type="clinical_interview"` | Pre-assessment wizard → Interview step |

**Copyright validity:** both documents are agency/psychologist-authored — not
published assessment instruments — so full digitization is inside the copyright
boundary that defines V2. All three templates seed with `attestation=True`.

The templates are available for **all case types** (not restricted to
Adoption); the psychologist chooses when to use them.

## 2. Model changes (`clinical` app, one migration)

### 2.1 `AgencyFormTemplate.body` — new field
- `body = models.TextField(blank=True, default="")`
- Holds document prose (the consent's 10 legal sections; the child
  questionnaire's age note). Plain text; **lines starting with `## ` render as
  section headings** in the UI and in print. Blank lines separate paragraphs.
  No markdown library — split on newlines, check the `## ` prefix.
- Serializer: add `body` to `AgencyFormTemplateSerializer.Meta.fields`.
  A change to `body` bumps `version` exactly like a change to `fields`
  (extend the existing condition in `update()`).

### 2.2 `ClinicalInterviewRecord.respondent` — new field
- `respondent = models.CharField(max_length=100, blank=True, default="")`
- Free-text label for who answered (e.g. `"Custodian/PAP"`, `"Child"`,
  `"Guardian"`). Add to `ClinicalInterviewRecordSerializer` fields
  (writable). Displayed anywhere interviews are listed (child chart).

### 2.3 `section` field type (no schema change)
- `fields` JSON entries may now use `"field_type": "section"`: the `label` is
  a section heading, there is **no input** and no answer key for it.
- Backend: `fields` is a free JSON list already — no validation change needed.
- All three renderers must handle it (builder, InterviewStep, print — §4).

### 2.4 Agency-wide (shared) templates
Seeded official forms have `owner=None` and must be visible to psychologists,
but `AgencyFormTemplateViewSet.get_queryset()` currently filters
psychologists to `owner=self.request.user` only.

- **Read:** psychologists see `Q(owner=user) | Q(owner__isnull=True)`.
  Other psychologists' templates stay invisible to them (queryset-scoped →
  404, which avoids leaking their existence).
- **Write:** psychologists may modify/deactivate **only templates they own**;
  attempts on shared (`owner=None`) templates → 403. Implement as an
  object-level check in the viewset (update / partial_update / destroy /
  `deactivate` action). Admins are unrestricted (unchanged).
- **Owner reassignment is admin-only:** a psychologist's `owner` value on
  create AND update is forced to themselves (silently ignored if supplied),
  so they can never promote a template into the shared pool or hand it to
  another user.

## 3. Seed command

`python manage.py seed_agency_forms` (new, in
`backend/clinical/management/commands/`).

- **Idempotent via `get_or_create`** keyed on `(form_type, title)` — re-running
  never clobbers subsequent in-app edits. Prints created/skipped per template.
- All three: `owner=None`, `attestation=True`, `attested_at=timezone.now()`,
  `active=True`, `version=1`.
- Question text is transcribed faithfully, with obvious source typos fixed
  (`"enjpy"` → `"enjoy"`; the child questionnaire numbers two sections "VII" —
  Self-Concept becomes VIII).

### 3.1 Template 1 — consent
- `form_type="consent"`, title
  **"Informed Consent for Psychological Evaluation (Adoption)"**.
- `fields=[]` (signer details are captured by `ConsentRecord` itself; the
  document is prose + signatures, not form inputs).
- `body` = the full document text with `## ` headings, structured exactly as:

```
(Intro paragraph: "This Informed Consent Form is executed by the undersigned
individual (hereinafter referred to as the Client/Examinee) who has voluntarily
agreed to undergo a psychological evaluation in connection with adoption
proceedings, in accordance with applicable laws, rules, and regulations of the
Republic of the Philippines.")

## I. PURPOSE OF THE PSYCHOLOGICAL EVALUATION
## II. NATURE AND SCOPE OF THE EVALUATION
## III. VOLUNTARY PARTICIPATION
## IV. CONFIDENTIALITY AND LIMITATIONS OF CONFIDENTIALITY
## V. RISKS AND DISCOMFORTS
## VI. BENEFITS
## VII. FEES AND PAYMENT
## VIII. ACCURACY AND COOPERATION
## IX. QUESTIONS AND CLARIFICATIONS
## X. CONSENT
```

Each heading is followed by its full paragraph text from the source document.
The exact, ready-to-use body text sits between the `BODY BEGIN`/`BODY END`
markers in `docs/agency-forms/informed-consent-adoption-extracted.md` — use it
verbatim (sections II and X contain their bullet lists as plain lines).

### 3.2 Template 2 — Custodian/PAP questionnaire
- `form_type="clinical_interview"`, title
  **"Adoption Pre-Assessment Questionnaire — Custodian/PAP"**, `body=""`.
- `fields`: 9 `section` entries interleaved with `long_text` questions, in
  document order:

| Section | Questions (all `long_text`) |
|---|---|
| I. Background Information | Please tell me about yourself and your relationship with the child. · How long has the child been under your care? · Can you describe how the child came into your custody? · What were the circumstances that led to the proposed adoption? |
| II. Developmental History | What do you know about the child's pregnancy and birth? · Were there any medical or developmental concerns during infancy or early childhood? · Did the child reach developmental milestones (walking, talking, toilet training) on time? · Has the child experienced any serious illness, hospitalization, or disability? |
| III. Family History | What can you tell me about the child's birth parents? · How often did the child have contact with his/her birth parents? · What was the quality of their relationship? · Does the child ask about his/her biological parents? · How does the child react when they are mentioned? |
| IV. Emotional and Behavioral Functioning | How would you describe the child's personality? · What are the child's strengths? · What behaviors concern you? · How does the child express happiness, sadness, anger, or fear? · How does the child cope with disappointment or frustration? · Has the child experienced any traumatic events? · How did the child respond to these experiences? |
| V. Social Functioning | How does the child interact with family members? · How does the child interact with peers? · Does the child easily make friends? · Does the child have difficulty trusting adults or other children? · How does the child respond to authority figures? |
| VI. Academic Functioning | How is the child performing in school? · What are the child's favorite subjects? · Has the child experienced behavioral or learning difficulties in school? · How do teachers describe the child? |
| VII. Daily Living Skills | Can the child independently perform age-appropriate self-care activities? · What household responsibilities does the child have? · How does the child spend free time? |
| VIII. Relationship with Prospective Adoptive Parent(s) | How did the child first meet the prospective adoptive parent(s)? · Describe their relationship. · How does the child behave when around them? · Does the child seek comfort from them? · Have you noticed positive changes since they became involved? · Has the child expressed feelings about the planned adoption? |
| IX. Adjustment and Readiness | How do you think the child will adjust to the adoptive family? · What challenges do you anticipate? · What support do you believe the child will need? · Is there anything else you think is important for me to know about the child? |

### 3.3 Template 3 — Child questionnaire
- `form_type="clinical_interview"`, title
  **"Adoption Pre-Assessment Questionnaire — Child"**.
- `body` = "Some questions may not be answered depending on the child's age."
- `fields` (same section/long_text pattern):

| Section | Questions |
|---|---|
| I. Home and Family | Who do you live with? · Tell me about the people at home. · Who takes care of you? · What do you like most about living with them? · Is there anything you don't like? |
| II. School | What grade are you in? · What do you like about school? · What subjects do you enjoy and least enjoy? · Who are your friends in school? |
| III. Feelings | What makes you happy? · What makes you sad? · What makes you angry? · When you are upset, what do you usually do? · Who do you talk to when you have problems? |
| IV. Relationships | Who are the people you feel closest to? · Who makes you feel safe? · Who do you enjoy spending time with? · Is there someone you miss? |
| V. Biological Parents (if developmentally appropriate) | What do you know about your mother? · What do you know about your father? · Do you remember them? · How do you feel when you think about them? · Do you have any questions about them? |
| VI. Prospective Adoptive Parent(s) | Can you tell me about (name of adoptive parent)? · What do you like doing together? · How do they make you feel? · Do you feel safe with them? · If you are sick or scared, would you go to them? · What do you think about living with them? |
| VII. Understanding of Adoption (if adoption has already been disclosed) | Has anyone talked to you about adoption? · What do you think adoption means? · How do you feel about being adopted? · Is there anything that worries you? · What are you hoping for in your future family? |
| VIII. Self-Concept | Can you tell me three things you like about yourself? · What are you good at? · What do you want to be when you grow up? · If you could wish for three things, what would they be? |

## 4. Frontend changes

### 4.1 Shared print utility
Extract `printBlank` out of `Instruments.jsx` into
`frontend/src/utils/printForm.js` so both `/instruments` and the wizard's
Consent step use one implementation. Enhancements:

- Render `body` first: `## ` lines as `<h2>`, other non-empty lines as `<p>`.
- `field_type === "section"` renders as an `<h2>` heading (no input line).
- **Consent forms** (`form_type === "consent"`) replace the current single
  generic signature row with the document's two signature blocks:
  - **CLIENT / EXAMINEE** — Name / Signature / Date lines
  - **LICENSED PSYCHOLOGIST / EXAMINER** — Name / License No. / Signature / Date lines
- Non-consent forms keep the existing single signature row.

### 4.2 `Instruments.jsx` (builder)
- Template editor gains a **"Document text"** textarea bound to `body`, with
  hint: *"Optional. Shown before the fields on screen and in print. Lines
  starting with '## ' become section headings."*
- Field type dropdown gains **"Section heading"** (`section`); when selected,
  the options editor is hidden (same as text).

### 4.3 `PreAssessment.jsx` — Consent step
- When a consent template is selected, show its `body` (scrollable, headings
  styled) so the psychologist/signer can read the actual document on screen.
- Add a **"Print blank form"** button (uses the shared print utility) so the
  paper copy can be printed, signed, then recorded/scanned — matching the
  existing paper-first consent flow. No `ConsentRecord` schema change: the
  psychologist countersignature lives on the printed/scanned document.

### 4.4 `PreAssessment.jsx` — Interview step
- Render the template `body` (the child questionnaire's age note) as an info
  note above the questions.
- `section` fields render as bold section headings, not inputs.
- New **Respondent** input above the questions: a select with suggestions
  `Custodian/PAP`, `Child`, `Guardian`, `Other…` (Other reveals a free-text
  input). Sent as `respondent` on `POST /interviews/`. Optional.
- Unanswered questions stay allowed (age-gating) — already the case; keep it.
- **Multi-respondent:** new secondary button **"Save & interview another
  respondent"** — saves the current interview, resets template/respondent/
  answers, and stays on the step. The **first** saved interview id is the one
  linked to the pre-assessment (existing single FK, unchanged); later saves
  simply exist as `ClinicalInterviewRecord`s on the child. The primary
  **"Save interview & continue"** keeps its behavior (if an interview was
  already saved via "Save & interview another", continue links the first id).

### 4.5 Child chart
Wherever clinical interviews are listed on the child chart, show the
`respondent` label (e.g. a small badge "Custodian/PAP") when present.

## 5. Error handling / edge cases
- Seed re-run: `get_or_create` → zero duplicates, in-app edits preserved.
- Templates with `fields=[]` but a `body` (the consent): Interview/print
  renderers must not crash on empty fields; the consent template is only
  offered in consent contexts anyway (`?type=` filter already used).
- Psychologist PATCH/deactivate on a shared template → 403 with a clear
  message ("Official agency forms can only be edited by an administrator.").
- `section` entries never appear in `answers` (no input rendered).
- Print popup blocked (`window.open` returns null) — existing guard kept.

## 6. Testing (backend; keep the existing 208 green)
1. Migration adds `body` + `respondent` with correct defaults.
2. `seed_agency_forms` creates exactly 3 templates; running twice creates no
   duplicates and preserves an in-between edit.
3. Seeded consent template: `form_type="consent"`, `fields==[]`, body contains
   all ten `## ` headings; questionnaires: correct section/question counts
   (PAP: 9 sections + 42 questions; Child: 8 sections + 38 questions).
4. Psychologist template visibility: sees own + shared (`owner=None`), still
   cannot see another psychologist's; PATCH/deactivate on shared → 403; admin OK.
5. `respondent` round-trips through `POST /interviews/` and list output.
6. `body` edit bumps template `version` and requires re-attestation
   (same rule as `fields`).

## 7. Out of scope
- Per-case-type template filtering/suggestion.
- M2M `PreAssessment.interviews` remodel (single FK stays).
- Any change to `ConsentRecord` schema.
- OCR/import of the .docx files (content is transcribed in the seed command).
- The v1 repo — this is V2-only work.
