# Phase 3 — Free Rule-Based Analysis Engine — Design

- **Date:** 2026-06-27
- **Status:** Approved (design)
- **Phase:** Phase 3, sub-feature **#1** (the engine + wizard). Sub-feature #2 (results page wired to real data) is a fast follow.
- **Related:** [System Design](2026-06-22-nacc-system-design.md), [Assessment-Taking Flow](2026-06-27-assessment-taking-flow-design.md)

---

## 1. Problem & Goal

Phase 2 saves assessments (answers + the psychologist's notes/classification) but never interprets them — the wizard shows an *"Automated analysis arrives in Phase 3"* placeholder. **Goal:** turn saved responses into a **`behavioral_score`**, a triage **`classification`** (Normal / Needs Monitoring / Needs Counseling Attention), and a written **recommendation + priority**, filling the `AssessmentResult` and `Recommendation` tables (already migrated, empty).

**Hard constraint:** **100% free — no LLM, no paid API, ever.** Pure rule-based scoring + template recommendations, behind a swappable interface so an LLM *could* replace the recommendation step later, but nothing depends on it.

## 2. Scope

**In:** the scoring key on questions, the scoring engine, template recommendations, an `/analyze/` preview endpoint, persistence of `AssessmentResult` + `Recommendation` on submit, and the wizard step-4 showing real output.
**Out:** any LLM; the "Assessment Results" page wiring (sub-feature #2).

## 3. Two taxonomies kept separate (important)

- **Engine triage** → `AssessmentResult.classification` = **Normal / Needs Monitoring / Needs Counseling Attention** (+ `behavioral_score`). This is the automated decision-support output.
- **Practitioner clinical category** → `Assessment.classification` (Phase 2) = the psychologist's own label (Trauma / Behavioral / Adjustment / Normal Development).

These are different things and both persist. The wizard does **not** overwrite the practitioner's dropdown with the engine triage — it shows the engine result for the psychologist to consider, and they set their clinical category themselves.

## 4. Schema — the scoring key (small; one migration)

Add to `Question`:
- `concern_direction` — CharField, choices `higher` / `lower`, default `higher`.
- `concern_options` — JSONField (list of option strings), default empty.

Per-question concern mapping:
| Type | Scored using |
|---|---|
| `rating_scale` (1–5) | `concern_direction`: `higher` → `(v−1)/4`; `lower` → `(5−v)/4` |
| `yes_no` | concern answer = `Yes` if `higher` else `No`; 1 if matched else 0 |
| `multiple_choice` / `emotion` | 1 if the chosen option ∈ `concern_options`, else 0; **un-marked (empty) → not scored** |

Defaults keep existing questionnaires working (rating/yes-no score immediately under `higher`).

## 5. Scoring engine — `assessments/analysis/scoring.py`

`score(questionnaire, responses) -> dict`:
- Compute a concern value in `[0,1]` per scorable answered question (above); skip non-scorable (unknown type, blank, choice with no `concern_options`).
- `behavioral_score = round(mean(concerns) * 100, 2)` (0–100); `scored_count`, `total_count`.
- **Classification thresholds** (module constants): `< 34` → **Normal**; `34–66` → **Needs Monitoring**; `>= 67` → **Needs Counseling Attention**.
- `top_concerns` = up to 2 question texts with concern ≥ 0.5 (highest first).
- **Edge case:** `scored_count == 0` → `behavioral_score = None`, classification **Needs Monitoring**, coverage note "0 of M items scorable".

Returns `{behavioral_score, classification, scored_count, total_count, top_concerns}`. Pure function, fully unit-testable, no DB writes.

## 6. Recommendation templates — `assessments/analysis/recommendations.py`

`recommend(score_result) -> dict` returns `{recommendation_text, priority_level}` from the classification:
- **Normal** → priority **Low**; "The child appears to be adjusting well; responses show no significant behavioral concerns. Suggested actions: continue routine periodic check-ins."
- **Needs Monitoring** → priority **Medium**; "Some responses indicate mild-to-moderate behavioral concerns[, notably around: <top concerns>]. Suggested actions: increase observation, schedule a follow-up within 4 weeks, and introduce light supportive measures."
- **Needs Counseling Attention** → priority **High**; "Responses indicate notable behavioral concerns requiring attention[, notably around: <top concerns>]. Suggested actions: arrange focused counseling support, coordinate with the house parent/guardian, and reassess within 1–2 weeks."

Every `recommendation_text` ends with: *"This is decision support, not a diagnosis; the final determination rests with the licensed professional."*

A thin `RecommendationEngine` seam (one factory `get_recommender()`) returns the free `TemplateRecommender` now; an LLM recommender can replace it later with no caller change.

## 7. Backend API (one engine, two entry points — DRY)

- **`POST /api/assessments/analyze/`** (`CanTakeAssessments`) — body `{questionnaire, responses:[{question, answer}]}`; runs `score` + `recommend` and returns the result **without persisting** (so the wizard can preview before signing). Mirrors the `/extract/` pattern.
- **`POST /api/assessments/`** (submit) — after saving the `Assessment` + `Response`s, the server **re-runs the same engine** and creates `AssessmentResult` (score + triage classification) + `Recommendation` (text + priority). Client-sent scores are never trusted.
- Logs an activity entry as today.

Serializer: an `AssessmentResultSerializer` (read) used in the analyze response and (sub-feature #2) the results page.

## 8. Frontend — wizard step 4 becomes real (`Assessment.jsx`)

- On entering **step 4** (all answered), call `/analyze/` with the chosen questionnaire + answers; show the **real** analysis where the placeholder was: the triage **classification**, the **score** (0–100), a **coverage note** ("based on N of M items"), the **summary**, and the **priority**.
- The **practitioner clinical-category** dropdown + **notes** stay exactly as in Phase 2 (the psychologist's own judgment) — *not* overwritten by the engine.
- **Sign & Submit** persists as today; the backend attaches the `AssessmentResult` + `Recommendation`.
- A small loading state while `/analyze/` runs; if it fails, step 4 still works (placeholder text + manual flow), so analysis never blocks signing.

## 9. Testing

Backend unit tests (`assessments/tests/test_analysis.py`): each question type + direction maps to the right concern; the three classification bands; `top_concerns`; the zero-scorable edge case; `recommend()` returns the right priority per band. API tests: `/analyze/` returns a result without persisting; submitting an assessment creates an `AssessmentResult` + `Recommendation`; permissions (Staff → 403). The existing suite stays green.

Frontend: `npm run build` + a browser run of a full assessment showing the real analysis at step 4.

## 10. File change summary

**Backend — new:** `assessments/analysis/{__init__,scoring,recommendations}.py`, `assessments/tests/test_analysis.py`; a migration. **Modify:** `assessments/models.py` (2 `Question` fields), `assessments/serializers.py` (result serializer + accept concern fields in the question serializer), `assessments/views.py` (`analyze` action + persist-on-submit in `AssessmentViewSet`), `assessments/tests/test_api.py`.

**Frontend — modify:** `src/pages/Assessment.jsx` (call `/analyze/`, show real output), `src/pages/Questionnaires.jsx` (the per-question concern controls in the builder).
