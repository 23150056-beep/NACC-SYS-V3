# Assessment-Taking Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the assessment wizard real — pick a child + a published questionnaire, answer its questions, and persist an `Assessment` with its `Response` rows, notes, and a manual classification.

**Architecture:** New `AssessmentViewSet` + a read-only `/active-questionnaires/` endpoint in the `assessments` app, gated by a new `CanTakeAssessments` permission kept separate from instrument management. The `Assessment.jsx` wizard is rewired to real data; scoring/AI stays a Phase-3 placeholder.

**Tech Stack:** Django + DRF (SQLite); React + Vite.

**Spec:** [2026-06-27-assessment-taking-flow-design.md](../specs/2026-06-27-assessment-taking-flow-design.md)

**Conventions:** Backend from `backend/` as `./venv/Scripts/python.exe manage.py <cmd>`. Commits omit any Claude co-author trailer. **Commits are deferred** — the executor holds them until the user asks; commit steps below are checkpoints.

---

## File Structure

**Modify (backend):** `assessments/models.py` (3 fields), `accounts/permissions.py` (`CanTakeAssessments`), `assessments/serializers.py` (assessment + response serializers), `assessments/views.py` (`AssessmentViewSet`, active-questionnaires view), `assessments/urls.py`, `assessments/tests/test_api.py`; new migration `0004_*`.
**Modify (frontend):** `src/pages/Assessment.jsx` (full rewire). No new files.

---

## Task 1: Assessment model fields

**Files:** Modify `backend/assessments/models.py`; Test `backend/assessments/tests/test_models.py`.

- [ ] **Step 1: Write the failing test**

Append to `backend/assessments/tests/test_models.py`:
```python
class AssessmentFieldsTest(TestCase):
    def test_assessment_has_questionnaire_notes_classification(self):
        from django.contrib.auth import get_user_model
        from accounts.models import Role
        from children.models import Child
        from assessments.models import Questionnaire, Assessment
        User = get_user_model()
        role = Role.objects.create(role_name=Role.PSYCHOLOGIST)
        psy = User.objects.create_user(email="p2@racco1.gov.ph", username="p2", password="x", role=role)
        child = Child.objects.create(fullname="Ana", case_type="Foster")
        qn = Questionnaire.objects.create(title="SDQ", status="active")
        a = Assessment.objects.create(
            child=child, psychologist=psy, questionnaire=qn,
            assessment_type="Intake", notes="Calm.", classification="Normal Development")
        self.assertEqual(a.questionnaire, qn)
        self.assertEqual(a.notes, "Calm.")
        self.assertEqual(a.classification, "Normal Development")
```

- [ ] **Step 2: Run it to verify failure**

