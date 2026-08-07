# Confidence Threshold Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the "Minimum confidence threshold" feature real end-to-end — the engine emits a deterministic confidence, the threshold + override toggle persist, and low-confidence results are blocked from saving until a practitioner explicitly overrides.

**Architecture:** Backend (Django REST) gains a deterministic `confidence` (0–100) in the rule-based scorer, a singleton `AnalysisSetting` model + GET/PUT API, and a server-enforced save gate keyed on an `override_acknowledged` flag. Frontend (React/Vite) wires the Settings page to the API and adds a confidence display + override checkbox to the assessment wizard. The in-browser `mockBackend.js` mirrors all of it for the demo.

**Tech Stack:** Django 5 / DRF, SQLite; React + Vite + Axios. No LLM, no paid API — confidence is pure arithmetic.

**Branch:** `feature/confidence-threshold` (already checked out; spec committed at `4a2eb2d`).

**Test runner (backend):** run from `backend/` with the venv Python directly, e.g.
`./venv/Scripts/python.exe manage.py test assessments -v 2`

**Conventions:** Commit messages use Conventional Commits and **must not** include any Claude co-author trailer (author = the user only). Frontend has no unit-test harness — verify frontend tasks with `npm run build` + the preview browser.

---

## Task 1: Engine emits `confidence`

**Files:**
- Modify: `backend/assessments/analysis/scoring.py`
- Test: `backend/assessments/tests/test_analysis.py`

- [ ] **Step 1: Write the failing tests**

Add these methods inside the existing `ScoringTest` class in `backend/assessments/tests/test_analysis.py` (it already has `setUp` with `self.rate` rating_scale, `self.yn` yes_no `concern_direction="lower"`, `self.emo` emotion `concern_options=["Sad"]`, and the `_score` helper):

```python
    def test_confidence_full_coverage_decisive(self):
        # all 3 scorable, score 100 -> far from any boundary
        r = self._score([(self.rate.id, "5"), (self.yn.id, "No"), (self.emo.id, "Sad")])
        self.assertEqual(r["confidence"], 100)

    def test_confidence_low_coverage_lowers_it(self):
        # only 1 of 3 questions scorable -> coverage 1/3
        r = self._score([(self.rate.id, "5")])
        self.assertEqual(r["scored_count"], 1)
        self.assertEqual(r["confidence"], 67)

    def test_confidence_drops_near_boundary(self):
        # full coverage but score 66.67 sits right on the 67 boundary
        r = self._score([(self.rate.id, "5"), (self.yn.id, "No"), (self.emo.id, "Happy")])
        self.assertEqual(r["behavioral_score"], 66.67)
        self.assertEqual(r["confidence"], 51)

    def test_confidence_zero_when_nothing_scorable(self):
        qn2 = Questionnaire.objects.create(title="E2")
        q = Question.objects.create(questionnaire=qn2, question_text="Pick", question_type="multiple_choice", options=["A"], order=1)
        r = scoring.score(qn2, [{"question": q.id, "answer": "A"}])
        self.assertEqual(r["confidence"], 0)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `./venv/Scripts/python.exe manage.py test assessments.tests.test_analysis.ScoringTest -v 2`
Expected: FAIL with `KeyError: 'confidence'`.

- [ ] **Step 3: Implement confidence in the scorer**

In `backend/assessments/analysis/scoring.py`, add the constants + helper just below the existing `NEEDS_ATTENTION = ...` line (top of file):

```python
BOUNDARY_LOW, BOUNDARY_HIGH = 34, 67
BOUNDARY_MARGIN = 15          # points from a boundary at which the verdict is "decisive"
W_COVERAGE, W_DECISIVENESS = 0.5, 0.5


def confidence_for(coverage, behavioral):
    """0-100 certainty: how much data we have (coverage) and how clear the verdict is."""
    if behavioral is None:
        return 0
    margin = min(abs(behavioral - BOUNDARY_LOW), abs(behavioral - BOUNDARY_HIGH))
    decisiveness = min(margin / BOUNDARY_MARGIN, 1.0)
    return round(100 * (W_COVERAGE * coverage + W_DECISIVENESS * decisiveness))
