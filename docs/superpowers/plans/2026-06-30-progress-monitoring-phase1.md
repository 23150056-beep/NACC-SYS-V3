# Progress Monitoring (Phase 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a dedicated, role-scoped "Progress Monitoring" page that lists every child with their progress at a glance (trajectory, latest score/classification, last assessment, assessment count), reusing existing assessment data with no migrations.

**Architecture:** One new read-only DRF endpoint (`GET /api/reports/monitoring/`) aggregates a per-child progress summary, role-scoped in one place (admin/staff → all active children; psychologist → assigned children) and reusing `assessments.reports.trajectory()`. One new React page (`Monitoring.jsx`) renders the list with search + trajectory filters; rows link to the existing per-child detail report.

**Tech Stack:** Django REST Framework (backend), React + react-router + Vite (frontend), Recharts already present (not needed here). No new dependencies. Backend tests via Django `APITestCase`; frontend verified via ESLint + the preview dev server (the repo has no JS test runner).

---

## Spec reference

[2026-06-30-progress-monitoring-design.md](../specs/2026-06-30-progress-monitoring-design.md) — Phase 1 only. Phase 2 (progress log, goals, scheduling) is **out of scope** for this plan.

---

## File Structure

- **Create** `backend/assessments/tests/test_reports.py` → add `MonitoringApiTest` class (append to existing file).
- **Modify** `backend/assessments/views.py` → add `MonitoringListView`.
- **Modify** `backend/assessments/urls.py` → add `reports/monitoring/` route + import.
- **Create** `frontend/src/pages/Monitoring.jsx` → the overview page.
- **Modify** `frontend/src/App.jsx` → import + `/monitoring` route.
- **Modify** `frontend/src/components/Sidebar.jsx` → nav item under "Clinical".

---

## Task 1: Backend — `/api/reports/monitoring/` endpoint (TDD)

**Files:**
- Test: `backend/assessments/tests/test_reports.py` (append `MonitoringApiTest`)
- Modify: `backend/assessments/views.py`
- Modify: `backend/assessments/urls.py`

> All backend commands run from the `backend/` directory. On Windows the venv Python is `venv/Scripts/python.exe`.

- [ ] **Step 1: Write the failing test**

Append to the end of `backend/assessments/tests/test_reports.py` (the file already defines `User`, `Role`, `Child`, `Assessment`, and the `_result(a, score, cls, priority, conf)` helper at module level):

