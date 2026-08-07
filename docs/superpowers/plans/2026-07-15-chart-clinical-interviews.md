# Chart Clinical Interviews Section Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every `ClinicalInterviewRecord` of a child (including secondary "Save & interview another respondent" records) becomes visible on the child chart page, in a new "Clinical interviews" section with expandable answers.

**Architecture:** The child-chart endpoint (`ChildReportView` in `backend/clinical/reports_views.py`) gains an `interviews` key serialized with the existing `ClinicalInterviewRecordSerializer`, scoped by the same carry-history rule as the other record types (a psychologist without history sees only interviews they conducted). The frontend chart page (`frontend/src/pages/ChildProgressReport.jsx`) renders the list in a new Card between the Pre-assessment log and the Opinionnaire section.

**Tech Stack:** Django REST Framework (backend), React + inline-styled RACCO UI primitives (frontend). No new dependencies, no migrations (model and serializer already exist).

**Context:** Closes the backlog item flagged in the final review of the 2026-07-14 "real agency forms" feature (spec §4.5: "Wherever clinical interviews are listed on the child chart, show the respondent"). Today only the interview linked via `PreAssessment.interview` FK is visible (as a column); secondary respondent records have no read path.

## Global Constraints

- Repo root: `C:\Users\User\Desktop\NACC SYS\NACC-V2` (note the space in the path — always quote it). Branch `main`. This is where ALL work happens.
- **Do NOT commit.** The controller reviews the diff and commits. (Repo convention: commits are authored solely by the user, never with a Claude co-author trailer.)
- **Never run `git add -A` / `git add .`** — the working tree contains an unrelated local edit to `frontend/src/components/Sidebar.jsx` that must remain uncommitted and untouched.
- TDD is mandatory for the backend task: write the failing tests, run them to watch them fail, then implement.
- Backend test command (run from `backend/`): `./venv/Scripts/python.exe manage.py test clinical.tests.test_reports -v 1` (Git Bash) — the venv python is invoked directly, never activated.
- Frontend has no test harness; verification is `npm run build` from `frontend/` (must exit 0).
- Response key is exactly `interviews`; serializer is the existing `ClinicalInterviewRecordSerializer` — do not create a new serializer.
- Respondent select options used by the wizard (for reference): `Custodian/PAP`, `Child`, `Guardian`, `Other…` (free text). `respondent` may be blank (`""`).

---

### Task 1: Backend — `interviews` in the child chart bundle

**Files:**
- Modify: `backend/clinical/tests/test_reports.py` (imports at top + new test class at the end)
- Modify: `backend/clinical/reports_views.py:17-21` (serializer import), `:42-58` (queryset + carry-history), `:60-70` (response dict)

**Interfaces:**
- Consumes: `ClinicalInterviewRecordSerializer` (exists in `clinical/serializers.py`, fields: `id, child, child_name, template, template_title, answers, respondent, interviewer, interviewer_name, date, created_at`); `Child.clinical_interviews` related manager; `Child.assignee_sees_history` flag.
- Produces: `GET /api/reports/child/<id>/` response gains `"interviews"`: a list of the child's `ClinicalInterviewRecord`s (newest first per model Meta ordering `["-date", "-id"]`), carry-history-scoped by `interviewer=request.user`. Task 2's frontend consumes `data.interviews` with fields `id, respondent, template_title, interviewer_name, date, answers`.

- [ ] **Step 1: Write the failing tests**

In `backend/clinical/tests/test_reports.py`, extend the models import (line 5) to:

```python
from clinical.models import (
    AgencyFormTemplate, ClinicalInterviewRecord, InstrumentCatalog,
    PreAssessment, ResultEntry, RemarkNote,
)
```

Append this test class at the end of the file:

```python
class ChildReportInterviewsTest(ReportsBase):
    """The chart bundle must list EVERY ClinicalInterviewRecord of the child —
    not just the one linked to a PreAssessment via its `interview` FK."""

    def setUp(self):
        super().setUp()
        self.template = AgencyFormTemplate.objects.create(
            form_type="clinical_interview",
            title="Adoption Pre-Assessment Questionnaire — Child",
            owner=self.psy, attestation=True)
        pa = self.child.pre_assessments.first()
        self.primary = ClinicalInterviewRecord.objects.create(
            child=self.child, respondent="Custodian/PAP", interviewer=self.psy,
            answers={"Reason for adoption": "Kinship adoption, long planned."})
        pa.interview = self.primary
        pa.save()
        # Secondary respondent: exists ONLY as a ClinicalInterviewRecord.
        self.secondary = ClinicalInterviewRecord.objects.create(
            child=self.child, template=self.template, respondent="Child",
            interviewer=self.psy,
            answers={"How do you feel about the family?": "Happy."})

    def test_bundle_lists_all_interviews_not_just_the_linked_one(self):
        self._auth("p@racco1.gov.ph")
        resp = self.client.get(f"/api/reports/child/{self.child.id}/")
        self.assertEqual(resp.status_code, 200)
        ids = {i["id"] for i in resp.data["interviews"]}
        self.assertEqual(ids, {self.primary.id, self.secondary.id})

    def test_interview_rows_carry_display_fields(self):
        self._auth("p@racco1.gov.ph")
        resp = self.client.get(f"/api/reports/child/{self.child.id}/")
        row = next(i for i in resp.data["interviews"] if i["id"] == self.secondary.id)
        self.assertEqual(row["respondent"], "Child")
        self.assertEqual(row["template_title"],
                         "Adoption Pre-Assessment Questionnaire — Child")
        self.assertEqual(row["answers"], {"How do you feel about the family?": "Happy."})
        self.assertIn("interviewer_name", row)
        self.assertIn("date", row)

    def test_carry_history_off_scopes_interviews_to_own(self):
        self.child.assigned_psychologist = self.other
        self.child.assignee_sees_history = False
        self.child.save()
        mine = ClinicalInterviewRecord.objects.create(
            child=self.child, respondent="Guardian", interviewer=self.other)
        self._auth("o@racco1.gov.ph")
        resp = self.client.get(f"/api/reports/child/{self.child.id}/")
        self.assertEqual([i["id"] for i in resp.data["interviews"]], [mine.id])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run (from `backend/`): `./venv/Scripts/python.exe manage.py test clinical.tests.test_reports.ChildReportInterviewsTest -v 1`
Expected: 3 FAILURES/ERRORS — `KeyError: 'interviews'` (the response has no such key yet). If they fail for any other reason (import error, model kwarg typo), fix the test, not the view, and re-run.

- [ ] **Step 3: Implement the view change**

In `backend/clinical/reports_views.py`:

(a) Extend the serializers import (lines 17–21) with `ClinicalInterviewRecordSerializer`:

```python
from clinical.serializers import (
    PreAssessmentSerializer, ResultEntrySerializer, RemarkNoteSerializer,
    TreatmentPlanSerializer, PsychologicalReportSerializer, ProblemEntrySerializer,
    CaseStudySerializer, OpinionnaireInviteSerializer, ClinicalInterviewRecordSerializer,
)
```

(b) After the `opinionnaires = ...` line (line 49), add:

```python
        interviews = child.clinical_interviews.select_related("template", "interviewer")
```

(c) Inside the existing carry-history `if` block (after `files = files.filter(author=request.user)`, line 58), add:

```python
            interviews = interviews.filter(interviewer=request.user)
```

(d) In the response dict, after the `"pre_assessments"` entry, add:

```python
            "interviews": ClinicalInterviewRecordSerializer(interviews, many=True).data,
```

(e) Update the class docstring (line 29–30) to mention interviews: `"""Chart view of one child: profile + pre-assessment log + clinical interviews + result entries + report files + remarks + treatment plan + open problems."""`

- [ ] **Step 4: Run the new tests to verify they pass**

Run: `./venv/Scripts/python.exe manage.py test clinical.tests.test_reports.ChildReportInterviewsTest -v 1`
Expected: `OK` (3 tests).

- [ ] **Step 5: Run the whole reports module, then the full suite**

Run: `./venv/Scripts/python.exe manage.py test clinical.tests.test_reports -v 1`
Expected: OK, no regressions.
Run: `./venv/Scripts/python.exe manage.py test`
Expected: `OK` — 221 tests (218 existing + 3 new), zero failures.

- [ ] **Step 6: Report** — do NOT commit; report status, test output summary, and files touched.

---

### Task 2: Frontend — "Clinical interviews" section on the child chart

**Files:**
- Modify: `frontend/src/pages/ChildProgressReport.jsx` (one new state hook + one new Card section)

**Interfaces:**
- Consumes: `data.interviews` from Task 1 — array of `{ id, respondent, template_title, interviewer_name, date, answers }` where `answers` is an object `{question: answer}` and `respondent`/`template_title`/`interviewer_name` may be empty/null. Existing imports already available in the file: `Card, Button, Badge, Icon` from `../ui`.
- Produces: visual section only; nothing downstream consumes it.

- [ ] **Step 1: Add expansion state**

Next to the other `useState` hooks (after line 36, `const [surveyTemplates, ...]`), add:

```jsx
  const [openInterviews, setOpenInterviews] = useState({}); // interview id -> expanded?