```

Then update `score()` so both return paths include `coverage` + `confidence`. Replace the body from `total = len(questions)` to the end with:

```python
    total = len(questions)
    scored = len(items)
    coverage = scored / total if total else 0.0
    if scored == 0:
        return {"behavioral_score": None, "classification": NEEDS_MONITORING,
                "scored_count": 0, "total_count": total, "top_concerns": [],
                "confidence": confidence_for(coverage, None)}
    behavioral = round(sum(c for _, c in items) / scored * 100, 2)
    top = [q.question_text for q, c in sorted(items, key=lambda x: x[1], reverse=True) if c >= 0.5][:2]
    return {"behavioral_score": behavioral, "classification": classify(behavioral),
            "scored_count": scored, "total_count": total, "top_concerns": top,
            "confidence": confidence_for(coverage, behavioral)}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `./venv/Scripts/python.exe manage.py test assessments.tests.test_analysis -v 2`
Expected: PASS (all ScoringTest + RecommendationTest tests green).

- [ ] **Step 5: Commit**

```bash
git add backend/assessments/analysis/scoring.py backend/assessments/tests/test_analysis.py
git commit -m "feat(analysis): deterministic confidence from coverage + decisiveness"
```

---

## Task 2: `AnalysisSetting` singleton model

**Files:**
- Modify: `backend/assessments/models.py`
- Create: `backend/assessments/migrations/0003_analysissetting.py` (generated)
- Test: `backend/assessments/tests/test_models.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/assessments/tests/test_models.py`:

```python
class AnalysisSettingTest(TestCase):
    def test_load_returns_singleton_with_defaults(self):
        from assessments.models import AnalysisSetting
        s = AnalysisSetting.load()
        self.assertEqual(s.pk, 1)
        self.assertEqual(s.min_confidence_threshold, 80)
        self.assertTrue(s.require_override_on_low_confidence)

    def test_save_always_pins_pk_one(self):
        from assessments.models import AnalysisSetting
        s = AnalysisSetting.load()
        s.min_confidence_threshold = 70
        s.save()
        self.assertEqual(AnalysisSetting.objects.count(), 1)
        self.assertEqual(AnalysisSetting.load().min_confidence_threshold, 70)
```

If `test_models.py` does not already `from django.test import TestCase`, add that import at the top.

- [ ] **Step 2: Run the test to verify it fails**

Run: `./venv/Scripts/python.exe manage.py test assessments.tests.test_models.AnalysisSettingTest -v 2`
Expected: FAIL with `ImportError: cannot import name 'AnalysisSetting'`.

- [ ] **Step 3: Add the model**

Append to `backend/assessments/models.py`:

```python
class AnalysisSetting(models.Model):
    """Singleton (pk=1) holding the AI-engine gate configuration."""
    min_confidence_threshold = models.PositiveSmallIntegerField(default=80)
    require_override_on_low_confidence = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tbl_analysis_setting"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
```

- [ ] **Step 4: Generate + apply the migration**

Run:
```bash
./venv/Scripts/python.exe manage.py makemigrations assessments
./venv/Scripts/python.exe manage.py migrate
```
Expected: creates `0003_analysissetting.py` (number may differ) and applies it.

- [ ] **Step 5: Run the test to verify it passes**

