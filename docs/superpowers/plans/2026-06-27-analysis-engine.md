# Phase 3 — Free Rule-Based Analysis Engine — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn saved assessment responses into a behavioral score, a triage classification, and a template recommendation — free, deterministic, no LLM — shown in the wizard and persisted to `AssessmentResult` + `Recommendation`.

**Architecture:** A pure-Python `assessments/analysis/` module (scoring + template recommendations) is the single source of truth, called by a `/analyze/` preview endpoint and by assessment submit (which persists the result). A small scoring key on `Question` makes scoring directionally correct.

**Tech Stack:** Django + DRF (SQLite); React + Vite.

**Spec:** [2026-06-27-analysis-engine-design.md](../specs/2026-06-27-analysis-engine-design.md)

**Conventions:** Backend from `backend/` as `./venv/Scripts/python.exe manage.py <cmd>`. Commits omit any Claude co-author trailer. Commits deferred until the user asks (checkpoints below).

---

## File Structure

**Backend — new:** `assessments/analysis/{__init__,scoring,recommendations}.py`, `assessments/tests/test_analysis.py`; migration `0006_*`.
**Backend — modify:** `assessments/models.py` (2 `Question` fields), `assessments/serializers.py` (question concern fields + `AssessmentResultSerializer`), `assessments/views.py` (`analyze` action + persist-on-submit), `assessments/tests/test_api.py`.
**Frontend — modify:** `src/pages/Assessment.jsx`, `src/pages/Questionnaires.jsx`.

---

## Task 1: Scoring-key fields on `Question`

**Files:** Modify `backend/assessments/models.py`, `backend/assessments/serializers.py`; Test `backend/assessments/tests/test_models.py`.

- [ ] **Step 1: Write the failing test**

Append to `backend/assessments/tests/test_models.py`:
```python
class ConcernFieldsTest(TestCase):
    def test_question_concern_defaults(self):
        from assessments.models import Questionnaire, Question
        qn = Questionnaire.objects.create(title="S", status="active")
        q = Question.objects.create(questionnaire=qn, question_text="x", question_type="rating_scale", order=1)
        self.assertEqual(q.concern_direction, "higher")
        self.assertEqual(q.concern_options, [])
```

- [ ] **Step 2: Run it to verify failure**

Run: `./venv/Scripts/python.exe manage.py test assessments.tests.test_models.ConcernFieldsTest -v 2`
Expected: FAIL (`concern_direction` missing).

- [ ] **Step 3: Add the fields**

In `backend/assessments/models.py`, in `Question` (after `options` / `order`), add:
```python
    HIGHER, LOWER = "higher", "lower"
    CONCERN_CHOICES = [(HIGHER, "Higher"), (LOWER, "Lower")]
    concern_direction = models.CharField(max_length=10, choices=CONCERN_CHOICES, default=HIGHER)
    concern_options = models.JSONField(default=list, blank=True)
```

- [ ] **Step 4: Add the serializer fields**

In `backend/assessments/serializers.py`, update `QuestionSerializer`:
```python
class QuestionSerializer(serializers.ModelSerializer):
    options = serializers.JSONField(required=False, default=list)
    concern_options = serializers.JSONField(required=False, default=list)

    class Meta:
        model = Question
        fields = ["id", "question_text", "question_type", "options", "order",
                  "concern_direction", "concern_options"]
```

- [ ] **Step 5: Make migration + run test**

Run: `./venv/Scripts/python.exe manage.py makemigrations assessments`
Expected: `0006_…` adding `concern_direction`, `concern_options`.
Run: `./venv/Scripts/python.exe manage.py test assessments.tests.test_models -v 1`
Expected: OK.

- [ ] **Step 6: Commit (deferred — checkpoint only)**

```bash
git add backend/assessments/models.py backend/assessments/serializers.py backend/assessments/migrations/0006_*.py backend/assessments/tests/test_models.py
git commit -m "feat(assessments): per-question scoring key (concern direction/options)"
```

---

## Task 2: Scoring + recommendation engine

**Files:** Create `backend/assessments/analysis/__init__.py`, `scoring.py`, `recommendations.py`, `backend/assessments/tests/test_analysis.py`.

- [ ] **Step 1: Write the failing tests**

