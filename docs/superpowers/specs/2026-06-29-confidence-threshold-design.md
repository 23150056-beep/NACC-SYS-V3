# Confidence Threshold — Make the AI-Engine Gate Functional — Design

- **Date:** 2026-06-29
- **Status:** Approved (design)
- **Phase:** Phase 3 follow-on (analysis engine hardening).
- **Related:** [Analysis Engine](2026-06-27-analysis-engine-design.md), [Assessment-Taking Flow](2026-06-27-assessment-taking-flow-design.md)

---

## 1. Problem & Goal

The Settings page advertises an **"AI Engine · Assessment Support → Minimum confidence threshold"** slider whose help text promises *"Results below {threshold}% confidence are flagged for mandatory practitioner override before saving."* Today this is entirely cosmetic:

- the slider is local React state; **Save Configuration** is a no-op toast (persists nothing);
- the backend has **zero** references to confidence/threshold;
- the rule-based engine produces no confidence value at all, so there is nothing to gate on.

**Goal:** make the feature real, end to end, with **no LLM and no paid API** (consistent with the free-engine constraint). The engine emits a deterministic, explainable `confidence`; the threshold + override toggle persist; and a low-confidence result is **blocked from saving** until a practitioner explicitly overrides it.

**Hard constraint:** 100% free / deterministic. Confidence is computed from data the engine already has — no model, no network.

## 2. Scope

**In:** confidence in the scoring engine; a persisted singleton setting (threshold + require-override toggle) with a GET/PUT API; backend-enforced save gate keyed on an `override_acknowledged` flag; `confidence` + `overridden` on the saved result; Settings page wired to the API; the assessment wizard showing confidence and an override checkbox; demo parity in `mockBackend.js`; tests.

**Out:** any LLM swap; Partner Agency Name and NACC auto-sync settings (remain cosmetic mocks); reworking the existing triage/recommendation logic.

## 3. The confidence metric (engine) — `assessments/analysis/scoring.py`

`score()` gains one output, **`confidence`** — an integer **0–100** — derived from two explainable signals:

- **Coverage** = `scored_count / total_count` (0 when `total_count == 0`). Fraction of questions that actually produced a score; lots of skipped/unscorable answers ⇒ thinner evidence ⇒ lower confidence.
- **Decisiveness** = how far `behavioral_score` sits from the nearest classification boundary (34 and 67). `margin = min(|score − 34|, |score − 67|)`, normalized as `decisiveness = min(margin / BOUNDARY_MARGIN, 1.0)` with **`BOUNDARY_MARGIN = 15`**. A score on a boundary (e.g. 66, a coin-flip between Needs Monitoring / Needs Counseling) ⇒ 0; a score ≥15 points clear of both boundaries (e.g. 12, 50, 90) ⇒ 1.0.

**Formula (module constants, tunable):**

```
W_COVERAGE = 0.5
W_DECISIVENESS = 0.5
confidence = round(100 * (W_COVERAGE * coverage + W_DECISIVENESS * decisiveness))
```

**Edge cases:** `scored_count == 0` ⇒ `behavioral_score = None`, `coverage = 0`, `decisiveness = 0` ⇒ **`confidence = 0`** (always flagged — forces human review). `total_count == 0` ⇒ `coverage = 0` (guard against divide-by-zero).

`confidence` is added to **both** return dicts in `score()`. It is decision support only; it never changes the score, classification, or recommendation.

## 4. Persisted setting (backend) — singleton model + API

No settings store exists. Add a **singleton** `AnalysisSetting` model in the `assessments` app (cohesive with the engine it governs; avoids a new app):

| Field | Type | Default |
|---|---|---|
| `min_confidence_threshold` | PositiveSmallInteger (50–99) | `80` |
| `require_override_on_low_confidence` | Boolean | `True` |

- Singleton via a `load()` classmethod (get-or-create `pk=1`); `save()` pins `pk=1`.
- One migration. Optionally seed the row in `seed_initial_data` (otherwise `load()` creates it lazily).