Run: `./venv/Scripts/python.exe manage.py test assessments.tests.test_models.AnalysisSettingTest -v 2`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/assessments/models.py backend/assessments/migrations/ backend/assessments/tests/test_models.py
git commit -m "feat(assessments): AnalysisSetting singleton for the confidence gate"
```

---

## Task 3: Settings API (GET any assessor / PUT admin-only)

**Files:**
- Modify: `backend/assessments/serializers.py`
- Modify: `backend/assessments/views.py`
- Modify: `backend/assessments/urls.py`
- Test: `backend/assessments/tests/test_api.py`

> **Routing note:** the DRF router owns the `assessments/` prefix, so a literal `assessments/settings/` would collide with the `assessments/<pk>/` detail route. Mount the settings endpoint at `analysis-settings/` → full path **`/api/analysis-settings/`**.

- [ ] **Step 1: Write the failing tests**

Append to `backend/assessments/tests/test_api.py` (reuses `User`, `Role` already imported at top):

```python
class AnalysisSettingApiTest(APITestCase):
    def setUp(self):
        self.admin_role = Role.objects.create(role_name=Role.ADMINISTRATOR)
        self.psy_role = Role.objects.create(role_name=Role.PSYCHOLOGIST)
        self.admin = User.objects.create_user(email="a@racco1.gov.ph", username="a", password="pass1234", role=self.admin_role)
        self.psy = User.objects.create_user(email="p@racco1.gov.ph", username="p", password="pass1234", role=self.psy_role)

    def _auth(self, email):
        token = self.client.post("/api/auth/login/", {"email": email, "password": "pass1234"}).data["access"]
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + token)

    def test_get_returns_defaults(self):
        self._auth("p@racco1.gov.ph")
        resp = self.client.get("/api/analysis-settings/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["min_confidence_threshold"], 80)
        self.assertTrue(resp.data["require_override_on_low_confidence"])

    def test_admin_can_update(self):
        self._auth("a@racco1.gov.ph")
        resp = self.client.put("/api/analysis-settings/", {
            "min_confidence_threshold": 70, "require_override_on_low_confidence": False}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["min_confidence_threshold"], 70)

    def test_non_admin_cannot_update(self):
        self._auth("p@racco1.gov.ph")
        resp = self.client.put("/api/analysis-settings/", {
            "min_confidence_threshold": 70, "require_override_on_low_confidence": True}, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_threshold_out_of_range_rejected(self):
        self._auth("a@racco1.gov.ph")
        resp = self.client.put("/api/analysis-settings/", {
            "min_confidence_threshold": 10, "require_override_on_low_confidence": True}, format="json")
        self.assertEqual(resp.status_code, 400)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `./venv/Scripts/python.exe manage.py test assessments.tests.test_api.AnalysisSettingApiTest -v 2`
Expected: FAIL (404 — route does not exist yet).

- [ ] **Step 3: Add the serializer**

Append to `backend/assessments/serializers.py` (and add `AnalysisSetting` to the model import on line 2):

```python
class AnalysisSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnalysisSetting
        fields = ["min_confidence_threshold", "require_override_on_low_confidence"]

    def validate_min_confidence_threshold(self, value):
        if value < 50 or value > 99:
            raise serializers.ValidationError("Threshold must be between 50 and 99.")
        return value
```

Update the import line at the top of the file to:

```python
from assessments.models import Questionnaire, Question, Assessment, Response, AssessmentResult, AnalysisSetting
```

- [ ] **Step 4: Add the view**

In `backend/assessments/views.py`, add to the imports near the top:

```python
from rest_framework.permissions import IsAuthenticated
from accounts.permissions import IsAdministrator
from assessments.models import Questionnaire, Assessment, AssessmentResult, Recommendation, AnalysisSetting
from assessments.serializers import (
    QuestionnaireSerializer, AssessmentWriteSerializer, AssessmentListSerializer, AnalysisSettingSerializer,
)
```

(Replace the existing two import lines for models/serializers — keep the rest. Leave the existing `from accounts.permissions import ...` line and just add `IsAdministrator` to it, or add the new import line shown above; both work.)

Append this view at the end of `views.py`:

```python
class AnalysisSettingView(generics.RetrieveUpdateAPIView):
    serializer_class = AnalysisSettingSerializer

    def get_permissions(self):
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [IsAuthenticated()]
        return [IsAdministrator()]

    def get_object(self):
        return AnalysisSetting.load()
```

- [ ] **Step 5: Register the route**

In `backend/assessments/urls.py`, import the view and add the path:

```python
from assessments.views import (
    QuestionnaireViewSet, AssessmentViewSet, ActiveQuestionnaireListView, AnalysisSettingView,
)
```

Add to the `urlpatterns` list (after the active-questionnaires path):

```python
    path("analysis-settings/", AnalysisSettingView.as_view(), name="analysis-settings"),
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `./venv/Scripts/python.exe manage.py test assessments.tests.test_api.AnalysisSettingApiTest -v 2`
Expected: PASS (4 tests).

- [ ] **Step 7: Commit**

```bash
git add backend/assessments/serializers.py backend/assessments/views.py backend/assessments/urls.py backend/assessments/tests/test_api.py
git commit -m "feat(assessments): analysis-settings API (read any assessor, write admin)"
```

---

## Task 4: Persist `confidence` + `overridden` on `AssessmentResult`

**Files:**
- Modify: `backend/assessments/models.py`
- Create: `backend/assessments/migrations/0004_*.py` (generated)

- [ ] **Step 1: Add the fields**

In `backend/assessments/models.py`, add to the `AssessmentResult` model (after the `classification` field):

```python
    confidence = models.PositiveSmallIntegerField(null=True, blank=True)
    overridden = models.BooleanField(default=False)
```

- [ ] **Step 2: Generate + apply the migration**

Run:
```bash
./venv/Scripts/python.exe manage.py makemigrations assessments
./venv/Scripts/python.exe manage.py migrate
```
Expected: creates a `0004_*` migration adding both fields and applies it.

- [ ] **Step 3: Verify the schema loads**

Run: `./venv/Scripts/python.exe manage.py test assessments.tests.test_models -v 2`
Expected: PASS (existing model tests still green with the new columns).

- [ ] **Step 4: Commit**

```bash
git add backend/assessments/models.py backend/assessments/migrations/
git commit -m "feat(assessments): store confidence + overridden on AssessmentResult"
```

---

## Task 5: Backend gate + analyze context + persist confidence

**Files:**
- Modify: `backend/assessments/views.py`
- Test: `backend/assessments/tests/test_api.py`

- [ ] **Step 1: Write the failing tests**

Add these methods inside the existing `AssessmentTakingTest` class in `backend/assessments/tests/test_api.py`. Its `setUp` defines `self.qn` with `self.q1` (yes_no) and `self.q2` (rating_scale), and `self.child`. Add a low-confidence payload helper + the gate tests:

```python
    def _low_conf_payload(self):
        # q1 scorable ("Yes" -> concern 1.0); q2 blank -> unscorable.
        # coverage 1/2, score 100 -> confidence round(100*(0.5*0.5 + 0.5*1.0)) = 75 -> below 80.
        return {
            "child": self.child.id, "questionnaire": self.qn.id, "assessment_type": "Intake",
            "classification": "Normal Development", "notes": "Limited data.",
            "responses": [
                {"question": self.q1.id, "answer": "Yes"},
                {"question": self.q2.id, "answer": ""},
            ],
        }

    def test_low_confidence_blocked_without_override(self):
        self._auth("p@racco1.gov.ph")
        resp = self.client.post("/api/assessments/", self._low_conf_payload(), format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data["code"], "override_required")
        self.assertEqual(resp.data["confidence"], 75)
        self.assertEqual(Assessment.objects.count(), 0)

    def test_low_confidence_saved_with_override(self):
        from assessments.models import AssessmentResult
        self._auth("p@racco1.gov.ph")
        payload = self._low_conf_payload()
        payload["override_acknowledged"] = True
        resp = self.client.post("/api/assessments/", payload, format="json")
        self.assertEqual(resp.status_code, 201)
        ar = AssessmentResult.objects.get()
        self.assertTrue(ar.overridden)
        self.assertEqual(ar.confidence, 75)

    def test_high_confidence_not_gated(self):
        from assessments.models import AssessmentResult
        self._auth("p@racco1.gov.ph")
        resp = self.client.post("/api/assessments/", self._assessment_payload(), format="json")
        self.assertEqual(resp.status_code, 201)
        self.assertFalse(AssessmentResult.objects.get().overridden)

    def test_gate_disabled_when_override_not_required(self):
        from assessments.models import AnalysisSetting
        s = AnalysisSetting.load()
        s.require_override_on_low_confidence = False
        s.save()
        self._auth("p@racco1.gov.ph")
        resp = self.client.post("/api/assessments/", self._low_conf_payload(), format="json")
        self.assertEqual(resp.status_code, 201)

    def test_analyze_returns_confidence_and_flag(self):
        self._auth("p@racco1.gov.ph")
        resp = self.client.post("/api/assessments/analyze/", {
            "questionnaire": self.qn.id,
            "responses": [{"question": self.q1.id, "answer": "Yes"}, {"question": self.q2.id, "answer": ""}],
        }, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["confidence"], 75)
        self.assertTrue(resp.data["flagged"])
        self.assertEqual(resp.data["min_confidence_threshold"], 80)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `./venv/Scripts/python.exe manage.py test assessments.tests.test_api.AssessmentTakingTest -v 2`
Expected: FAIL — low-confidence save currently returns 201 (no gate); analyze response has no `confidence`/`flagged`.

- [ ] **Step 3: Add the gate to `create()` and wire `overridden` through `perform_create`**

In `backend/assessments/views.py`, inside `AssessmentViewSet`, add a `create()` override **above** the existing `perform_create`:

```python
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        questionnaire = serializer.validated_data.get("questionnaire")
        setting = AnalysisSetting.load()
        confidence, flagged = 0, False
        if questionnaire is not None:
            responses = [{"question": r["question"].id, "answer": r.get("answer", "")}
                         for r in serializer.validated_data.get("responses", [])]
            confidence = scoring.score(questionnaire, responses)["confidence"]
            flagged = (setting.require_override_on_low_confidence
                       and confidence < setting.min_confidence_threshold)
        if flagged and not request.data.get("override_acknowledged"):
            return Response({
                "detail": "This result is below the minimum confidence threshold and requires practitioner override.",
                "code": "override_required",
                "confidence": confidence,
                "threshold": setting.min_confidence_threshold,
            }, status=status.HTTP_400_BAD_REQUEST)
        self._overridden = flagged
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
```

Then update `_persist_analysis` so it records confidence + the override flag. Change the `AssessmentResult.objects.create(...)` call to include both fields:

```python
        ar = AssessmentResult.objects.create(
            assessment=assessment,
            behavioral_score=result["behavioral_score"],
            classification=result["classification"],
            confidence=result["confidence"],
            overridden=getattr(self, "_overridden", False),
            assessment_date=assessment.assessment_date,
            assessment_type=assessment.assessment_type,
        )
```

- [ ] **Step 4: Add confidence + gate context to the `analyze` action**

Replace the body of the existing `analyze` method's final two lines (the `result = ...` / `rec = ...` / `return Response(...)`) with:

```python
        result = scoring.score(questionnaire, request.data.get("responses", []))
        rec = recommendations.recommend(result)
        setting = AnalysisSetting.load()
        flagged = (setting.require_override_on_low_confidence
                   and result["confidence"] < setting.min_confidence_threshold)
        return Response({
            **result, **rec,
            "min_confidence_threshold": setting.min_confidence_threshold,
            "require_override": setting.require_override_on_low_confidence,
            "flagged": flagged,
        }, status=status.HTTP_200_OK)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `./venv/Scripts/python.exe manage.py test assessments.tests.test_api.AssessmentTakingTest -v 2`
Expected: PASS — including the pre-existing `test_psychologist_creates_assessment_with_responses` (default payload → confidence 100 → not gated).

- [ ] **Step 6: Run the whole backend suite (no regressions)**

Run: `./venv/Scripts/python.exe manage.py test -v 1`
Expected: PASS (all apps green).

- [ ] **Step 7: Commit**

```bash
git add backend/assessments/views.py backend/assessments/tests/test_api.py
git commit -m "feat(assessments): server-enforced low-confidence override gate"
```

---

## Task 6: Expose `confidence` + `overridden` in the result serializer

**Files:**
- Modify: `backend/assessments/serializers.py`
- Test: `backend/assessments/tests/test_api.py`

- [ ] **Step 1: Write the failing test**

Add to `AssessmentTakingTest` in `test_api.py`:

```python
    def test_result_payload_includes_confidence(self):
        self._auth("p@racco1.gov.ph")
        self.client.post("/api/assessments/", self._assessment_payload(), format="json")
        resp = self.client.get("/api/assessments/")
        self.assertIn("confidence", resp.data[0]["result"])
        self.assertIn("overridden", resp.data[0]["result"])
        self.assertEqual(resp.data[0]["result"]["confidence"], 100)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `./venv/Scripts/python.exe manage.py test assessments.tests.test_api.AssessmentTakingTest.test_result_payload_includes_confidence -v 2`
Expected: FAIL with `KeyError: 'confidence'`.

- [ ] **Step 3: Add the fields to `AssessmentResultSerializer`**

In `backend/assessments/serializers.py`, extend the `AssessmentResultSerializer.Meta.fields` list to:

```python
        fields = ["behavioral_score", "classification", "generated_date",
                  "confidence", "overridden", "priority_level", "recommendation_text"]
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `./venv/Scripts/python.exe manage.py test assessments.tests.test_api.AssessmentTakingTest.test_result_payload_includes_confidence -v 2`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/assessments/serializers.py backend/assessments/tests/test_api.py
git commit -m "feat(assessments): surface confidence + overridden in result payload"
```

---

## Task 7: Wire `Settings.jsx` to the real API

**Files:**
- Modify: `frontend/src/pages/Settings.jsx`

- [ ] **Step 1: Load settings on mount + save via API**

In `frontend/src/pages/Settings.jsx`, add the API import and replace the hard-coded `threshold`/`override` state initialization with a server-loaded version. At the top, add:

```jsx
import React, { useState, useEffect } from 'react';
import api from '../api/client';
```

Inside the component, after the existing `useState` declarations, add load + save logic and an error state:

```jsx
  const [error, setError] = useState('');

  useEffect(() => {
    api.get('/analysis-settings/')
      .then((r) => { setThreshold(r.data.min_confidence_threshold); setOverride(r.data.require_override_on_low_confidence); })
      .catch(() => {});
  }, []);

  const saveConfig = async () => {
    setError('');
    try {
      await api.put('/analysis-settings/', {
        min_confidence_threshold: threshold,
        require_override_on_low_confidence: override,
      });
      setSaved(true); setTimeout(() => setSaved(false), 2600);
    } catch (err) {
      setError(err.response?.status === 403
        ? 'Only an Administrator can change these settings.'
        : 'Could not save settings. Please try again.');
    }
  };
```

Change the Save button's `onClick` from the inline toast handler to `onClick={saveConfig}`. Directly below the existing success `Alert` block (the `{saved && (...)}`), add an error banner:

```jsx
      {error && (
        <div style={{ position: 'fixed', top: 78, right: 26, zIndex: 50 }}>
          <Alert tone="danger" icon={<Icon name="alert-triangle" size={18} />} style={{ boxShadow: 'var(--shadow-lg)' }}>{error}</Alert>
        </div>
      )}
```

- [ ] **Step 2: Build to verify it compiles**

Run (from `frontend/`): `npm run build`
Expected: build succeeds with no errors.

- [ ] **Step 3: Verify in the browser**

Start the backend (`./venv/Scripts/python.exe manage.py runserver 8000` from `backend/`) and the preview server. Log in as `admin@racco1.gov.ph` / `admin1234`, open **Settings**, move the threshold slider, click **Save Configuration**, confirm the success toast. Reload the page and confirm the slider reflects the saved value (proves persistence). Screenshot for proof.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/Settings.jsx
git commit -m "feat(settings): persist confidence threshold + override toggle via API"
```

---

## Task 8: Assessment wizard — confidence display + override gate

**Files:**
- Modify: `frontend/src/pages/Assessment.jsx`

- [ ] **Step 1: Add override state**

In `frontend/src/pages/Assessment.jsx`, add a state hook next to the others (near `const [analysis, setAnalysis] = useState(null);`):

```jsx
  const [override, setOverride] = useState(false);
```

Reset it whenever a fresh analysis starts — in the `useEffect` that calls `/assessments/analyze/`, set `setOverride(false);` next to `setAnalysis(null); setAnalyzing(true);`.

- [ ] **Step 2: Send the override flag + handle the gate error in `submit()`**

In `submit()`, add `override_acknowledged: override,` to the `api.post('/assessments/', {...})` body. The existing `catch` already surfaces `err.response?.data`; refine it so the gate message is readable — replace the catch body with:

```jsx
    } catch (err) {
      const data = err.response?.data;
      if (data?.code === 'override_required') {
        setError(`Confidence ${data.confidence}% is below the ${data.threshold}% threshold — tick the override box to proceed.`);
      } else {
        setError(typeof data === 'string' ? data : JSON.stringify(data || 'Submit failed'));
      }
    }
```

- [ ] **Step 3: Show confidence + the override checkbox in step 4**

In the `AnalysisPanel` component (bottom of the file), inside the `{!analyzing && analysis && (...)}` block, add a confidence chip next to the score line — after the existing "based on N of M items" span:

```jsx
            {analysis.confidence != null && (
              <span className="racco-mono" style={{ fontSize: 12.5, fontWeight: 700, color: analysis.flagged ? 'var(--red-700)' : 'var(--text-strong)' }}>
                Confidence {analysis.confidence}%
              </span>
            )}
```

Then, in the main `step === 4` block in the `Assessment` component, immediately after `<AnalysisPanel analyzing={analyzing} analysis={analysis} />`, add the override gate UI:

```jsx
              {analysis?.flagged && (
                <div style={{ marginBottom: 16, padding: '12px 14px', borderRadius: 'var(--radius-lg)', background: 'var(--red-50)', border: '1px solid var(--red-100)' }}>
                  <p style={{ fontSize: 12.5, color: 'var(--red-700)', margin: '0 0 8px', lineHeight: 1.5 }}>
                    This result is below the minimum confidence threshold ({analysis.min_confidence_threshold}%). Review it before signing.
                  </p>
                  <label style={{ display: 'flex', gap: 9, alignItems: 'flex-start', fontSize: 13, color: 'var(--text-strong)', cursor: 'pointer' }}>
                    <input type="checkbox" checked={override} onChange={(e) => setOverride(e.target.checked)} style={{ marginTop: 2, accentColor: 'var(--blue-600)' }} />
                    <span>I have reviewed this low-confidence result and accept responsibility for the assessment.</span>
                  </label>
                </div>
              )}
```

Finally, update the **Sign & Submit** button's `disabled` prop (the `step === 4` branch of the footer) to also require the override when flagged:

```jsx
              : <Button variant="primary" disabled={!notes.trim() || sent || (analysis?.flagged && !override)} onClick={submit} iconLeft={<Icon name="pen-line" size={17} />}>Sign &amp; Submit to NACC</Button>}