Create `backend/assessments/tests/test_analysis.py`:
```python
from django.test import TestCase
from assessments.models import Questionnaire, Question
from assessments.analysis import scoring, recommendations


class ScoringTest(TestCase):
    def setUp(self):
        self.qn = Questionnaire.objects.create(title="S", status="active")
        self.rate = Question.objects.create(questionnaire=self.qn, question_text="Distress?", question_type="rating_scale", order=1)
        self.yn = Question.objects.create(questionnaire=self.qn, question_text="Sleeps well?", question_type="yes_no", concern_direction="lower", order=2)
        self.emo = Question.objects.create(questionnaire=self.qn, question_text="Mood?", question_type="emotion", options=["Happy", "Sad"], concern_options=["Sad"], order=3)

    def _score(self, answers):
        responses = [{"question": qid, "answer": a} for qid, a in answers]
        return scoring.score(self.qn, responses)

    def test_high_concern(self):
        r = self._score([(self.rate.id, "5"), (self.yn.id, "No"), (self.emo.id, "Sad")])
        self.assertEqual(r["behavioral_score"], 100.0)
        self.assertEqual(r["classification"], "Needs Counseling Attention")

    def test_low_concern(self):
        r = self._score([(self.rate.id, "1"), (self.yn.id, "Yes"), (self.emo.id, "Happy")])
        self.assertEqual(r["behavioral_score"], 0.0)
        self.assertEqual(r["classification"], "Normal")

    def test_mid_concern_is_monitoring(self):
        r = self._score([(self.rate.id, "3"), (self.yn.id, "No"), (self.emo.id, "Happy")])
        # concerns: 0.5, 1.0, 0.0 -> mean 0.5 -> 50
        self.assertEqual(r["behavioral_score"], 50.0)
        self.assertEqual(r["classification"], "Needs Monitoring")

    def test_unmarked_choice_not_scored(self):
        q = Question.objects.create(questionnaire=self.qn, question_text="Pick", question_type="multiple_choice", options=["A", "B"], order=4)
        r = self._score([(self.rate.id, "1"), (q.id, "A")])
        self.assertEqual(r["scored_count"], 1)  # only the rating

    def test_no_scorable_defaults_monitoring(self):
        q = Question.objects.create(questionnaire=Questionnaire.objects.create(title="E"), question_text="Pick", question_type="multiple_choice", options=["A"], order=1)
        r = scoring.score(q.questionnaire, [{"question": q.id, "answer": "A"}])
        self.assertIsNone(r["behavioral_score"])
        self.assertEqual(r["classification"], "Needs Monitoring")


class RecommendationTest(TestCase):
    def test_priority_by_classification(self):
        self.assertEqual(recommendations.recommend({"classification": "Normal", "top_concerns": []})["priority_level"], "Low")
        self.assertEqual(recommendations.recommend({"classification": "Needs Monitoring", "top_concerns": ["Sleep"]})["priority_level"], "Medium")
        high = recommendations.recommend({"classification": "Needs Counseling Attention", "top_concerns": ["Distress?"]})
        self.assertEqual(high["priority_level"], "High")
        self.assertIn("Distress?", high["recommendation_text"])
        self.assertIn("decision support", high["recommendation_text"])
```

- [ ] **Step 2: Run to verify failure**

Run: `./venv/Scripts/python.exe manage.py test assessments.tests.test_analysis -v 2`
Expected: FAIL (`assessments.analysis` not found).

- [ ] **Step 3: Create the scoring module**