```

- [ ] **Step 2: Add the section markup**

Insert this Card immediately AFTER the closing `</Card>` of the "Pre-assessment log" section (line 265) and BEFORE the `{/* Child opinionnaire (QR survey) */}` comment:

```jsx
      {/* Clinical interviews — every respondent, incl. secondary "Save & interview another" records */}
      <Card eyebrow="Clinical workflow" title="Clinical interviews" padding="0" style={{ marginBottom: 18 }}>
        {(data.interviews || []).length === 0 ? (
          <div style={{ padding: 18, fontSize: 13, color: 'var(--text-muted)' }}>
            No clinical interviews recorded yet — they are conducted in the pre-assessment wizard.
          </div>
        ) : (
          <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 8 }}>
            {data.interviews.map((iv) => {
              const entries = Object.entries(iv.answers || {}).filter(([, a]) => String(a ?? '').trim() !== '');
              const open = !!openInterviews[iv.id];
              return (
                <div key={iv.id} style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: 14, background: 'var(--ink-50)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
                    <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                      <Badge tone="brand" size="sm">{iv.respondent || 'Respondent not recorded'}</Badge>
                      <span style={{ fontWeight: 700, fontSize: 13.5, color: 'var(--text-strong)' }}>{iv.template_title || 'Free-form interview'}</span>
                    </div>
                    <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                      <span style={{ fontSize: 11.5, color: 'var(--text-faint)' }}>{iv.date} · {iv.interviewer_name || '—'}</span>
                      {entries.length > 0 && (
                        <Button variant="ghost" className="racco-no-print"
                          onClick={() => setOpenInterviews((s) => ({ ...s, [iv.id]: !s[iv.id] }))}
                          iconLeft={<Icon name={open ? 'chevron-up' : 'chevron-down'} size={14} />}>
                          {open ? 'Hide answers' : `Answers (${entries.length})`}
                        </Button>
                      )}
                    </div>
                  </div>
                  {entries.length === 0 && (
                    <div style={{ fontSize: 12, color: 'var(--text-faint)', marginTop: 6 }}>No written answers recorded.</div>
                  )}
                  {open && entries.length > 0 && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 10 }}>
                      {entries.map(([q, a]) => (
                        <div key={q} style={{ fontSize: 13, lineHeight: 1.5 }}>
                          <span style={{ color: 'var(--text-muted)', fontWeight: 600 }}>{q}</span>{' '}
                          <span style={{ color: 'var(--text-strong)' }}>— {a}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </Card>
```

Style notes (match the file's idiom): the row container copies the opinionnaire/result-entry card pattern (`border`, `radius-lg`, `ink-50` background); the Q&A rendering copies the opinionnaire answers pattern (lines 295-300); `racco-no-print` on the toggle button keeps print output clean. `Icon` renders lucide-react icons by kebab-case name — `chevron-up`/`chevron-down` are valid.

- [ ] **Step 3: Build to verify**

Run (from `frontend/`): `npm run build`
Expected: exit 0, no errors (warnings pre-existing at most).

- [ ] **Step 4: Report** — do NOT commit; report status, build output tail, and files touched.

---

### Task 3 (controller, not a subagent): verify live, commit, push

- [ ] Review Task 1 diff → commit `feat(chart): list all clinical interviews in child report bundle` (stage only `backend/clinical/reports_views.py` and `backend/clinical/tests/test_reports.py`).
- [ ] Review Task 2 diff → commit `feat(chart): clinical interviews section with expandable answers` (stage only `frontend/src/pages/ChildProgressReport.jsx`; plan doc may ride along in either commit).
- [ ] Live check: seed one secondary interview for dev child 2 if needed, load `/reports/child/2` in the browser pane, confirm the section renders both respondents and answers expand.
- [ ] `git push origin main` (durably authorized), leave `Sidebar.jsx` local edit untouched.
- [ ] Append ledger lines to `.superpowers/sdd/progress.md`.

## Self-Review Notes

- Spec coverage: backend key + carry-history scoping (task prompt) → Task 1; section with date/respondent badge/template title/interviewer/expandable answers (task prompt + spec §4.5 respondent display) → Task 2. No gaps found.
- Placeholder scan: none — all steps carry complete code and exact commands.
- Type consistency: frontend consumes exactly the serializer fields Task 1's Interfaces block lists (`id, respondent, template_title, interviewer_name, date, answers`); key `interviews` used consistently.