```

- [ ] **Step 4: Build to verify it compiles**

Run (from `frontend/`): `npm run build`
Expected: build succeeds.

- [ ] **Step 5: Verify the gate in the browser**

With backend + preview running, log in as a psychologist (or admin), start a new assessment, and craft a low-confidence case (leave a scorable rating question effectively unscorable by the data, or use a questionnaire where coverage is partial) to trigger the flag. Confirm: the red callout + checkbox appear, **Sign & Submit stays disabled** until the box is ticked, ticking it enables submit, and a normal high-confidence assessment shows no callout and submits freely. Screenshot both states.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/Assessment.jsx
git commit -m "feat(assessment): show confidence + require override on low-confidence results"
```

---

## Task 9: Demo parity in `mockBackend.js`

**Files:**
- Modify: `frontend/src/api/mockBackend.js`

- [ ] **Step 1: Bump the demo DB key + seed default settings**

In `frontend/src/api/mockBackend.js`, change the storage key so existing demo DBs reseed with the new `settings` field:

```js
const KEY = 'nacc_demo_db_v3';
```

In `seed()`, add `settings` to the returned object:

```js
  return { seq: 1000, roles, users, guardians, children, questionnaires, assessments: [], activity,
           settings: { min_confidence_threshold: 80, require_override_on_low_confidence: true } };
```