Create `backend/assessments/analysis/__init__.py` (empty).
Create `backend/assessments/analysis/scoring.py`:
```python
"""Free, deterministic behavioral scoring. No external services."""

NORMAL = "Normal"
NEEDS_MONITORING = "Needs Monitoring"
NEEDS_ATTENTION = "Needs Counseling Attention"


def classify(score):
    if score is None:
        return NEEDS_MONITORING
    if score < 34:
        return NORMAL
    if score < 67:
        return NEEDS_MONITORING
    return NEEDS_ATTENTION


def concern_for(question, answer):
    """Return a concern value in [0, 1], or None if this answer is not scorable."""
    answer = (answer or "").strip()
    qtype = question.question_type
    if qtype == "rating_scale":
        try:
            v = int(float(answer))
        except (TypeError, ValueError):
            return None
        if v < 1 or v > 5:
            return None
        return (v - 1) / 4 if question.concern_direction != "lower" else (5 - v) / 4
    if qtype == "yes_no":
        concern_answer = "yes" if question.concern_direction != "lower" else "no"
        return 1.0 if answer.lower() == concern_answer else 0.0
    if qtype in ("multiple_choice", "emotion"):
        opts = question.concern_options or []
        if not opts:
            return None
        return 1.0 if answer in opts else 0.0
    return None


def score(questionnaire, responses):
    """responses: iterable of {"question": <id>, "answer": <text>}."""
    questions = {q.id: q for q in questionnaire.questions.all()}
    items = []
    for r in responses:
        qid = r.get("question")
        try:
            q = questions.get(int(qid))
        except (TypeError, ValueError):
            q = None
        if q is None:
            continue
        c = concern_for(q, str(r.get("answer", "")))
        if c is None:
            continue
        items.append((q, c))
    total = len(questions)
    scored = len(items)
    if scored == 0:
        return {"behavioral_score": None, "classification": NEEDS_MONITORING,
                "scored_count": 0, "total_count": total, "top_concerns": []}
    behavioral = round(sum(c for _, c in items) / scored * 100, 2)
    top = [q.question_text for q, c in sorted(items, key=lambda x: x[1], reverse=True) if c >= 0.5][:2]
    return {"behavioral_score": behavioral, "classification": classify(behavioral),
            "scored_count": scored, "total_count": total, "top_concerns": top}
```

- [ ] **Step 4: Create the recommendations module**

Create `backend/assessments/analysis/recommendations.py`:
```python
"""Free template recommendations. Swap get_recommender() for an LLM later."""

DISCLAIMER = ("This is decision support, not a diagnosis; the final determination "
              "rests with the licensed professional.")

_TEMPLATES = {
    "Normal": ("Low",
               "The child appears to be adjusting well; responses show no significant behavioral concerns.",
               "continue routine periodic check-ins"),
    "Needs Monitoring": ("Medium",
                         "Some responses indicate mild-to-moderate behavioral concerns{focus}.",
                         "increase observation, schedule a follow-up within 4 weeks, and introduce light supportive measures"),
    "Needs Counseling Attention": ("High",
                                   "Responses indicate notable behavioral concerns requiring attention{focus}.",
                                   "arrange focused counseling support, coordinate with the house parent or guardian, and reassess within 1-2 weeks"),
}


def recommend(result):
    classification = result.get("classification", "Needs Monitoring")
    priority, summary_tpl, actions = _TEMPLATES.get(classification, _TEMPLATES["Needs Monitoring"])
    top = result.get("top_concerns") or []
    focus = f", notably around: {'; '.join(top)}" if top else ""
    summary = summary_tpl.format(focus=focus)
    text = f"{summary} Suggested actions: {actions}. {DISCLAIMER}"
    return {"recommendation_text": text, "priority_level": priority}


def get_recommender():
    # Swap point: return an LLM-backed callable here once budget exists.
    return recommend
```

- [ ] **Step 5: Run analysis tests to verify pass**

Run: `./venv/Scripts/python.exe manage.py test assessments.tests.test_analysis -v 1`
Expected: all OK.

- [ ] **Step 6: Commit (deferred — checkpoint only)**

```bash
git add backend/assessments/analysis backend/assessments/tests/test_analysis.py
git commit -m "feat(assessments): free rule-based scoring + template recommendations"
```

---

## Task 3: `/analyze/` endpoint + persist on submit

