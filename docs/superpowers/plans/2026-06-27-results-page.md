# Phase 3 #2 — Assessment Results Page (Real Data) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the demo data in the Assessment Results page with real saved assessments + their engine results, viewable by Psychologist (own), Admin + Staff (all, Staff read-only).

**Architecture:** Open the assessment list endpoint to Staff for reads via a permission split, scope the queryset by role, enrich `AssessmentListSerializer` with the nested engine result, and rewire `Report.jsx` to it. No schema change.

**Tech Stack:** Django + DRF (SQLite); React + Vite.

**Spec:** [2026-06-27-results-page-design.md](../specs/2026-06-27-results-page-design.md)

**Conventions:** Backend from `backend/` as `./venv/Scripts/python.exe manage.py <cmd>`. Commits omit any Claude co-author trailer. Commits deferred until the user asks (checkpoints below).

---

## File Structure

**Backend — modify:** `accounts/permissions.py` (`CanViewResults`), `assessments/views.py` (`get_permissions` + queryset), `assessments/serializers.py` (`AssessmentListSerializer` additions), `assessments/tests/test_api.py`.
**Frontend — modify:** `frontend/src/pages/Report.jsx`.

---

## Task 1: Backend — read access for Staff + result in the payload

**Files:** Modify `backend/accounts/permissions.py`, `backend/assessments/views.py`, `backend/assessments/serializers.py`; Test `backend/assessments/tests/test_api.py`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/assessments/tests/test_api.py` (inside `class AssessmentTakingTest`):
```python
    def test_staff_can_view_results_sees_all(self):
        Assessment.objects.create(child=self.child, psychologist=self.psy, questionnaire=self.qn, status="completed")
        self._auth("s@racco1.gov.ph")
        resp = self.client.get("/api/assessments/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)

    def test_result_included_in_list(self):
        self._auth("p@racco1.gov.ph")
        self.client.post("/api/assessments/", self._assessment_payload(), format="json")
        resp = self.client.get("/api/assessments/")
        self.assertIsNotNone(resp.data[0]["result"])
        self.assertIn("behavioral_score", resp.data[0]["result"])
        self.assertIn("notes", resp.data[0])
```

- [ ] **Step 2: Run to verify failure**

Run: `./venv/Scripts/python.exe manage.py test assessments.tests.test_api.AssessmentTakingTest.test_staff_can_view_results_sees_all assessments.tests.test_api.AssessmentTakingTest.test_result_included_in_list -v 2`
Expected: FAIL (Staff gets 403; `result`/`notes` not in payload).

- [ ] **Step 3: Add the view permission**

In `backend/accounts/permissions.py`, append:
```python
# Roles allowed to VIEW assessment results (read-only). Staff is included for
# case coordination; creating/running assessments stays ASSESSMENT_TAKER_ROLES.
RESULT_VIEWER_ROLES = (Role.ADMINISTRATOR, Role.PSYCHOLOGIST, Role.STAFF)


class CanViewResults(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated
                    and _role_name(request) in RESULT_VIEWER_ROLES)
```

- [ ] **Step 4: Split permissions + scope queryset in the viewset**

In `backend/assessments/views.py`, add `CanViewResults` to the permissions import:
```python
from accounts.permissions import CanManageInstruments, CanTakeAssessments, CanViewResults
```
Replace the `AssessmentViewSet` class attribute + `get_queryset` head:
```python
class AssessmentViewSet(viewsets.ModelViewSet):
    pagination_class = None

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [CanViewResults()]
        return [CanTakeAssessments()]

    def get_queryset(self):
        qs = (Assessment.objects
              .select_related("child", "questionnaire", "psychologist", "result")
              .prefetch_related("result__recommendations")
              .order_by("-assessment_date", "-id"))
        role = getattr(getattr(self.request.user, "role", None), "role_name", None)
        if role == Role.PSYCHOLOGIST:
            qs = qs.filter(psychologist=self.request.user)
        return qs
```
(Remove the old `permission_classes = [CanTakeAssessments]` line and the old `get_queryset` body.)

- [ ] **Step 5: Enrich the list serializer**

In `backend/assessments/serializers.py`, update `AssessmentListSerializer` (the `AssessmentResultSerializer` it references is defined later in the file, so use a method field to defer the reference):
```python
class AssessmentListSerializer(serializers.ModelSerializer):
    child_name = serializers.CharField(source="child.fullname", read_only=True)
    child_case_type = serializers.CharField(source="child.case_type", read_only=True, default="")
    questionnaire_title = serializers.CharField(source="questionnaire.title", read_only=True, default=None)
    psychologist_name = serializers.CharField(source="psychologist.fullname", read_only=True)
    result = serializers.SerializerMethodField()

    class Meta:
        model = Assessment
        fields = ["id", "child", "child_name", "child_case_type", "questionnaire", "questionnaire_title",
                  "psychologist_name", "assessment_type", "classification", "notes",
                  "status", "assessment_date", "result"]

    def get_result(self, obj):
        ar = getattr(obj, "result", None)
        return AssessmentResultSerializer(ar).data if ar else None
```

- [ ] **Step 6: Run the tests + full suite**

Run: `./venv/Scripts/python.exe manage.py test assessments -v 1`
Expected: OK.
Run: `./venv/Scripts/python.exe manage.py test`
Expected: all OK.

- [ ] **Step 7: Commit (deferred — checkpoint only)**

```bash
git add backend/accounts/permissions.py backend/assessments/views.py backend/assessments/serializers.py backend/assessments/tests/test_api.py
git commit -m "feat(assessments): results readable by staff + result included in list"
```

---

## Task 2: Frontend — rewire `Report.jsx` to real data

**Files:** Modify `frontend/src/pages/Report.jsx`.

- [ ] **Step 1: Replace the page with the real-data version**

Replace `frontend/src/pages/Report.jsx` with:
```jsx
import React, { useEffect, useMemo, useState } from 'react';
import api from '../api/client';
import { useAuth } from '../context/AuthContext';
import { Card, Badge, Alert, Input, SeverityBadge, EmptyState, Icon, iconBtn, PAGE } from '../ui';

function caseRef(id) { return `C-${String(id).padStart(4, '0')}`; }

const TRIAGE = {
  'Normal': { level: 'standard', tone: 'success' },
  'Needs Monitoring': { level: 'moderate', tone: 'warning' },
  'Needs Counseling Attention': { level: 'high', tone: 'danger' },
};

export default function Report() {
  const { user } = useAuth();
  const role = user?.role_name || 'Staff';
  const staff = role === 'Staff';
  const [items, setItems] = useState([]);
  const [q, setQ] = useState('');
  const [sel, setSel] = useState(null);

  useEffect(() => { api.get('/assessments/').then((r) => setItems(r.data)).catch(() => {}); }, []);

  const rows = useMemo(() => items.map((a) => ({
    id: a.id,
    name: a.child_name,
    ref: caseRef(a.child),
    caseType: a.child_case_type || '—',
    psychologist: a.psychologist_name || '—',
    date: a.assessment_date,
    cls: a.classification || '—',
    notes: a.notes || '',
    result: a.result,
  })), [items]);

  const visible = rows.filter((r) => (r.name || '').toLowerCase().includes(q.toLowerCase()) || r.ref.toLowerCase().includes(q.toLowerCase()));
  const td = { padding: '12px 16px', fontSize: 13, color: 'var(--text-body)', whiteSpace: 'nowrap' };

  return (
    <div style={{ ...PAGE, position: 'relative' }}>
      {staff ? (
        <Alert tone="info" icon={<Icon name="eye" size={18} />} style={{ marginBottom: 18 }} title="Read-only view">
          As Staff, you can view assessment outcomes for case coordination, but the assessment tools and raw questionnaire responses are restricted to psychologists.
        </Alert>
      ) : (
        <Alert tone="info" icon={<Icon name="users" size={18} />} style={{ marginBottom: 16 }} title="Saved results">
          Completed assessments and their automated analysis appear here. Run or update an assessment from <strong>Assessment Tools</strong>.
        </Alert>
      )}

      {!staff && (
        <div style={{ width: 340, maxWidth: '100%', marginBottom: 14 }}>
          <Input placeholder="Search results by child name or case ID…" value={q} onChange={(e) => setQ(e.target.value)} leading={<Icon name="search" size={16} />} />
        </div>
      )}

      <Card padding="0">
        {visible.length === 0 ? (
          <EmptyState icon={<Icon name="folder-search" size={24} />} title="No assessments yet" description="Completed assessments will appear here once they are signed." />
        ) : (
          <div className="racco-scroll" style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', minWidth: 760, borderCollapse: 'collapse', fontFamily: 'var(--font-sans)' }}>
              <thead>
                <tr style={{ background: 'var(--ink-50)', borderBottom: '1px solid var(--border)' }}>
                  {['Child', 'Case Type', 'Outcome', 'Score', 'Psychologist', 'Last Session', staff ? null : ''].filter((h) => h !== null).map((h, i) => (
                    <th key={i} scope="col" style={{ textAlign: 'left', padding: '12px 16px', fontSize: 11, fontWeight: 800, letterSpacing: '0.05em', textTransform: 'uppercase', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {visible.map((r) => {
                  const clickable = !staff;
                  const triage = r.result ? TRIAGE[r.result.classification] : null;
                  return (
                    <tr key={r.id} tabIndex={clickable ? 0 : undefined} role={clickable ? 'button' : undefined} aria-label={clickable ? `View ${r.name}'s assessment result` : undefined}
                      onClick={clickable ? () => setSel(r) : undefined}
                      onKeyDown={clickable ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setSel(r); } } : undefined}
                      style={{ borderBottom: '1px solid var(--ink-100)', cursor: clickable ? 'pointer' : 'default', transition: 'background var(--dur-fast) var(--ease-out)' }}
                      onMouseEnter={clickable ? (e) => (e.currentTarget.style.background = 'var(--blue-50)') : undefined}
                      onMouseLeave={clickable ? (e) => (e.currentTarget.style.background = 'transparent') : undefined}>
                      <td style={{ padding: '12px 16px' }}>
                        <div style={{ fontWeight: 700, fontSize: 13.5, color: staff ? 'var(--text-strong)' : 'var(--blue-700)', whiteSpace: 'nowrap' }}>{r.name}</div>
                        <div className="racco-mono" style={{ fontSize: 11, color: 'var(--text-muted)' }}>{r.ref}</div>
                      </td>
                      <td style={td}>{r.caseType}</td>
                      <td style={{ padding: '12px 16px' }}>{triage ? <SeverityBadge level={triage.level} size="sm" /> : <span style={{ color: 'var(--text-faint)' }}>—</span>}</td>
                      <td style={{ padding: '12px 16px' }}><span className="racco-mono" style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-strong)' }}>{r.result && r.result.behavioral_score != null ? `${r.result.behavioral_score}` : '—'}</span></td>
                      <td style={td}>{r.psychologist}</td>
                      <td style={{ padding: '12px 16px', fontSize: 13, color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>{r.date}</td>
                      {!staff && <td style={{ padding: '12px 16px', textAlign: 'right' }}><Icon name="chevron-right" size={16} style={{ color: 'var(--text-faint)' }} /></td>}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {sel && <ResultDrawer row={sel} onClose={() => setSel(null)} />}
    </div>
  );
}

function ResultDrawer({ row, onClose }) {
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);
  const res = row.result;
  const triage = res ? TRIAGE[res.classification] : null;
  const soft = triage?.tone === 'danger' ? 'var(--red-50)' : triage?.tone === 'warning' ? 'var(--warning-50)' : 'var(--success-50)';
  const line = triage?.tone === 'danger' ? 'var(--red-100)' : triage?.tone === 'warning' ? 'var(--warning-100)' : 'var(--success-100)';
  return (
    <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(14,19,29,0.32)', display: 'flex', justifyContent: 'flex-end', zIndex: 60, animation: 'racco-fade-in var(--dur-base) var(--ease-out)' }}>
      <div role="dialog" aria-modal="true" aria-label={`Assessment result for ${row.name}`} onClick={(e) => e.stopPropagation()} style={{ width: 440, maxWidth: '92%', height: '100%', background: 'var(--surface)', boxShadow: 'var(--shadow-xl)', display: 'flex', flexDirection: 'column', animation: 'racco-slide-left var(--dur-slow) var(--ease-out)' }}>
        <div style={{ padding: '18px 20px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: 'var(--ink-50)' }}>
          <div>
            <div style={{ fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 17, color: 'var(--text-strong)' }}>{row.name}</div>
            <div className="racco-mono" style={{ fontSize: 12, color: 'var(--text-muted)' }}>{row.ref} · {row.caseType}</div>
          </div>
          <button onClick={onClose} aria-label="Close panel" title="Close" style={iconBtn('var(--text-muted)', 32)}><Icon name="x" size={17} /></button>
        </div>

        <div className="racco-scroll" style={{ flex: 1, overflowY: 'auto', padding: 20, display: 'flex', flexDirection: 'column', gap: 18 }}>
          <div>
            <div className="racco-eyebrow" style={{ fontSize: 10, marginBottom: 8 }}>Automated analysis</div>
            {res ? (
              <div style={{ background: soft, border: `1px solid ${line}`, borderRadius: 'var(--radius-lg)', padding: 18 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 12 }}>
                  <SeverityBadge level={triage.level}>{res.classification}</SeverityBadge>
                  {res.behavioral_score != null && <Badge tone="brand" solid>Score {res.behavioral_score} / 100</Badge>}
                </div>
                <p style={{ fontSize: 13.5, color: 'var(--text-body)', lineHeight: 1.6, margin: '0 0 8px' }}>{res.recommendation_text}</p>
                {res.priority_level && <span style={{ fontSize: 11, fontWeight: 800, letterSpacing: '0.05em', textTransform: 'uppercase', color: 'var(--text-muted)' }}>Priority: {res.priority_level}</span>}
              </div>
            ) : (
              <div style={{ background: 'var(--ink-50)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: 16, fontSize: 13, color: 'var(--text-muted)' }}>No automated analysis for this assessment.</div>
            )}
          </div>

          <div>
            <div className="racco-eyebrow" style={{ fontSize: 10, marginBottom: 8 }}>Psychologist's clinical notes</div>
            <div style={{ background: 'var(--ink-50)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: 16 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, paddingBottom: 12, marginBottom: 12, borderBottom: '1px solid var(--border)' }}>
                <div><div style={{ fontSize: 11, color: 'var(--text-faint)' }}>Final classification</div><div style={{ fontWeight: 700, fontSize: 13.5, color: 'var(--text-strong)' }}>{row.cls}</div></div>
                <div style={{ textAlign: 'right' }}><div style={{ fontSize: 11, color: 'var(--text-faint)' }}>Signed by</div><div style={{ fontWeight: 700, fontSize: 13.5, color: 'var(--text-strong)' }}>{row.psychologist}</div></div>
              </div>
              <p style={{ fontSize: 13.5, color: 'var(--text-body)', lineHeight: 1.6, margin: 0 }}>{row.notes || '—'}</p>
            </div>
          </div>

          <Alert disclaimer title="Read-only record:">This is the signed assessment on file with NACC. To revise it, run a new session from Assessment Tools.</Alert>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'var(--text-faint)' }}>
            <Icon name="calendar" size={14} /> Last session {row.date}
          </div>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify build**

Run (from `frontend/`): `npm run build`
Expected: built, no errors (no remaining `seedData`/`statusToResult` imports on this page).

- [ ] **Step 3: Commit (deferred — checkpoint only)**

```bash
git add frontend/src/pages/Report.jsx
git commit -m "feat(report): wire Assessment Results to real saved assessments + analysis"
```

---

## Task 3: End-to-end verification

- [ ] **Step 1: Full backend suite**

Run (from `backend/`): `./venv/Scripts/python.exe manage.py test`
Expected: all OK.

- [ ] **Step 2: Frontend build**

Run (from `frontend/`): `npm run build`
Expected: built, no errors.

- [ ] **Step 3: Browser smoke test**

Backend `runserver` + preview. As a **Psychologist**, run + sign an assessment (with an active questionnaire), then open **Assessment Results**: confirm the row shows the real **Outcome** badge + **Score**, and the drawer shows the **Automated analysis** (classification + score + recommendation + priority) alongside the **practitioner notes**. Log in as **Staff** and confirm the page loads (read-only, no drawer) and lists assessments.
