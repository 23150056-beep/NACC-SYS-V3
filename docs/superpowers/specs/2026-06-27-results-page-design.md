# Phase 3 #2 — Assessment Results Page (Real Data) — Design

- **Date:** 2026-06-27
- **Status:** Approved (design)
- **Phase:** Phase 3, sub-feature **#2** (completes Phase 3's user-facing loop).
- **Related:** [Analysis Engine](2026-06-27-analysis-engine-design.md), [Assessment-Taking Flow](2026-06-27-assessment-taking-flow-design.md)

---

## 1. Problem & Goal

The "Assessment Results" page (`Report.jsx`) still shows **demo data** — it derives a fake severity from `/children/` and reads narrative notes from `seedData`. Now that assessments persist real `AssessmentResult`s (Phase 3 #1), wire this page to **real saved assessments + their engine analysis**. This answers *"where do I see my assessments and their results."* No schema change.

## 2. Scope

**In:** read API for assessments-with-results, role-scoped visibility, and the existing table + drawer rewired to real data.
**Access:** Psychologist sees **own**; Admin + Staff see **all**; **Staff is read-only** (view the table, no detail drawer, can't run assessments).
**Out:** charts/trends/date-range reports (Phase 4); any new screens.

## 3. Backend

- **Permission split on `AssessmentViewSet`** via `get_permissions()`:
  - read (`list`, `retrieve`) → **`CanViewResults`** (Admin + Psychologist + Staff),
  - everything else (`create`, `analyze`) → **`CanTakeAssessments`** (Admin + Psychologist — unchanged).
  - New in `accounts/permissions.py`: `RESULT_VIEWER_ROLES = (Role.ADMINISTRATOR, Role.PSYCHOLOGIST, Role.STAFF)` + a `CanViewResults` class.
- **Queryset scoping** (`get_queryset`): if the caller is a **Psychologist** → filter to `psychologist=self.request.user`; **Admin/Staff** → all.
- **Serializer:** extend `AssessmentListSerializer` to include:
  - `result` — nested `AssessmentResultSerializer` (read-only): `behavioral_score`, triage `classification`, `priority_level`, `recommendation_text`. **Null** for assessments without a result (older / no questionnaire).
  - `child_case_type` (source `child.case_type`) and `notes` (the practitioner's clinical notes) for the drawer.
  - (Existing fields kept: `child_name`, `psychologist_name`, `assessment_type`, `classification` [practitioner clinical], `status`, `assessment_date`.)

## 4. Frontend (`Report.jsx` — rewire, no new file)

- Fetch **`GET /api/assessments/`**; drop the `/children/` + `deriveSeverity` + `resultMeta`/`statusToResult` demo path on this page.
- **Table rows** (one per assessment): Child (name + `C-####` ref from id), Case Type, **Outcome** (engine `result.classification` → the severity badge; "—" if no result), **Score** (`result.behavioral_score` / 100, or "—"), Psychologist, Last Session (`assessment_date`). **Empty state** when there are none.
- **Detail drawer** — opens for **Psychologist/Admin only** (Staff rows are not clickable, preserving today's read-only behavior):
  - **Automated analysis** block: engine `classification` + score + `recommendation_text` + `priority_level`.
  - **Practitioner** block: the clinical `classification`, "signed by" `psychologist_name`, and `notes`.
  - The two are visually distinct (engine vs professional), consistent with the wizard.
- Maps engine triage to the existing severity tones: Normal→standard/success, Needs Monitoring→moderate/warning, Needs Counseling Attention→high/danger.

## 5. Testing

Backend (`assessments/tests/test_api.py`): Staff can `GET /api/assessments/` (200) and sees all; a Psychologist sees only their own; Staff still gets 403 on `POST`; a submitted assessment's payload includes a non-null `result` with `behavioral_score` + `classification`. The existing suite stays green.

Frontend: `npm run build` + a browser check — submit an assessment, open Assessment Results, confirm the row shows the real outcome + score and the drawer shows the engine analysis + practitioner notes.

## 6. File change summary

**Backend — modify:** `accounts/permissions.py` (`CanViewResults` + `RESULT_VIEWER_ROLES`), `assessments/serializers.py` (`AssessmentListSerializer` additions), `assessments/views.py` (`get_permissions` + queryset scoping), `assessments/tests/test_api.py`.

**Frontend — modify:** `src/pages/Report.jsx` (real data + drawer); remove its `seedData` demo imports.
