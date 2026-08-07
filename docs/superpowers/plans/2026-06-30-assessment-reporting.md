# Assessment Reporting — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Steps use checkbox (`- [ ]`).

**Goal:** Add the Child Progress Report (per-child, over time; psychologist edit / staff read-only) and Agency Assessment Summary (weekly/monthly/yearly; admin + staff), with editable-with-audit + lock on assessments, dashboard wired to real data, and print-to-PDF + CSV export.

**Architecture:** Backend exposes report endpoints that aggregate existing Assessment/AssessmentResult rows (Django ORM); a lock field makes signed assessments immutable after finalize. Frontend renders report views with `recharts` + `@media print` CSS; the dashboard reads the summary endpoint instead of `seedData`.

**Tech Stack:** Django REST Framework + SQLite; React + Vite + recharts. Builds on the access/assignment foundation (psychologist scoping already enforced).

**Spec:** `docs/superpowers/specs/2026-06-30-assessment-reporting-design.md`

---

## File Structure
**Backend:**
- `backend/assessments/models.py` — `Assessment.is_locked`, `locked_at`
- `backend/assessments/reports.py` (new) — trajectory + summary aggregation helpers
- `backend/assessments/views.py` — `partial_update` (edit notes/classification), `finalize` action, `ChildReportView`, `SummaryReportView`
- `backend/assessments/serializers.py` — `AssessmentEditSerializer`
- `backend/assessments/urls.py` — report routes
- migration

**Frontend:**
- `frontend/src/pages/ChildProgressReport.jsx` (new)
- `frontend/src/pages/AgencySummary.jsx` (new)
- `frontend/src/pages/Report.jsx` — link each row to the child progress report
- `frontend/src/pages/Dashboard.jsx` — read `/reports/summary/`
- `frontend/src/components/Sidebar.jsx` — add "Agency Summary" (admin+staff)
- `frontend/src/App.jsx` — routes
- `frontend/src/index.css` (or ui) — print styles

---

## Phase 1 — Lock model
### Task 1: `is_locked` + `locked_at`
- [ ] Add to `Assessment`: `is_locked = models.BooleanField(default=False)`, `locked_at = models.DateTimeField(null=True, blank=True)`.
- [ ] makemigrations assessments → migrate → commit.

## Phase 2 — Edit-with-audit + finalize
### Task 2: Edit own notes/classification (blocked if locked)
**Files:** `assessments/serializers.py`, `assessments/views.py`; Test `assessments/tests/`.
- [ ] Write tests: owning psychologist PATCHes notes+classification → 200, persists, ActivityLog written; non-owner → 404/403; locked assessment → 400; result fields ignored.
- [ ] Add `AssessmentEditSerializer` (fields: `notes`, `classification`). Override `AssessmentViewSet.partial_update`: require `psychologist == request.user`; reject if `is_locked` (`"This assessment is finalized and can no longer be edited."`); save only notes/classification; `log_activity(updated, record, Assessment, recipient=child.assigned_psychologist)`.
- [ ] Run → pass; commit.

### Task 3: Finalize (lock) action
- [ ] Write test: owning psychologist POST `/api/assessments/<id>/finalize/` → `is_locked=True`, `locked_at` set; a second edit → 400.
- [ ] Add `@action(detail=True, methods=["post"]) finalize`: owner-only; set lock; log. Run → pass; commit.

## Phase 3 — Report endpoints
### Task 4: Trajectory + child report
**Files:** `assessments/reports.py`, `assessments/views.py`, `assessments/urls.py`; Test.
- [ ] Write tests: `GET /api/reports/child/<id>/` returns child + ordered assessments + `trajectory` in {improving, stable, worsening, baseline}. Improving when latest score >5 lower than prior; worsening when >5 higher; stable within ±5; baseline with <2 scored. Psychologist scoping respected (only assigned/visible).
- [ ] `reports.py`: `trajectory(scores)` per spec §4. `ChildReportView` (GenericAPIView) reuses `AssessmentViewSet` scoping logic for the child's assessments. Route `reports/child/<int:child_id>/`.
- [ ] Run → pass; commit.

### Task 5: Agency summary + CSV
**Files:** `assessments/reports.py`, `assessments/views.py`, `assessments/urls.py`; Test.
- [ ] Write tests: `GET /api/reports/summary/?range=monthly` (admin/staff) returns totals, classification breakdown, priority breakdown, per-psychologist rows, attention list, trend buckets; psychologist → 403; `&format=csv` returns `text/csv`. Date-range filter respected.
- [ ] `reports.py`: `summary(qs, range, frm, to)` building the aggregates via ORM `values().annotate(Count)`. `SummaryReportView` (admin+staff); CSV branch using `csv` + `HttpResponse`. Routes.
- [ ] Run → pass; commit.

## Phase 4 — Frontend
### Task 6: ChildProgressReport view
- [ ] New `ChildProgressReport.jsx`: fetch `/reports/child/<id>/`; render header, trajectory badge, recharts score-over-time line with bands, history table, latest recommendation + notes, print button (`window.print()`); psychologist gets inline edit (notes/classification) on unlocked assessments + Finalize. Route `/report/child/:id`. Link from `Report.jsx` rows. Commit.

### Task 7: AgencySummary view
- [ ] New `AgencySummary.jsx`: period toggle (Weekly/Monthly/Yearly) + custom range; KPI cards; recharts trend; per-psychologist table; attention list; Print + CSV (download) buttons. Route `/reports/summary` (admin+staff). Sidebar item under Governance. Commit.

### Task 8: Dashboard real data
- [ ] `Dashboard.jsx`: replace `metrics`/`trendByRange`/`caseTrends`/`casesByPsychologist` seedData with `/reports/summary/` response (fallback to zeros while loading). Remove now-unused seedData exports. Commit.

### Task 9: Print CSS
- [ ] Add `@media print` rules: hide `aside`, `header` (topbar), buttons; expand report to full width; page-break-friendly tables. Commit.

## Phase 5 — Verification
### Task 10: Full-stack verify
- [ ] `manage.py test` all pass.
- [ ] Run stack: psychologist opens a child → progress report + trend + edit/finalize; admin + staff open Agency Summary → KPIs + CSV download; dashboard shows real counts. No console errors. Commit fixes; push.

---
## Self-Review
- Spec coverage: lock §6→T1–3; child report §4→T4,T6; summary §5→T5,T7; dashboard §7.2→T8; print §7.2→T9; edit policy §6→T2–3.
- Builds on foundation: report endpoints reuse psychologist scoping; per-psychologist attribution by author.