- [ ] **Step 2: Mirror the confidence calc**

Add these helpers next to `scoreQ` (after the `scoreQ` function):

```js
const BOUNDARY_LOW = 34, BOUNDARY_HIGH = 67, BOUNDARY_MARGIN = 15, W_COV = 0.5, W_DEC = 0.5;
function confidenceFor(coverage, behavioral) {
  if (behavioral == null) return 0;
  const margin = Math.min(Math.abs(behavioral - BOUNDARY_LOW), Math.abs(behavioral - BOUNDARY_HIGH));
  const decisiveness = Math.min(margin / BOUNDARY_MARGIN, 1);
  return Math.round(100 * (W_COV * coverage + W_DEC * decisiveness));
}
```

In `scoreQ`, compute and return confidence on **both** return paths. Replace the two `return { ... }` lines:

```js
  if (!items.length) return { behavioral_score: null, classification: 'Needs Monitoring', scored_count: 0, total_count: total, top_concerns: [], confidence: 0 };
```

and:

```js
  const coverage = total ? items.length / total : 0;
  return { behavioral_score: score, classification, scored_count: items.length, total_count: total, top_concerns: top, confidence: confidenceFor(coverage, score) };
```

(Add the `const coverage = ...` line just before the final return.)

- [ ] **Step 3: Add the settings endpoint + the gate to the mock handler**