```python
class MonitoringApiTest(APITestCase):
    def setUp(self):
        self.admin_role = Role.objects.create(role_name=Role.ADMINISTRATOR)
        self.psy_role = Role.objects.create(role_name=Role.PSYCHOLOGIST)
        self.staff_role = Role.objects.create(role_name=Role.STAFF)
        self.admin = User.objects.create_user(
            email="a@racco1.gov.ph", username="a", password="pass1234", role=self.admin_role)
        self.psy = User.objects.create_user(
            email="p@racco1.gov.ph", username="p", password="pass1234", role=self.psy_role)
        self.other = User.objects.create_user(
            email="o@racco1.gov.ph", username="o", password="pass1234", role=self.psy_role)
        self.staff = User.objects.create_user(
            email="s@racco1.gov.ph", username="s", password="pass1234", role=self.staff_role)
        # Assigned to psy, two assessments 60 -> 50 (improving).
        self.mine = Child.objects.create(
            fullname="Ana", case_type="Foster Care", assigned_psychologist=self.psy)
        a1 = Assessment.objects.create(child=self.mine, psychologist=self.psy, status="completed")
        _result(a1, 60, "Needs Counseling Attention", "High")
        a2 = Assessment.objects.create(child=self.mine, psychologist=self.psy, status="completed")
        _result(a2, 50, "Needs Monitoring", "Medium")
        # Assigned to a different psychologist.
        self.theirs = Child.objects.create(fullname="Ben", assigned_psychologist=self.other)
        a3 = Assessment.objects.create(child=self.theirs, psychologist=self.other, status="completed")
        _result(a3, 40, "Normal", "Low")
        # Assigned to psy but never assessed.
        self.fresh = Child.objects.create(fullname="Cara", assigned_psychologist=self.psy)
        # Archived — must never appear.
        self.gone = Child.objects.create(
            fullname="Zed", assigned_psychologist=self.psy, status=Child.ARCHIVED)

    def _auth(self, email):
        token = self.client.post("/api/auth/login/", {
            "email": email, "password": "pass1234"}).data["access"]
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + token)

    def test_admin_sees_all_active_children_sorted(self):
        self._auth("a@racco1.gov.ph")
        resp = self.client.get("/api/reports/monitoring/")
        self.assertEqual(resp.status_code, 200)
        names = [r["child_name"] for r in resp.data]
        self.assertEqual(names, ["Ana", "Ben", "Cara"])  # sorted, Zed excluded

    def test_staff_sees_all_active_children(self):
        self._auth("s@racco1.gov.ph")
        resp = self.client.get("/api/reports/monitoring/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 3)

    def test_psychologist_sees_only_assigned(self):
        self._auth("p@racco1.gov.ph")
        resp = self.client.get("/api/reports/monitoring/")
        self.assertEqual(resp.status_code, 200)
        names = [r["child_name"] for r in resp.data]
        self.assertEqual(names, ["Ana", "Cara"])  # Ben (other psy) and Zed (archived) excluded

    def test_assessed_row_has_trajectory_and_latest(self):
        self._auth("a@racco1.gov.ph")
        resp = self.client.get("/api/reports/monitoring/")
        ana = next(r for r in resp.data if r["child_name"] == "Ana")
        self.assertEqual(ana["trajectory"], "improving")        # 60 -> 50
        self.assertEqual(ana["latest_score"], 50.0)
        self.assertEqual(ana["latest_classification"], "Needs Monitoring")
        self.assertEqual(ana["assessment_count"], 2)
        self.assertEqual(ana["case_ref"], f"C-{self.mine.id:04d}")
        self.assertIsNotNone(ana["last_assessment_date"])

    def test_unassessed_child_is_baseline(self):
        self._auth("p@racco1.gov.ph")
        resp = self.client.get("/api/reports/monitoring/")
        cara = next(r for r in resp.data if r["child_name"] == "Cara")
        self.assertEqual(cara["trajectory"], "baseline")
        self.assertIsNone(cara["latest_score"])
        self.assertIsNone(cara["latest_classification"])
        self.assertEqual(cara["assessment_count"], 0)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `venv/Scripts/python manage.py test assessments.tests.test_reports.MonitoringApiTest -v 2`
Expected: FAIL — `404` responses (the `/api/reports/monitoring/` route does not exist yet).

- [ ] **Step 3: Add the view**

In `backend/assessments/views.py`, add the following class. Place it immediately **after** `ChildReportView` (it shares the same imports — `Child`, `Assessment`, `Role`, `CanViewResults`, `reports` — which are already imported at the top of the file):

```python
class MonitoringListView(generics.GenericAPIView):
    """Per-child progress overview for the Progress Monitoring page, role-scoped:
    admin/staff -> all active children; psychologist -> their assigned children.
    Read-only; reuses reports.trajectory(). No new model."""
    permission_classes = [CanViewResults]

    def get(self, request):
        role = getattr(getattr(request.user, "role", None), "role_name", None)
        children = (Child.objects.exclude(status=Child.ARCHIVED)
                    .select_related("assigned_psychologist"))
        if role == Role.PSYCHOLOGIST:
            children = children.filter(assigned_psychologist=request.user)
        children = list(children)

        child_ids = [c.id for c in children]
        assessments = (Assessment.objects.filter(child_id__in=child_ids)
                       .select_related("result")
                       .order_by("assessment_date", "id"))
        by_child = {}
        for a in assessments:
            by_child.setdefault(a.child_id, []).append(a)

        rows = []
        for c in children:
            items = by_child.get(c.id, [])
            scores = [getattr(a, "result", None).behavioral_score
                      if getattr(a, "result", None) else None for a in items]
            latest = items[-1] if items else None
            latest_result = getattr(latest, "result", None) if latest else None
            if c.assigned_psychologist_id:
                psy = c.assigned_psychologist
                psy_name = (getattr(psy, "fullname", "") or getattr(psy, "username", "")) or None
            else:
                psy_name = None
            score = (float(latest_result.behavioral_score)
                     if latest_result and latest_result.behavioral_score is not None else None)
            rows.append({
                "child_id": c.id,
                "child_name": c.fullname,
                "case_ref": f"C-{c.id:04d}",
                "case_type": c.case_type or None,
                "psychologist_name": psy_name,
                "latest_classification": latest_result.classification if latest_result else None,
                "latest_score": score,
                "trajectory": reports.trajectory(scores),
                "last_assessment_date": latest.assessment_date if latest else None,
                "assessment_count": len(items),
            })
        rows.sort(key=lambda r: (r["child_name"] or "").lower())
        return Response(rows)
