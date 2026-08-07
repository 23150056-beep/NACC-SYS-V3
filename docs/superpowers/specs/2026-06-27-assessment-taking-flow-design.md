# Assessment-Taking Flow — Design

- **Date:** 2026-06-27
- **Status:** Approved (design)
- **Phase:** Phase 2, sub-feature **#2 of 3** (after Questionnaire Builder; before Child Respondent).
- **Related:** [System Design](2026-06-22-nacc-system-design.md), [Questionnaire Builder](2026-06-27-questionnaire-builder-design.md)

---

## 1. Problem & Goal

The `Assessment.jsx` wizard is polished but fake: step 3 shows 4 hardcoded questions from `seedData`, step 4 "AI analysis" just sums them, and **"Sign & Submit" persists nothing**. Now that real published questionnaires exist, make the wizard real.

**Goal:** a psychologist selects a child + a published questionnaire, answers its real questions, records clinical notes and a manual classification, and the system **persists** an `Assessment` with all its `Response` rows.

## 2. Scope

**In:** real questionnaire selection, real question rendering + answer capture, persistence of `Assessment` + `Response` + the psychologist's notes/classification, a "my assessments" list for confirmation.

**Out (deferred to Phase 3):** rule-based scoring, AI classification, emotional summary, and recommendations. The wizard's "AI Analysis" panel becomes a clearly-labeled **"Automated analysis arrives in Phase 3"** placeholder. Results browsing/reporting (the Report page) stays as-is. Draft/resume of a partially-finished assessment is out (one-shot submit — YAGNI).

## 3. Schema additions (additive — one migration)

`Assessment` represents the **practitioner's** record. The AI's future output (score, AI classification, recommendations) already has its own tables (`AssessmentResult`, `Recommendation`) for Phase 3, so practitioner judgment stays separate. `Assessment` gains:

| Field | Type | Purpose |
|---|---|---|
| `questionnaire` | FK → `Questionnaire`, `null=True`, `on_delete=SET_NULL` | Which instrument was used. |
| `notes` | TextField, blank | The psychologist's clinical notes. |
| `classification` | CharField(50), blank | The psychologist's **manual** classification. |

`status` flips from its `"ongoing"` default to `"completed"` on submit.

## 4. Backend API (`assessments` app)

**Decoupled permission** (in `accounts/permissions.py`), deliberately independent of `INSTRUMENT_MANAGER_ROLES`:
```python
# Roles allowed to take/administer assessments. Kept SEPARATE from instrument
# management so reverting that to admin-only never blocks taking assessments.
ASSESSMENT_TAKER_ROLES = (Role.ADMINISTRATOR, Role.PSYCHOLOGIST)

class CanTakeAssessments(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated
                    and _role_name(request) in ASSESSMENT_TAKER_ROLES)
```

Endpoints (all `CanTakeAssessments`):
- **`GET /api/active-questionnaires/`** — read-only list of `status="active"` questionnaires with nested questions (reuses `QuestionnaireSerializer`). This is the taker's read path, independent of instrument-management rights.
- **`POST /api/assessments/`** — creates an `Assessment` in one call with nested `responses` + `notes` + `classification`. The view sets `psychologist = request.user` and `status = "completed"` server-side (never trusted from the client). Logs to the activity feed (`category=record`, `entity_type="Assessment"`, label = child's name).
- **`GET /api/assessments/`** — lists assessments; a psychologist sees **their own**, an admin sees **all**. Lightweight serializer (id, child name, questionnaire title, classification, status, date).

**Serializers:**
- `ResponseWriteSerializer` — `question` (PK), `answer` (text).
- `AssessmentWriteSerializer` — `child`, `questionnaire`, `assessment_type`, `notes`, `classification`, `responses[]`; `create()` writes the assessment + its responses. `psychologist`/`status` are **not** client-writable.
- `AssessmentListSerializer` — read view with `child_name`, `questionnaire_title`, `psychologist_name`, `classification`, `status`, `assessment_date`.

Wire `assessments` viewset routes into the existing `assessments/urls.py` (router already there for questionnaires); add the `active-questionnaires` route.

## 5. Frontend — make `Assessment.jsx` real

Keep the 4-step shell; replace the fake parts:
- **Step 1 (select child):** unchanged (already real).
- **Step 2 (session):** replace the hardcoded "Session Type" select with a **questionnaire picker** populated from `GET /active-questionnaires/`, plus the free-text/`Select` assessment type. "Next" disabled until a questionnaire is chosen.
- **Step 3 (questionnaire):** render the chosen questionnaire's real questions **by `question_type`**:
  - `rating_scale` → 1–5 buttons (current control), `yes_no` → Yes/No buttons, `multiple_choice` / `emotion` → buttons from the question's `options`.
  - Answers captured in state keyed by question id; "Run" disabled until all answered. Stored as text in `Response.answer`.
- **Step 4 (review + sign):** the AI box → a muted **"Automated analysis arrives in Phase 3"** placeholder. Keep the **practitioner classification** `Select` and **clinical notes** textarea (required). Remove the "do you agree with the AI?" control (no AI yet). **Sign & Submit** → `POST /api/assessments/` with `{ child, questionnaire, assessment_type, classification, notes, responses: [{question, answer}] }`; on success show a real confirmation and reset (or link to the assessments list).
- Drop the `seedData` `questions` / `scoreToResult` imports (the fake AI).

## 6. Testing

Backend (`assessments/tests/test_api.py`, existing style):
- Creating an assessment with nested responses persists the `Assessment` (status `completed`, `psychologist` = caller) and one `Response` per answer; `notes`/`classification` saved.
- Permission: Psychologist ✅, Admin ✅, Staff ❌ (403) for `POST /assessments/` and `GET /active-questionnaires/`.
- `GET /active-questionnaires/` returns only `active` (not draft/archived).
- A psychologist's `GET /assessments/` returns only their own; admin sees all.

Frontend: `npm run build` + browser smoke — run a published questionnaire end-to-end as a psychologist and confirm the assessment is saved (appears in the list / activity feed).

## 7. File change summary

**Backend — modify:** `assessments/models.py` (3 fields), `assessments/serializers.py` (assessment + response serializers), `assessments/views.py` (`AssessmentViewSet`, active-questionnaires view), `assessments/urls.py`, `accounts/permissions.py` (`CanTakeAssessments`); new migration; `assessments/tests/test_api.py`.

**Frontend — modify:** `src/pages/Assessment.jsx` (real selection, rendering, submit). No new files.