In `handle()`, add a settings route (place it near the assessments routes):

```js
  if (url === '/analysis-settings/' && method === 'get') return ok(db.settings);
  if (url === '/analysis-settings/' && method === 'put') {
    if (!actor || actor.role_name !== 'Administrator') return ok({ detail: 'Admin only' }, 403);
    db.settings = { min_confidence_threshold: Number(body.min_confidence_threshold), require_override_on_low_confidence: !!body.require_override_on_low_confidence };
    save();
    return ok(db.settings);
  }
```

Update the analyze route to include the gate context:

```js
  if (url === '/assessments/analyze/' && method === 'post') {
    const qn = db.questionnaires.find((x) => x.id === Number(body.questionnaire));
    const result = scoreQ(qn || { questions: [] }, body.responses || []);
    const flagged = db.settings.require_override_on_low_confidence && result.confidence < db.settings.min_confidence_threshold;
    return ok({ ...result, ...recommend(result), min_confidence_threshold: db.settings.min_confidence_threshold, require_override: db.settings.require_override_on_low_confidence, flagged });
  }
```

In the `/assessments/` POST route, enforce the gate before creating, and store confidence + overridden. Right after `const result = scoreQ(...)` and `const rec = recommend(result)`, add:

```js
    const flagged = db.settings.require_override_on_low_confidence && result.confidence < db.settings.min_confidence_threshold;
    if (flagged && !body.override_acknowledged) {
      return ok({ detail: 'Below confidence threshold; override required.', code: 'override_required', confidence: result.confidence, threshold: db.settings.min_confidence_threshold }, 400);
    }
```