```

- [ ] **Step 4: Wire the URL**

In `backend/assessments/urls.py`, add `MonitoringListView` to the import from `assessments.views`:

```python
from assessments.views import (
    QuestionnaireViewSet, AssessmentViewSet, ActiveQuestionnaireListView, AnalysisSettingView,
    ChildReportView, SummaryReportView, DashboardView, MonitoringListView,
)
```

Then add this line to `urlpatterns` (after the `reports/dashboard/` path):

```python
    path("reports/monitoring/", MonitoringListView.as_view(), name="report-monitoring"),
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `venv/Scripts/python manage.py test assessments.tests.test_reports.MonitoringApiTest -v 2`
Expected: PASS (5 tests OK).

- [ ] **Step 6: Run the full assessments suite (no regressions)**

Run: `venv/Scripts/python manage.py test assessments -v 1`
Expected: PASS (all existing tests still green).

- [ ] **Step 7: Commit**

```bash
git add backend/assessments/views.py backend/assessments/urls.py backend/assessments/tests/test_reports.py
git commit -m "feat(monitoring): role-scoped per-child progress endpoint"
git push origin main
```

---

## Task 2: Frontend — Progress Monitoring page (`Monitoring.jsx`)

**Files:**
- Create: `frontend/src/pages/Monitoring.jsx`
- (route + nav wired in Task 3)

- [ ] **Step 1: Create the page**

Create `frontend/src/pages/Monitoring.jsx` with this exact content:

```jsx
import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/client';
import { Card, Input, SeverityBadge, EmptyState, Icon, hoverLift, PAGE } from '../ui';

// Trajectory presentation (mirrors the TRAJ map in ChildProgressReport.jsx).
const TRAJ = {
  improving: { label: 'Improving', icon: 'trending-down', color: 'var(--success-600)', bg: 'var(--success-50)' },
  worsening: { label: 'Worsening', icon: 'trending-up', color: 'var(--red-600)', bg: 'var(--red-50)' },
  stable: { label: 'Stable', icon: 'minus', color: 'var(--blue-600)', bg: 'var(--blue-50)' },
  baseline: { label: 'Baseline', icon: 'flag', color: 'var(--text-muted)', bg: 'var(--ink-50)' },
};
// Classification -> severity badge level (mirrors the TRIAGE map in Report.jsx).
const TRIAGE = {
  'Normal': 'standard',
  'Needs Monitoring': 'moderate',
  'Needs Counseling Attention': 'high',
};
const FILTERS = [
  { key: 'all', label: 'All' },
  { key: 'improving', label: 'Improving' },
  { key: 'worsening', label: 'Worsening' },
  { key: 'stable', label: 'Stable' },
];

export default function Monitoring() {
  const navigate = useNavigate();
  const [rows, setRows] = useState([]);
  const [q, setQ] = useState('');
  const [traj, setTraj] = useState('all');

  useEffect(() => {
    api.get('/reports/monitoring/').then((r) => setRows(r.data)).catch(() => {});
  }, []);

  const counts = useMemo(() => {
    const c = { all: rows.length, improving: 0, worsening: 0, stable: 0 };
    rows.forEach((r) => { if (c[r.trajectory] != null) c[r.trajectory] += 1; });
    return c;
  }, [rows]);

  const visible = useMemo(() => rows
    .filter((r) => (r.child_name || '').toLowerCase().includes(q.toLowerCase())
      || (r.case_ref || '').toLowerCase().includes(q.toLowerCase()))
    .filter((r) => traj === 'all' || r.trajectory === traj)
    .sort((a, b) => (a.child_name || '').localeCompare(b.child_name || '', undefined, { sensitivity: 'base' })),
    [rows, q, traj]);

  const td = { padding: '11px 16px', fontSize: 13, color: 'var(--text-body)', whiteSpace: 'nowrap' };

  const TrajPill = ({ value }) => {
    const t = TRAJ[value] || TRAJ.baseline;
    return (
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '3px 10px', borderRadius: 'var(--radius-pill)', background: t.bg, color: t.color, fontWeight: 800, fontSize: 12 }}>
        <Icon name={t.icon} size={14} /> {t.label}
      </span>
    );
  };

  return (
    <div style={{ ...PAGE, position: 'relative' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16, marginBottom: 14, flexWrap: 'wrap' }}>
        <div style={{ width: 340, maxWidth: '100%' }}>
          <Input placeholder="Search by child name or case ID…" value={q} onChange={(e) => setQ(e.target.value)} leading={<Icon name="search" size={16} />} />
        </div>
        <div style={{ fontSize: 12.5, color: 'var(--text-muted)' }}>
          Showing <strong style={{ color: 'var(--text-strong)' }}>{visible.length}</strong> of {rows.length} children
        </div>
      </div>

      <div role="tablist" aria-label="Filter by trajectory" style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 14 }}>
        {FILTERS.map((f) => {
          const on = traj === f.key;
          return (
            <button key={f.key} role="tab" aria-selected={on} onClick={() => setTraj(f.key)} {...hoverLift({ lift: -1, shadow: 'var(--shadow-md)' })}
              style={{ display: 'inline-flex', alignItems: 'center', gap: 7, padding: '7px 13px', cursor: 'pointer', borderRadius: 'var(--radius-pill)', fontFamily: 'var(--font-sans)', fontWeight: 700, fontSize: 12.5, border: `1px solid ${on ? 'var(--blue-500)' : 'var(--border)'}`, background: on ? 'var(--blue-50)' : 'var(--surface)', color: on ? 'var(--blue-700)' : 'var(--text-body)', transition: 'var(--transition-base)' }}>
              {f.label}
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 600, color: on ? 'var(--blue-600)' : 'var(--text-faint)' }}>{counts[f.key] || 0}</span>
            </button>
          );
        })}
      </div>

      <Card padding="0">
        {visible.length === 0 ? (
          <EmptyState icon={<Icon name="folder-search" size={24} />} title="No children to monitor" description="Try a different name, case ID, or trajectory filter." />
        ) : (
          <div className="racco-scroll" style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', minWidth: 820, borderCollapse: 'collapse', fontFamily: 'var(--font-sans)' }}>
              <thead>
                <tr style={{ background: 'var(--ink-50)', borderBottom: '1px solid var(--border)' }}>
                  {['Child', 'Case Type', 'Psychologist', 'Trajectory', 'Latest', 'Score', 'Last Assessment', 'Assessments'].map((h) => (
                    <th key={h} scope="col" style={{ textAlign: 'left', padding: '11px 16px', fontSize: 11, fontWeight: 800, letterSpacing: '0.05em', textTransform: 'uppercase', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {visible.map((r) => {
                  const level = TRIAGE[r.latest_classification];
                  const open = () => navigate(`/report/child/${r.child_id}`);
                  return (
                    <tr key={r.child_id} tabIndex={0} role="button" aria-label={`Open ${r.child_name}'s progress report`}
                      onClick={open}
                      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(); } }}
                      style={{ borderBottom: '1px solid var(--ink-100)', cursor: 'pointer', transition: 'background var(--dur-fast) var(--ease-out)' }}
                      onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--blue-50)')}
                      onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}>
                      <td style={{ padding: '11px 16px' }}>
                        <div style={{ fontWeight: 700, fontSize: 13.5, color: 'var(--blue-700)', whiteSpace: 'nowrap' }}>{r.child_name}</div>
                        <div className="racco-mono" style={{ fontSize: 11, color: 'var(--text-muted)' }}>{r.case_ref}</div>
                      </td>
                      <td style={td}>{r.case_type || '—'}</td>
                      <td style={td}>{r.psychologist_name || '—'}</td>
                      <td style={{ padding: '11px 16px' }}><TrajPill value={r.trajectory} /></td>
                      <td style={{ padding: '11px 16px' }}>{level ? <SeverityBadge level={level} size="sm" /> : <span style={{ color: 'var(--text-faint)' }}>—</span>}</td>
                      <td style={td}>{r.latest_score != null ? r.latest_score : '—'}</td>
                      <td style={td}>{r.last_assessment_date || '—'}</td>
                      <td style={td}>{r.assessment_count}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