**API** (`/api/analysis-settings/`, `RetrieveUpdateAPIView` over the singleton — mounted outside the `assessments/` router prefix to avoid colliding with the `assessments/<pk>/` detail route):
- **GET** — any authenticated assessor (so the wizard/UI can read the threshold). Returns `{min_confidence_threshold, require_override_on_low_confidence}`.
- **PUT/PATCH** — **Administrator only.**

## 5. The gate (backend-enforced) — `AssessmentViewSet`

The save path (`POST /assessments/`) enforces the gate **before committing**:

1. Validate the write serializer (child, questionnaire, responses, notes…).
2. Compute analysis (`scoring.score`) from the submitted responses.
3. Load `AnalysisSetting`. `flagged = require_override AND confidence < min_confidence_threshold`.
4. If `flagged` AND request body does **not** include `override_acknowledged: true` ⇒ **reject `HTTP 400`** with `{"detail": "...", "confidence": N, "threshold": T, "code": "override_required"}`.
5. Otherwise save the assessment, persist the result with `confidence` and `overridden = flagged` (true only when it was below threshold and accepted via override).

Implementation: override `create()` (or guard within `perform_create`) so the gate runs against `serializer.validated_data` and aborts cleanly with no partial writes.

## 6. Result storage — `AssessmentResult`

Add two fields (one migration):

| Field | Type | Meaning |
|---|---|---|
| `confidence` | PositiveSmallInteger, null=True | engine confidence at save time |
| `overridden` | Boolean, default False | saved below threshold via explicit override |

`_persist_analysis` writes both. This lets the Assessment Results / Report view show *"accepted at 72% — practitioner-overridden."*

## 7. `analyze` preview endpoint

`POST /assessments/analyze/` already returns `{**result, **rec}`. It now also returns `confidence` (via the engine) plus the active gate context so the UI needs no second call: `min_confidence_threshold`, `require_override`, and computed `flagged`.

## 8. Frontend

- **`Settings.jsx`** — on mount, GET `/analysis-settings/` to initialize the threshold slider and the override toggle from the server. **Save Configuration** does a real PUT (Admin); the success toast becomes truthful. Errors surfaced. (The Settings route is already Admin-only via `roles={['Administrator']}`, so non-admins never reach the page.)
- **`Assessment.jsx`** —
  - `AnalysisPanel` shows the **confidence %** next to the score, and when `flagged`, a distinct low-confidence callout explaining why review is required.
  - When `analysis.flagged`, render an **override checkbox**: *"I have reviewed this low-confidence result and accept responsibility for the assessment."*
  - **Sign & Submit** is disabled until `notes` is filled **AND** (`!flagged` **OR** override checked).
  - `submit()` includes `override_acknowledged: <bool>`; backend `400 override_required` is surfaced as an inline error.
- **`mockBackend.js`** — mirror the confidence calc, settings read/write, and the gate so the capstone demo works on the mock path.

## 9. Testing

**Engine (`tests/test_analysis.py`):** full coverage + decisive score ⇒ high confidence; low coverage ⇒ low; boundary score (e.g. 66) ⇒ low; zero-scored ⇒ `confidence == 0`.

**View/gate tests:** flagged save without override ⇒ `400 override_required` and **no** Assessment row created; flagged save with `override_acknowledged: true` ⇒ `201`/`200`, result persisted with `overridden == True`; high-confidence save ⇒ succeeds untouched (`overridden == False`); `require_override == False` ⇒ never gated regardless of confidence.

**Settings:** GET returns defaults; PUT as Administrator updates; PUT as non-admin ⇒ `403`.

## 10. Risks / notes

- **Threshold range** is clamped 50–99 to match the slider; backend validates.
- **Weights/margin** live as module constants so they can be tuned without touching logic — and are easy to defend in a panel ("confidence = half coverage, half how far the score is from a decision boundary").
- The gate is **server-side**, so a direct API call cannot bypass it; the UI checkbox merely supplies the flag.