Then add `confidence: result.confidence, overridden: flagged` to the `result: { ... }` object inside the created assessment `a`.

- [ ] **Step 4: Build to verify it compiles**

Run (from `frontend/`): `npm run build`
Expected: build succeeds.

- [ ] **Step 5: Verify the demo path (if a demo build is used)**

If running with `VITE_DEMO_MODE=true`, repeat the Task 8 browser check against the mock: low-confidence assessment is gated, override unlocks it, Settings persists across reload. Otherwise confirm the build is clean.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/mockBackend.js
git commit -m "feat(demo): mirror confidence + override gate in mock backend"
```

---

## Task 10: Full-system verification + wrap-up

- [ ] **Step 1: Backend suite green**

Run (from `backend/`): `./venv/Scripts/python.exe manage.py test -v 1`
Expected: all tests pass (the original suite plus the new analysis/settings/gate tests).

- [ ] **Step 2: Frontend builds clean**

Run (from `frontend/`): `npm run build`
Expected: success.

- [ ] **Step 3: End-to-end smoke (real backend)**

Start both servers, log in, and walk the full flow once: set the threshold in Settings → run a low-confidence assessment → confirm it's blocked, tick override → confirm it saves → open Assessment Results and confirm the saved result carries the confidence. Capture a screenshot of the gated state and the saved result.

- [ ] **Step 4: Final review + offer to finish the branch**

Run `git log --oneline main..HEAD` to review the commit series, then use the `superpowers:finishing-a-development-branch` skill to decide on merge/PR/cleanup.

---

## Self-Review (completed during planning)

- **Spec coverage:** §3 confidence → Task 1; §4 setting model+API → Tasks 2–3; §5 gate → Task 5; §6 result fields → Tasks 4 & 6; §7 analyze context → Task 5; §8 frontend → Tasks 7–8; §9 mock parity → Task 9; §9 (spec) tests → embedded per task. All covered.
- **Placeholder scan:** every code step contains complete code; every test step has concrete assertions with pre-computed expected values (confidence 100/75/67/51/0).
- **Type/name consistency:** `confidence_for` (engine), `AnalysisSetting.load()`, `AnalysisSettingSerializer`, `AnalysisSettingView`, endpoint `/api/analysis-settings/`, request flag `override_acknowledged`, response `code: "override_required"`, result fields `confidence`/`overridden` — used identically across backend, frontend, and mock.
- **Known cross-checks:** default `_assessment_payload` (q1 "Yes", q2 "4") → score 87.5, coverage 1.0 → confidence 100 (not gated), so the pre-existing assessment tests keep passing after the gate is added.
