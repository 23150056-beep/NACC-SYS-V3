# Progress Monitoring — Dedicated Role-Scoped View — Design

- **Date:** 2026-06-30
- **Status:** Approved (design)
- **Phase:** Phase 4 follow-on (Monitoring & Reporting).
- **Related:** [Confidence Threshold](2026-06-29-confidence-threshold-design.md)

---

## 1. Problem & Goal

The system already computes per-child progress — a trajectory chart + assessment timeline live in `ChildProgressReport.jsx` (`/report/child/:id`), and `assessments/reports.py::trajectory()` classifies a child's trend. But progress is **buried one click deep** inside **Assessment Results**; there is no single place to monitor every child's progress at a glance.

The backend **already scopes data by role** (`ChildReportView`, `AssessmentViewSet`, `ChildViewSet`, `DashboardView` all restrict a Psychologist to `assigned_psychologist=self`; Administrator/Staff see all). So role restriction is largely solved at the data layer — what's missing is a dedicated surface.

**Goal:** add a dedicated **Progress Monitoring** page that lists children with their progress at a glance, role-scoped — Administrator/Staff see the complete picture (all children), a Psychologist sees only the children they are assigned. Later, enrich each child's record with a progress log, treatment goals, and real next-session dates.

## 2. Scope

Build is **phased** (Approach A).

**Phase 1 — In (build now):**
- A new sidebar item **"Progress Monitoring"** and route `/monitoring` → `Monitoring.jsx`.
- A role-scoped, per-child overview table reusing **existing** assessment data (no migrations).
- A new read-only backend endpoint `GET /api/reports/monitoring/` returning the per-child progress summary, role-scoped, reusing `reports.trajectory()`.
- Rows link to the existing per-child detail report (`/report/child/:id`).
- Tests for role scoping + trajectory.

**Phase 2 — Out (documented here, built next):**
- `ProgressNote` (dated session log) and `Goal` (treatment goals with status) models; a real next-session date.
- Write access = **assigned Psychologist or Administrator**; **Staff read-only**.
- New sections in the per-child report + a "Next session" column on the overview.

**Out (both phases):** changing the existing scoring/trajectory logic; touching Assessment Results (`Report.jsx`) beyond leaving it as-is.

## 3. Phase 1 — Backend endpoint

New read-only view `MonitoringListView` in `assessments/views.py`, mounted at `path("reports/monitoring/", ...)` in `assessments/urls.py`.

- **Permission:** `CanViewResults` (any authenticated assessor; same as `ChildReportView`).
- **Role scoping** (single place, mirrors `DashboardView`):
  - Administrator / Staff → all children excluding `Child.ARCHIVED`.
  - Psychologist → those children filtered by `assigned_psychologist=request.user`.
- **Per child**, gather that child's assessments in chronological order (`assessment_date, id`), with `select_related("result")`, and compute:

  | Field | Source |
  |---|---|
  | `child_id`, `child_name`, `case_ref` | `Child` |
  | `case_type` | `Child.case_type` |
  | `psychologist_name` | `Child.assigned_psychologist` (fullname/username, `—` if none) |
  | `latest_classification` | latest assessment's `result.classification` (`None` if unassessed) |
  | `latest_score` | latest `result.behavioral_score` (`None` if unassessed) |
  | `trajectory` | `reports.trajectory([scores in order])` → improving / worsening / stable / baseline |
  | `last_assessment_date` | latest `assessment_date` (`None` if unassessed) |
  | `assessment_count` | count of that child's assessments |

- Returns a **flat list** (one object per child), ordered by `child_name`. Children with **zero** assessments are included with `trajectory: "baseline"`, null score/classification, `assessment_count: 0` (so unassessed children are visible, not hidden).
- Implementation note: fetch the scoped children, then the relevant assessments in one query and group by `child_id` in Python (avoids N+1), the way `summary()`/`DashboardView` already aggregate from a list.

## 4. Phase 1 — Frontend

### Navigation & route
- `Sidebar.jsx` `NAV`: add `{ to: '/monitoring', label: 'Progress Monitoring', icon: 'activity', roles: ['Administrator', 'Psychologist', 'Staff'] }` in the **Clinical** section, placed **after** Assessment and **before** Assessment Results.
- `App.jsx`: add `<Route path="/monitoring" element={<ProtectedRoute><Shell><Monitoring /></Shell></ProtectedRoute>} />` (roles enforced for all three; data scoping is done server-side).

### `Monitoring.jsx`
- On mount, `GET /reports/monitoring/`; the response is already role-scoped, so the page renders whatever it receives.
- **Search** by child name or case ref (same control/style as Records & Results).
- **Trajectory filter chips** (All / Improving / Worsening / Stable), styled like the Records page status chips, each with a live count.
- **Table**, alphabetical by child name, one row per child:
  - Child (name + case ref) · Case Type · Assigned Psychologist · Trajectory badge · Latest classification (`SeverityBadge` via the existing `TRIAGE` mapping) · Latest score · Last assessment date · # assessments.
  - Trajectory badge styling reuses the `TRAJ` map already defined in `ChildProgressReport.jsx` (improving = down/green, worsening = up/red, stable = blue, baseline = neutral) — extract it to a shared spot or duplicate the small constant.
- Row click → `navigate('/report/child/:childId')` (existing detail report; already role-guarded by `ChildReportView`).
- **No "Next session" column in Phase 1** — the current next-session value is a placeholder (date + 14 days); showing invented dates is misleading. It returns in Phase 2 as a real field.
- **Empty state:** `EmptyState` when no children match the filter/search; unassessed children still appear (with a "Baseline" trajectory and `—` score).

## 5. Phase 2 — Outline (built later)

- **Models** (in `children` or a new `progress` app, one migration):
  - `ProgressNote`: `child` (FK), `author` (FK user), `date`, `text`.
  - `Goal`: `child` (FK), `text`, `status` (`ongoing` / `met`), optional `target_date`.
  - Next session: add a real `next_session` date (on `Assessment`, or a small `Session` model) to replace the `Report.jsx` placeholder.
- **Permissions:** write = the child's `assigned_psychologist` **or** an `Administrator`; **Staff read-only** — enforced in the serializer/permission layer like the existing `AssessmentViewSet.partial_update` rule ("you can only edit your own…").
- **UI:** progress-log timeline + goals checklist + next-session control added to `ChildProgressReport.jsx`; a "Next session" column added back to `Monitoring.jsx`.

## 6. Testing

**Backend (`assessments/tests`):**
- Psychologist `GET /reports/monitoring/` returns **only** their assigned children; Administrator and Staff get **all** active children; archived children excluded.
- Trajectory correctness: falling score ⇒ `improving`, rising ⇒ `worsening`, <2 scored ⇒ `baseline` (delegates to `reports.trajectory`, already unit-covered).
- Unassessed assigned child appears with `assessment_count: 0`, `trajectory: "baseline"`.

**Frontend:** page renders the scoped rows; trajectory filter narrows the list; row click navigates to `/report/child/:id`.

## 7. Risks / notes

- **No migrations in Phase 1** — it is purely a read endpoint + a new page, so it is low-risk and quickly demoable.
- **Single source of scoping** — the endpoint reuses the same `assigned_psychologist` rule as the rest of the system, so Progress Monitoring cannot leak a child outside a psychologist's caseload even via a direct API call.
- **Trajectory semantics** are intentionally unchanged (higher score = more concern, so a falling score = improving), keeping the new page consistent with the existing detail report.
- **`TRAJ` constant duplication** — extracting it to a shared module is cleaner than copying; either is acceptable, decided at implementation time.