Run: `./venv/Scripts/python.exe manage.py test assessments.tests.test_models.AssessmentFieldsTest -v 2`
Expected: FAIL (`questionnaire`/`notes`/`classification` don't exist).

- [ ] **Step 3: Add the fields**

In `backend/assessments/models.py`, update the `Assessment` class to add three fields (place them after `child`/`psychologist`):
```python
class Assessment(models.Model):
    child = models.ForeignKey(Child, on_delete=models.CASCADE, related_name="assessments")
    psychologist = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="assessments")
    questionnaire = models.ForeignKey(
        Questionnaire, on_delete=models.SET_NULL, null=True, blank=True, related_name="assessments")
    assessment_date = models.DateField(auto_now_add=True)
    assessment_type = models.CharField(max_length=50, blank=True)
    status = models.CharField(max_length=50, default="ongoing")
    notes = models.TextField(blank=True)
    classification = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tbl_assessment"
```

- [ ] **Step 4: Make migration and run the test**

Run: `./venv/Scripts/python.exe manage.py makemigrations assessments`
Expected: `0004_…` adding `questionnaire`, `notes`, `classification`.
Run: `./venv/Scripts/python.exe manage.py test assessments.tests.test_models -v 1`
Expected: OK.

- [ ] **Step 5: Commit (deferred — checkpoint only)**

```bash
git add backend/assessments/models.py backend/assessments/migrations/0004_*.py backend/assessments/tests/test_models.py
git commit -m "feat(assessments): add questionnaire link, notes, classification to Assessment"
```

---

## Task 2: Permission + serializers + endpoints

**Files:** Modify `backend/accounts/permissions.py`, `backend/assessments/serializers.py`, `backend/assessments/views.py`, `backend/assessments/urls.py`; Test append to `backend/assessments/tests/test_api.py`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/assessments/tests/test_api.py`:
```python
from assessments.models import Questionnaire, Question, Assessment, Response
from children.models import Child


class AssessmentTakingTest(QuestionnaireApiTest):
    def setUp(self):
        super().setUp()
        self.child = Child.objects.create(fullname="Ana Lopez", case_type="Foster")
        self.qn = Questionnaire.objects.create(title="SDQ", status="active")
        self.q1 = Question.objects.create(questionnaire=self.qn, question_text="Calm?", question_type="yes_no", order=1)
        self.q2 = Question.objects.create(questionnaire=self.qn, question_text="Sleeps?", question_type="rating_scale", order=2)
        self.draft = Questionnaire.objects.create(title="Draft one", status="draft")

    def _assessment_payload(self):
        return {
            "child": self.child.id, "questionnaire": self.qn.id, "assessment_type": "Intake",
            "classification": "Normal Development", "notes": "Adjusting well.",
            "responses": [
                {"question": self.q1.id, "answer": "Yes"},
                {"question": self.q2.id, "answer": "4"},
            ],
        }

    def test_active_questionnaires_lists_only_active(self):
        self._auth("p@racco1.gov.ph")
        resp = self.client.get("/api/active-questionnaires/")
        self.assertEqual(resp.status_code, 200)
        titles = [q["title"] for q in resp.data]
        self.assertIn("SDQ", titles)
        self.assertNotIn("Draft one", titles)

    def test_active_questionnaires_forbidden_for_staff(self):
        self._auth("s@racco1.gov.ph")
        self.assertEqual(self.client.get("/api/active-questionnaires/").status_code, 403)

    def test_psychologist_creates_assessment_with_responses(self):
        self._auth("p@racco1.gov.ph")
        resp = self.client.post("/api/assessments/", self._assessment_payload(), format="json")
        self.assertEqual(resp.status_code, 201)
        a = Assessment.objects.get()
        self.assertEqual(a.status, "completed")
        self.assertEqual(a.psychologist, self.psy)
        self.assertEqual(a.notes, "Adjusting well.")
        self.assertEqual(a.responses.count(), 2)

    def test_staff_cannot_create_assessment(self):
        self._auth("s@racco1.gov.ph")
        resp = self.client.post("/api/assessments/", self._assessment_payload(), format="json")
        self.assertEqual(resp.status_code, 403)

    def test_psychologist_lists_only_own_assessments(self):
        Assessment.objects.create(child=self.child, psychologist=self.admin, status="completed")
        self._auth("p@racco1.gov.ph")
        self.client.post("/api/assessments/", self._assessment_payload(), format="json")
        resp = self.client.get("/api/assessments/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)  # only the psychologist's own

    def test_admin_sees_all_assessments(self):
        Assessment.objects.create(child=self.child, psychologist=self.psy, status="completed")
        self._auth("a@racco1.gov.ph")
        resp = self.client.get("/api/assessments/")
        self.assertEqual(len(resp.data), 1)
```

- [ ] **Step 2: Run it to verify failure**

Run: `./venv/Scripts/python.exe manage.py test assessments.tests.test_api.AssessmentTakingTest -v 2`
Expected: FAIL (404s — endpoints absent).

- [ ] **Step 3: Add the permission**

In `backend/accounts/permissions.py`, append:
```python
# Roles allowed to take/administer assessments. Kept SEPARATE from instrument
# management so reverting that to admin-only never blocks taking assessments.
ASSESSMENT_TAKER_ROLES = (Role.ADMINISTRATOR, Role.PSYCHOLOGIST)


class CanTakeAssessments(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated
                    and _role_name(request) in ASSESSMENT_TAKER_ROLES)
```

- [ ] **Step 4: Add the serializers**

Append to `backend/assessments/serializers.py`:
```python
from assessments.models import Assessment, Response


class ResponseWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Response
        fields = ["question", "answer"]


class AssessmentWriteSerializer(serializers.ModelSerializer):
    responses = ResponseWriteSerializer(many=True)

    class Meta:
        model = Assessment
        fields = ["id", "child", "questionnaire", "assessment_type", "notes", "classification", "responses"]

    def create(self, validated_data):
        responses = validated_data.pop("responses", [])
        assessment = Assessment.objects.create(**validated_data)
        for rd in responses:
            Response.objects.create(assessment=assessment, **rd)
        return assessment


class AssessmentListSerializer(serializers.ModelSerializer):
    child_name = serializers.CharField(source="child.fullname", read_only=True)
    questionnaire_title = serializers.CharField(source="questionnaire.title", read_only=True, default=None)
    psychologist_name = serializers.CharField(source="psychologist.fullname", read_only=True)

    class Meta:
        model = Assessment
        fields = ["id", "child", "child_name", "questionnaire", "questionnaire_title",
                  "psychologist_name", "assessment_type", "classification", "status", "assessment_date"]
```

- [ ] **Step 5: Add the views**

In `backend/assessments/views.py`, extend the imports:
```python
from rest_framework import generics, viewsets, status
```
(replace the existing `from rest_framework import viewsets, status` line), and add these imports below the others:
```python
from accounts.models import Role
from accounts.permissions import CanManageInstruments, CanTakeAssessments
from assessments.models import Questionnaire, Assessment
from assessments.serializers import (
    QuestionnaireSerializer, AssessmentWriteSerializer, AssessmentListSerializer,
)
```
(merge with / replace the existing `from accounts.permissions import CanManageInstruments` and `from assessments.models import Questionnaire` and `from assessments.serializers import QuestionnaireSerializer` lines so there are no duplicates.)

Append these classes to `backend/assessments/views.py`:
```python
class ActiveQuestionnaireListView(generics.ListAPIView):
    permission_classes = [CanTakeAssessments]
    pagination_class = None
    serializer_class = QuestionnaireSerializer

    def get_queryset(self):
        return Questionnaire.objects.filter(status=Questionnaire.ACTIVE).order_by("title")


class AssessmentViewSet(viewsets.ModelViewSet):
    permission_classes = [CanTakeAssessments]
    pagination_class = None

    def get_queryset(self):
        qs = Assessment.objects.select_related("child", "questionnaire", "psychologist").order_by("-assessment_date", "-id")
        role = getattr(getattr(self.request.user, "role", None), "role_name", None)
        if role != Role.ADMINISTRATOR:
            qs = qs.filter(psychologist=self.request.user)
        return qs

    def get_serializer_class(self):
        if self.action == "create":
            return AssessmentWriteSerializer
        return AssessmentListSerializer

    def perform_create(self, serializer):
        assessment = serializer.save(psychologist=self.request.user, status="completed")
        log_activity(self.request.user, ActivityLog.CREATED, ActivityLog.RECORD,
                     entity_type="Assessment", entity_label=assessment.child.fullname, entity_id=assessment.id)
```

- [ ] **Step 6: Wire the URLs**

Replace `backend/assessments/urls.py` with:
```python
from django.urls import path
from rest_framework.routers import DefaultRouter
from assessments.views import QuestionnaireViewSet, AssessmentViewSet, ActiveQuestionnaireListView

router = DefaultRouter()
router.register("questionnaires", QuestionnaireViewSet, basename="questionnaire")
router.register("assessments", AssessmentViewSet, basename="assessment")

urlpatterns = router.urls + [
    path("active-questionnaires/", ActiveQuestionnaireListView.as_view(), name="active-questionnaires"),
]
```

- [ ] **Step 7: Run the tests to verify pass, then the full suite**

Run: `./venv/Scripts/python.exe manage.py test assessments.tests.test_api -v 1`
Expected: all OK (questionnaire + extract + assessment-taking tests).
Run: `./venv/Scripts/python.exe manage.py test`
Expected: all OK.

- [ ] **Step 8: Commit (deferred — checkpoint only)**

```bash
git add backend/accounts/permissions.py backend/assessments/serializers.py backend/assessments/views.py backend/assessments/urls.py backend/assessments/tests/test_api.py
git commit -m "feat(assessments): assessment-taking API (active questionnaires + create/list)"
```

---

## Task 3: Rewire the `Assessment.jsx` wizard

**Files:** Replace `frontend/src/pages/Assessment.jsx`.

- [ ] **Step 1: Replace the page with the real wizard**

Replace `frontend/src/pages/Assessment.jsx` with:
```jsx
import React, { useEffect, useMemo, useState } from 'react';
import api from '../api/client';
import { useActivity } from '../context/ActivityContext';
import { Card, Button, Alert, Select, FormField, ProgressSteps, Icon, PAGE } from '../ui';

function caseRef(id) { return `C-${String(id).padStart(4, '0')}`; }

const CLASSIFICATIONS = ['Trauma / Stressor-related', 'Behavioral / Conduct', 'Adjustment Disorder', 'Normal Development'];

export default function Assessment() {
  const { refresh: refreshActivity } = useActivity();
  const [step, setStep] = useState(1);
  const [children, setChildren] = useState([]);
  const [forms, setForms] = useState([]); // active questionnaires
  const [child, setChild] = useState('');
  const [formId, setFormId] = useState('');
  const [stype, setStype] = useState('Intake / Baseline');
  const [answers, setAnswers] = useState({}); // { [questionId]: answerText }
  const [cls, setCls] = useState('Normal Development');
  const [notes, setNotes] = useState('');
  const [sent, setSent] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    api.get('/children/').then((r) => setChildren(r.data)).catch(() => {});
    api.get('/active-questionnaires/').then((r) => setForms(r.data)).catch(() => {});
  }, []);

  const childObj = children.find((c) => String(c.id) === String(child));
  const form = forms.find((f) => String(f.id) === String(formId));
  const questions = form?.questions || [];
  const allAnswered = questions.length > 0 && questions.every((q) => answers[q.id] != null && answers[q.id] !== '');

  const next = () => setStep((s) => Math.min(4, s + 1));
  const back = () => setStep((s) => Math.max(1, s - 1));

  const submit = async () => {
    setError('');
    try {
      await api.post('/assessments/', {
        child: Number(child),
        questionnaire: form.id,
        assessment_type: stype,
        classification: cls,
        notes,
        responses: questions.map((q) => ({ question: q.id, answer: String(answers[q.id]) })),
      });
      setSent(true);
      refreshActivity();
      setTimeout(() => {
        setSent(false); setStep(1); setChild(''); setFormId(''); setAnswers({}); setNotes('');
      }, 2600);
    } catch (err) {
      setError(JSON.stringify(err.response?.data || 'Submit failed'));
    }
  };

  const setAnswer = (qid, val) => setAnswers((a) => ({ ...a, [qid]: val }));

  return (
    <div style={PAGE}>
      <div style={{ maxWidth: 760, margin: '0 auto' }}>
        <Card padding="28px">
          <div style={{ marginBottom: 26 }}>
            <ProgressSteps steps={['Select Child', 'Questionnaire', 'Responses', 'Review & Sign']} current={step} />
          </div>

          {step === 1 && (
            <div>
              <h2 style={{ fontFamily: 'var(--font-display)', fontSize: 19, fontWeight: 700, marginBottom: 4 }}>Select a child for assessment</h2>
              <p style={{ fontSize: 13.5, color: 'var(--text-muted)', marginBottom: 18 }}>Children with an active record appear here.</p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {children.length === 0 && <Alert tone="info" icon={<Icon name="info" size={18} />}>No child records available yet. Add children under Children Records first.</Alert>}
                {children.map((c) => (
                  <button key={c.id} onClick={() => setChild(String(c.id))} style={{ display: 'flex', alignItems: 'center', gap: 13, padding: '13px 15px', textAlign: 'left', cursor: 'pointer', borderRadius: 'var(--radius-lg)', background: String(child) === String(c.id) ? 'var(--blue-50)' : 'var(--surface)', border: `1.5px solid ${String(child) === String(c.id) ? 'var(--blue-500)' : 'var(--border)'}`, transition: 'var(--transition-base)' }}>
                    <span style={{ width: 38, height: 38, borderRadius: 'var(--radius-md)', background: 'var(--ink-100)', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)', flex: 'none' }}><Icon name="user" size={19} /></span>
                    <span style={{ flex: 1 }}>
                      <span style={{ display: 'block', fontWeight: 700, fontSize: 14.5, color: 'var(--text-strong)' }}>{c.fullname}</span>
                      <span style={{ display: 'block', fontSize: 12, color: 'var(--text-muted)' }}><span className="racco-mono">{caseRef(c.id)}</span>{c.case_type ? ` · ${c.case_type}` : ''}</span>
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {step === 2 && (
            <div>
              <h2 style={{ fontFamily: 'var(--font-display)', fontSize: 19, fontWeight: 700, marginBottom: 18 }}>Choose a questionnaire</h2>
              {forms.length === 0
                ? <Alert tone="warning" icon={<Icon name="alert-triangle" size={18} />}>No published questionnaires yet. Create and publish one under <strong>Assessment Instruments</strong> first.</Alert>
                : (
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 18 }}>
                    <FormField label="Instrument">
                      <Select value={formId} onChange={(e) => { setFormId(e.target.value); setAnswers({}); }}>
                        <option value="">— Select —</option>
                        {forms.map((f) => <option key={f.id} value={f.id}>{f.title}{f.age_group ? ` (${f.age_group})` : ''}</option>)}
                      </Select>
                    </FormField>
                    <FormField label="Session Type">
                      <Select value={stype} onChange={(e) => setStype(e.target.value)}>
                        <option>Intake / Baseline</option><option>Regular Check-in</option><option>Incident Follow-up</option>
                      </Select>
                    </FormField>
                  </div>
                )}
              {form && <div style={{ marginTop: 14, fontSize: 13, color: 'var(--text-muted)' }}>{questions.length} question(s){form.description ? ` · ${form.description}` : ''}</div>}
            </div>
          )}

          {step === 3 && (
            <div>
              <h2 style={{ fontFamily: 'var(--font-display)', fontSize: 19, fontWeight: 700, marginBottom: 4 }}>{form?.title || 'Questionnaire'}</h2>
              <p style={{ fontSize: 13.5, color: 'var(--text-muted)', marginBottom: 18 }}>Answer each item based on the session.</p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                {questions.map((q, i) => (
                  <div key={q.id} style={{ background: 'var(--ink-50)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: '14px 16px' }}>
                    <p style={{ fontWeight: 600, fontSize: 14, color: 'var(--text-strong)', marginBottom: 11 }}>{i + 1}. {q.question_text}</p>
                    <QuestionInput question={q} value={answers[q.id]} onChange={(v) => setAnswer(q.id, v)} />
                  </div>
                ))}
              </div>
            </div>
          )}

          {step === 4 && (
            <div>
              {sent && (
                <div style={{ position: 'fixed', top: 78, right: 26, zIndex: 50 }}>
                  <Alert tone="success" icon={<Icon name="check-circle-2" size={18} />} style={{ boxShadow: 'var(--shadow-lg)' }}>Assessment saved to NACC.</Alert>
                </div>
              )}
              {error && <Alert tone="danger" icon={<Icon name="alert-triangle" size={18} />} style={{ marginBottom: 14 }}>{error}</Alert>}

              {childObj && <p style={{ fontSize: 13, color: 'var(--text-muted)', margin: '0 0 14px' }}>For <strong style={{ color: 'var(--text-strong)' }}>{childObj.fullname}</strong> · <span className="racco-mono">{caseRef(childObj.id)}</span> · {form?.title} · {stype}</p>}

              <div style={{ background: 'var(--ink-50)', border: '1px dashed var(--border-strong)', borderRadius: 'var(--radius-xl)', padding: 22, marginBottom: 18 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Icon name="sparkles" size={18} style={{ color: 'var(--text-faint)' }} />
                  <span style={{ fontWeight: 700, fontSize: 14, color: 'var(--text-muted)' }}>Automated analysis arrives in Phase 3</span>
                </div>
                <p style={{ fontSize: 13, color: 'var(--text-faint)', margin: '8px 0 0' }}>Behavioral scoring and AI recommendations will appear here once the analysis engine is built. For now, record your clinical judgment below.</p>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                <FormField label="Practitioner classification">
                  <Select value={cls} onChange={(e) => setCls(e.target.value)}>
                    {CLASSIFICATIONS.map((c) => <option key={c}>{c}</option>)}
                  </Select>
                </FormField>
                <FormField label="Detailed psychologist's assessment" required hint="Required before the assessment can be signed.">
                  <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={6} placeholder="Observations, behavioral patterns, recommended interventions…" style={{ width: '100%', resize: 'vertical', padding: '12px 13px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-strong)', fontFamily: 'var(--font-sans)', fontSize: 14, color: 'var(--text-strong)', outline: 'none', lineHeight: 1.55 }} />
                </FormField>
              </div>
            </div>
          )}

          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 26, paddingTop: 18, borderTop: '1px solid var(--border)' }}>
            <Button variant="ghost" disabled={step === 1} onClick={back} iconLeft={<Icon name="arrow-left" size={17} />}>Back</Button>
            {step < 4
              ? <Button variant="primary" onClick={next} disabled={(step === 1 && !child) || (step === 2 && !formId) || (step === 3 && !allAnswered)} iconRight={<Icon name="arrow-right" size={17} />}>Next Step</Button>
              : <Button variant="primary" disabled={!notes.trim() || sent} onClick={submit} iconLeft={<Icon name="pen-line" size={17} />}>Sign &amp; Submit to NACC</Button>}
          </div>
        </Card>
      </div>
    </div>
  );
}

function QuestionInput({ question, value, onChange }) {
  const type = question.question_type;
  const pill = (label, on) => ({
    padding: '8px 14px', borderRadius: 'var(--radius-pill)', cursor: 'pointer', fontFamily: 'var(--font-sans)',
    fontWeight: 700, fontSize: 13, border: `1.5px solid ${on ? 'var(--blue-600)' : 'var(--border-strong)'}`,
    background: on ? 'var(--blue-600)' : 'var(--surface)', color: on ? '#fff' : 'var(--text-body)', transition: 'var(--transition-base)',
  });
  if (type === 'rating_scale') {
    return (
      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
        {[1, 2, 3, 4, 5].map((n) => (
          <button key={n} onClick={() => onChange(String(n))} style={{ ...pill(String(n), value === String(n)), width: 40, height: 40, borderRadius: '50%', padding: 0 }}>{n}</button>
        ))}
        <div style={{ flex: 1, display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-faint)', marginLeft: 6 }}><span>Never</span><span>Always</span></div>
      </div>
    );
  }
  const opts = type === 'yes_no' ? ['Yes', 'No'] : (question.options || []);
  if (opts.length === 0) {
    return <input value={value || ''} onChange={(e) => onChange(e.target.value)} placeholder="Answer" style={{ width: '100%', padding: '9px 12px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-strong)', fontSize: 14 }} />;
  }
  return (
    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
      {opts.map((o) => <button key={o} onClick={() => onChange(o)} style={pill(o, value === o)}>{o}</button>)}
    </div>
  );
}
```

- [ ] **Step 2: Verify the build**

Run (from `frontend/`): `npm run build`
Expected: built, no errors.

- [ ] **Step 3: Commit (deferred — checkpoint only)**

```bash
git add frontend/src/pages/Assessment.jsx
git commit -m "feat(assessment): real wizard — load questionnaire, answer, persist"
```

---

## Task 4: End-to-end verification

- [ ] **Step 1: Full backend suite**

Run (from `backend/`): `./venv/Scripts/python.exe manage.py migrate` (apply 0004 to the dev DB), then `./venv/Scripts/python.exe manage.py test`
Expected: all OK.

- [ ] **Step 2: Frontend build**

Run (from `frontend/`): `npm run build`
Expected: built, no errors.

- [ ] **Step 3: Browser smoke test (preview)**

Start backend (`runserver`) + preview, log in as the seeded admin (a taker), and (if no active questionnaire exists) publish one under **Assessment Instruments**, then open **Assessment Tools**:
- Step through select child → pick the questionnaire → answer each rendered question (by type) → enter notes → **Sign & Submit**.
- Confirm the success toast, an **"Added Assessment …"** entry in the notification bell, and a persisted row via `GET /api/assessments/`.
```