```

- [ ] **Step 2: Lint the new file**

Run (from `frontend/`): `npm run lint`
Expected: PASS with no new errors for `src/pages/Monitoring.jsx`.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/Monitoring.jsx
git commit -m "feat(monitoring): Progress Monitoring overview page"
git push origin main
```

---

## Task 3: Frontend — route + sidebar nav

**Files:**
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/components/Sidebar.jsx`

- [ ] **Step 1: Add the import + route in `App.jsx`**

Add the import alongside the other page imports (after the `ChildProgressReport` import line):

```jsx
import Monitoring from './pages/Monitoring';
```

Add this route inside `<Routes>`, immediately **after** the `/report/child/:id` route:

```jsx
          <Route path="/monitoring" element={<ProtectedRoute roles={['Administrator', 'Staff', 'Psychologist']}><Shell><Monitoring /></Shell></ProtectedRoute>} />
```

- [ ] **Step 2: Add the sidebar nav item in `Sidebar.jsx`**

In the `NAV` array, in the **Clinical** section, insert this item **between** the `/assessment` line and the `/report` line:

```jsx
  { to: '/monitoring', label: 'Progress Monitoring', icon: 'activity', roles: ['Administrator', 'Psychologist', 'Staff'] },
```

The Clinical block should then read:

```jsx
  { section: 'Clinical' },
  { to: '/assessment', label: 'Assessment', icon: 'clipboard-list', roles: ['Psychologist'] },
  { to: '/monitoring', label: 'Progress Monitoring', icon: 'activity', roles: ['Administrator', 'Psychologist', 'Staff'] },
  { to: '/report', label: 'Assessment Results', icon: 'clipboard-check', roles: ['Administrator', 'Psychologist', 'Staff'] },
```

- [ ] **Step 3: Lint**

Run (from `frontend/`): `npm run lint`
Expected: PASS, no new errors.

- [ ] **Step 4: Verify in the preview**

Start both servers (backend on 8000, frontend on 5173) and confirm:
1. The sidebar shows **Progress Monitoring** under Clinical.
2. Navigating to `/monitoring` renders the table without console errors.
3. The trajectory filter chips narrow the list; clicking a row navigates to `/report/child/:id`.

If cross-role checking is possible with seeded users: log in as a Psychologist and confirm only their assigned children appear; log in as Administrator/Staff and confirm all active children appear. (The role scoping itself is covered by the Task 1 backend tests, so this is a confidence check, not the primary gate.)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.jsx frontend/src/components/Sidebar.jsx
git commit -m "feat(monitoring): add Progress Monitoring route and sidebar nav"
git push origin main
```

---

## Self-Review (completed during planning)

- **Spec coverage:** dedicated page (Task 2) ✓; sidebar item + route under Clinical (Task 3) ✓; role-scoped read endpoint reusing `trajectory()` (Task 1) ✓; rows link to existing detail report (Task 2 row `onClick`) ✓; unassessed children shown as Baseline (Task 1 view + test) ✓; no "Next session" column (omitted by design) ✓; no migrations ✓; tests for role scoping + trajectory + baseline (Task 1) ✓.
- **Placeholder scan:** none — all steps contain concrete code/commands.
- **Type/name consistency:** endpoint JSON keys (`child_id`, `child_name`, `case_ref`, `case_type`, `psychologist_name`, `latest_classification`, `latest_score`, `trajectory`, `last_assessment_date`, `assessment_count`) are identical in the view (Task 1), the tests (Task 1), and the page consumer (Task 2). Route name `/api/reports/monitoring/` matches between `urls.py`, tests, and the `api.get('/reports/monitoring/')` call (the axios `baseURL` already includes `/api`).