**Files:** Modify `backend/assessments/views.py`, `backend/assessments/serializers.py`; Test append `backend/assessments/tests/test_api.py`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/assessments/tests/test_api.py` (inside `class AssessmentTakingTest`):
```python
    def test_analyze_returns_result_without_saving(self):
        from assessments.models import AssessmentResult
        self._auth("p@racco1.gov.ph")
        resp = self.client.post("/api/assessments/analyze/", {
            "questionnaire": self.qn.id,
            "responses": [{"question": self.q1.id, "answer": "No"}, {"question": self.q2.id, "answer": "5"}],
        }, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("behavioral_score", resp.data)
        self.assertIn("recommendation_text", resp.data)
        self.assertEqual(AssessmentResult.objects.count(), 0)

    def test_analyze_forbidden_for_staff(self):
        self._auth("s@racco1.gov.ph")
        resp = self.client.post("/api/assessments/analyze/", {"questionnaire": self.qn.id, "responses": []}, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_submit_persists_result_and_recommendation(self):
        from assessments.models import AssessmentResult, Recommendation
        self._auth("p@racco1.gov.ph")
        self.client.post("/api/assessments/", self._assessment_payload(), format="json")
        self.assertEqual(AssessmentResult.objects.count(), 1)
        self.assertEqual(Recommendation.objects.count(), 1)
        self.assertTrue(AssessmentResult.objects.first().classification)
```

(The existing `self.q1` is `yes_no`, `self.q2` is `rating_scale` — both scorable by default.)

- [ ] **Step 2: Run to verify failure**

Run: `./venv/Scripts/python.exe manage.py test assessments.tests.test_api.AssessmentTakingTest.test_submit_persists_result_and_recommendation -v 2`
Expected: FAIL (no result persisted / no analyze route).

- [ ] **Step 3: Add the result serializer**

Append to `backend/assessments/serializers.py`:
```python
from assessments.models import AssessmentResult


class AssessmentResultSerializer(serializers.ModelSerializer):
    priority_level = serializers.SerializerMethodField()
    recommendation_text = serializers.SerializerMethodField()

    class Meta:
        model = AssessmentResult
        fields = ["behavioral_score", "classification", "generated_date",
                  "priority_level", "recommendation_text"]

    def _first_rec(self, obj):
        return obj.recommendations.first()

    def get_priority_level(self, obj):
        rec = self._first_rec(obj)
        return rec.priority_level if rec else ""

    def get_recommendation_text(self, obj):
        rec = self._first_rec(obj)
        return rec.recommendation_text if rec else ""
```

- [ ] **Step 4: Add the analyze action + persist-on-submit**

In `backend/assessments/views.py`, add imports (merge with existing assessments.models / serializers imports):
```python
from assessments.models import Questionnaire, Assessment, AssessmentResult, Recommendation
from assessments.analysis import scoring, recommendations
```
Add the `analyze` action and `_persist_analysis`, and call it from `perform_create`, inside `AssessmentViewSet`:
```python
    @action(detail=False, methods=["post"])
    def analyze(self, request):
        try:
            questionnaire = Questionnaire.objects.get(pk=request.data.get("questionnaire"))
        except Questionnaire.DoesNotExist:
            return Response({"detail": "Questionnaire not found."}, status=status.HTTP_400_BAD_REQUEST)
        result = scoring.score(questionnaire, request.data.get("responses", []))
        rec = recommendations.recommend(result)
        return Response({**result, **rec}, status=status.HTTP_200_OK)

    def _persist_analysis(self, assessment):
        if not assessment.questionnaire_id:
            return
        responses = [{"question": r.question_id, "answer": r.answer} for r in assessment.responses.all()]
        result = scoring.score(assessment.questionnaire, responses)
        rec = recommendations.recommend(result)
        ar = AssessmentResult.objects.create(
            assessment=assessment,
            behavioral_score=result["behavioral_score"],
            classification=result["classification"],
            assessment_date=assessment.assessment_date,
            assessment_type=assessment.assessment_type,
        )
        Recommendation.objects.create(
            result=ar, recommendation_text=rec["recommendation_text"], priority_level=rec["priority_level"])
```
Update `perform_create` to call it (after save, before/after logging):
```python
    def perform_create(self, serializer):
        assessment = serializer.save(psychologist=self.request.user, status="completed")
        self._persist_analysis(assessment)
        log_activity(self.request.user, ActivityLog.CREATED, ActivityLog.RECORD,
                     entity_type="Assessment", entity_label=assessment.child.fullname, entity_id=assessment.id)
```

- [ ] **Step 5: Run the API tests + full suite**

Run: `./venv/Scripts/python.exe manage.py test assessments -v 1`
Expected: OK.
Run: `./venv/Scripts/python.exe manage.py test`
Expected: all OK.

- [ ] **Step 6: Commit (deferred — checkpoint only)**

```bash
git add backend/assessments/views.py backend/assessments/serializers.py backend/assessments/tests/test_api.py
git commit -m "feat(assessments): /analyze endpoint + persist result/recommendation on submit"
```

---

## Task 4: Wizard step 4 shows real analysis

**Files:** Modify `frontend/src/pages/Assessment.jsx`.

- [ ] **Step 1: Add analysis state + fetch on entering step 4**

In `frontend/src/pages/Assessment.jsx`, after the existing `const [respondentMode, setRespondentMode] = useState('staff');` line add:
```jsx
  const [analysis, setAnalysis] = useState(null);
  const [analyzing, setAnalyzing] = useState(false);
```
Add this effect after the existing `useEffect` that loads children/forms:
```jsx
  useEffect(() => {
    if (step !== 4 || !form) return;
    setAnalysis(null); setAnalyzing(true);
    api.post('/assessments/analyze/', {
      questionnaire: form.id,
      responses: questions.map((q) => ({ question: q.id, answer: String(answers[q.id]) })),
    }).then((r) => setAnalysis(r.data)).catch(() => {}).finally(() => setAnalyzing(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step]);
```

- [ ] **Step 2: Replace the placeholder box with the real analysis**

In `Assessment.jsx`, replace the step-4 "Automated analysis arrives in Phase 3" placeholder block:
```jsx
              <div style={{ background: 'var(--ink-50)', border: '1px dashed var(--border-strong)', borderRadius: 'var(--radius-xl)', padding: 22, marginBottom: 18 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Icon name="sparkles" size={18} style={{ color: 'var(--text-faint)' }} />
                  <span style={{ fontWeight: 700, fontSize: 14, color: 'var(--text-muted)' }}>Automated analysis arrives in Phase 3</span>
                </div>
                <p style={{ fontSize: 13, color: 'var(--text-faint)', margin: '8px 0 0' }}>Behavioral scoring and AI recommendations will appear here once the analysis engine is built. For now, record your clinical judgment below.</p>
              </div>
```
with:
```jsx
              <AnalysisPanel analyzing={analyzing} analysis={analysis} />
```
And add this component at the bottom of the file (after `QuestionInput`):
```jsx
const TRIAGE_TONE = {
  'Normal': { bg: 'var(--success-50)', line: 'var(--success-100)', fg: 'var(--success-700)' },
  'Needs Monitoring': { bg: 'var(--warning-50)', line: 'var(--warning-100)', fg: 'var(--warning-700)' },
  'Needs Counseling Attention': { bg: 'var(--red-50)', line: 'var(--red-100)', fg: 'var(--red-700)' },
};

function AnalysisPanel({ analyzing, analysis }) {
  const tone = TRIAGE_TONE[analysis?.classification] || TRIAGE_TONE['Needs Monitoring'];
  return (
    <div style={{ background: analysis ? tone.bg : 'var(--ink-50)', border: `1px solid ${analysis ? tone.line : 'var(--border-strong)'}`, borderRadius: 'var(--radius-xl)', padding: 22, marginBottom: 18 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
        <Icon name="sparkles" size={18} style={{ color: analysis ? tone.fg : 'var(--text-faint)' }} />
        <span style={{ fontWeight: 800, fontSize: 14, color: 'var(--text-strong)' }}>Automated analysis</span>
      </div>
      {analyzing && <p style={{ fontSize: 13.5, color: 'var(--text-muted)', margin: 0 }}>Analyzing responses…</p>}
      {!analyzing && !analysis && <p style={{ fontSize: 13.5, color: 'var(--text-faint)', margin: 0 }}>Analysis unavailable — record your clinical judgment below.</p>}
      {!analyzing && analysis && (
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap', marginBottom: 12 }}>
            <span style={{ fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 17, color: tone.fg }}>{analysis.classification}</span>
            {analysis.behavioral_score != null && <span className="racco-mono" style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-strong)' }}>Score {analysis.behavioral_score} / 100</span>}
            <span style={{ fontSize: 11.5, color: 'var(--text-faint)' }}>based on {analysis.scored_count} of {analysis.total_count} items</span>
          </div>
          <p style={{ fontSize: 13.5, color: 'var(--text-body)', lineHeight: 1.6, margin: '0 0 8px' }}>{analysis.recommendation_text}</p>
          <span style={{ display: 'inline-block', fontSize: 11, fontWeight: 800, letterSpacing: '0.05em', textTransform: 'uppercase', color: tone.fg }}>Priority: {analysis.priority_level}</span>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Reset analysis on submit**

In `Assessment.jsx`, in the `submit` success `setTimeout` reset, add `setAnalysis(null);`:
```jsx
        setSent(false); setStep(1); setChild(''); setFormId(''); setAnswers({}); setNotes(''); setRespondentMode('staff'); setAnalysis(null);
```

- [ ] **Step 4: Verify build**

Run (from `frontend/`): `npm run build`
Expected: built, no errors.

- [ ] **Step 5: Commit (deferred — checkpoint only)**

```bash
git add frontend/src/pages/Assessment.jsx
git commit -m "feat(assessment): show real automated analysis in the wizard"
```

---

## Task 5: Builder — per-question concern controls

**Files:** Modify `frontend/src/pages/Questionnaires.jsx`.

- [ ] **Step 1: Seed concern fields in new/edited questions**

In `frontend/src/pages/Questionnaires.jsx`, update `blankQuestion`:
```jsx
const blankQuestion = (order) => ({ question_text: '', question_type: 'rating_scale', options: [], concern_direction: 'higher', concern_options: [], order });
```
In `openEdit` and `onUpload`, ensure each mapped question carries the fields (default if absent):
```jsx
      questions: (r.data.questions.length ? r.data.questions : [blankQuestion(1)]).map((q) => ({ ...q, options: q.options || [], concern_direction: q.concern_direction || 'higher', concern_options: q.concern_options || [] })),
```
(apply the same `.map(...)` shape in both `openEdit` and the `onUpload` success setForm.)

- [ ] **Step 2: Send concern fields in the payload**

In `Questionnaires.jsx` `save`, update the questions map:
```jsx
      questions: form.questions
        .filter((q) => q.question_text.trim())
        .map((q, i) => ({ question_text: q.question_text, question_type: q.question_type, options: HAS_OPTIONS(q.question_type) ? q.options : [], concern_direction: q.concern_direction || 'higher', concern_options: HAS_OPTIONS(q.question_type) ? (q.concern_options || []) : [], order: i + 1 })),
```

- [ ] **Step 3: Add the concern control under each question**

In `Questionnaires.jsx`, inside the question editor (after the `HAS_OPTIONS(q.question_type)` options input block, still inside the question's flex column), add a small scoring-key control:
```jsx
                      {q.question_type === 'rating_scale' && (
                        <Select value={q.concern_direction} onChange={(e) => setQuestion(i, { concern_direction: e.target.value })}>
                          <option value="higher">Concern = higher ratings</option>
                          <option value="lower">Concern = lower ratings</option>
                        </Select>
                      )}
                      {q.question_type === 'yes_no' && (
                        <Select value={q.concern_direction} onChange={(e) => setQuestion(i, { concern_direction: e.target.value })}>
                          <option value="higher">Concern answer: Yes</option>
                          <option value="lower">Concern answer: No</option>
                        </Select>
                      )}
                      {HAS_OPTIONS(q.question_type) && (
                        <Input value={(q.concern_options || []).join(', ')} onChange={(e) => setQuestion(i, { concern_options: e.target.value.split(',').map((s) => s.trim()).filter(Boolean) })} placeholder="Concerning options (comma-separated, must match options)" />
                      )}
```

- [ ] **Step 4: Verify build**

Run (from `frontend/`): `npm run build`
Expected: built, no errors.

- [ ] **Step 5: Commit (deferred — checkpoint only)**

```bash
git add frontend/src/pages/Questionnaires.jsx
git commit -m "feat(questionnaires): per-question scoring-key controls"
```

---

## Task 6: End-to-end verification

- [ ] **Step 1: Apply migration + full backend suite**

Run (from `backend/`): `./venv/Scripts/python.exe manage.py migrate`, then `./venv/Scripts/python.exe manage.py test`
Expected: all OK.

- [ ] **Step 2: Frontend build**

Run (from `frontend/`): `npm run build`
Expected: built, no errors.

- [ ] **Step 3: Browser smoke test**

Backend `runserver` + preview; log in as the Psychologist; ensure an active questionnaire exists (its rating/yes-no items score by default); run an assessment → on **Review & Sign**, confirm the **Automated analysis** panel shows a classification + score + "based on N of M items" + a recommendation + priority. Sign & Submit. Verify `GET` shows an `AssessmentResult` persisted (shell: `AssessmentResult.objects.count()`).
