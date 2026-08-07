# Multidisciplinary UX Batch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn NACC-V2 into a true multidisciplinary-team workspace: staff + psychologist co-edit child records safely, the dashboard becomes a no-scroll bento with a mini calendar, results group per child, terminated cases are a reopenable admin archive, the instrument catalog moves into pre-assessment step 4 with the agency's real title lists, and the local-AI privacy guarantee is hardened.

**Architecture:** Django REST (backend/) + React/Vite (frontend/, RACCO design tokens, inline styles). Collaboration uses optimistic concurrency (409 on stale write) + cache-based presence polling — NO websockets (single local server, capstone scope). All AI stays on local Ollama.

**Tech Stack:** Django 5 / DRF, SQLite dev, React 18, react-router, recharts, react-big-calendar (full page only; mini widget is custom).

## Global Constraints

- Repo: `Desktop\NACC SYS\NACC-V2\` — its **own git repo**, remote `https://github.com/23150056-beep/NACC-SYS-V2`, branch `main`.
- Commits: **user is sole author — NEVER add a Claude co-author trailer.** Push to `origin main` after each completed task.
- Backend tests: from `backend/` run `./venv/Scripts/python.exe manage.py test` (218 green at plan time). Frontend has **no test harness** — verify with `npm run build` + browser (launch configs `v2-backend` / `v2-frontend` in v1's `.claude/launch.json`; backend runs `--noreload`, restart after backend edits; browser-pane screenshots time out on this machine — use `read_page`).
- **Copyright policy (V2 §2): instrument items, scales, scoring keys are NEVER stored — titles/metadata only.** The new seeded entries are titles only.
- Roles: Administrator, Psychologist, Staff (Staff = social worker).
- ⚠️ **Pre-flight:** `frontend/src/components/Sidebar.jsx`, `backend/clinical/reports_views.py`, `backend/clinical/tests/test_reports.py` have UNCOMMITTED changes from an in-flight "chart clinical interviews" session (plan `docs/superpowers/plans/2026-07-15-chart-clinical-interviews.md`). Finish/commit that work FIRST, or stash it — Task 8 and Task 10 also edit Sidebar.jsx.
- Dev seeds: `psy@racco1.gov.ph` / `psy12345` (Hannah) with child "Mika Santos" (id 2); admin `admin@racco1.gov.ph` / `admin1234`.

## Decisions locked for this plan (flag to user if they disagree at execution time)

1. **"Multimodal/Google-Docs collab" = optimistic concurrency + presence polling**, not live character-level sync. Rationale: single on-prem Django server, no Channels/Redis; a 409-guarded save with "who else is here" chip delivers the coordination value at capstone scope.
2. **"Recommendation" panel change** interpreted as: fields NOT asked in the RACCO I meeting (referral source/reason, education level, current placement, medical notes) move under a **"Recommendation"** section, plus a new free-text `recommendation` field. Backend field names unchanged (labels only + one new field).
3. **"Previous Custodian"** is a LABEL rename only — `surrendered_by` stays as the DB/API field name (avoids a risky rename migration; choices unchanged).
4. **Instrument catalog becomes shareable** (`owner=NULL` = agency-wide, mirroring AgencyFormTemplate) so the seeded official lists are visible to every psychologist. Admin creating without owner now means "shared" (previously a validation error).
5. **Sidebar**: "Pre-Assessment Instruments" page stays at `/instruments` but is relabelled — Admin sees "Instruments & Agency Forms" (both tabs); Psychologist entry becomes "Agency Form Templates" (forms tab only — catalog management now lives inside wizard step 4).
6. **Calendar**: `/schedule` route and page are kept as the "full screen" view; only the sidebar entry is removed. The dashboard mini calendar navigates there on click.
7. **Reopen case** is Admin-only (`POST /children/<id>/reopen/`); termination history is preserved forever and displayed in full.
8. **Name split (adviser #1)**: `Child.fullname` column is KEPT and auto-composed from new `first_name` / `middle_initial` / `last_name` fields on save — every existing `fullname`/`child_name` consumer keeps working; forms input the three parts. Existing rows are split best-effort (last token → last name).
9. **Age constraint (adviser #2)** = 5–17 inclusive, validated from `birth_date` server-side; `birth_date`, name parts, gender, and case type become required on CREATE (edits stay partial-friendly).
10. **Label renames (adviser #3)**: "Education Level" → **"Educational Placement"**, "Current Placement" → **"Place of Recovery"** — labels only, field names unchanged.
11. **LIFO (adviser #4)** = Records list defaults to newest-first, with an A–Z toggle kept (the earlier adviser round asked for alphabetical — both available, LIFO default).
12. **"Status has a function / add event" (adviser #13)**: appointment status actions (Completed / No-show / Cancel) ALREADY exist in the appointment detail modal — verified in code. The new part is calendar slot-click → prefilled booking form ("add event").
13. **Consent embedding (adviser #9)** already exists (template document text renders in the wizard); the rework keeps it and adds the missing pieces: single flow (no On-file/Record-new toggle), consents table at the bottom, scan upload + in-app preview (the `ConsentRecord.scan` FileField already exists in the model, unused by the UI).
14. **Records layout (follow-up request)**: the Records module's right-side drawers (detail + add/edit) become large CENTERED modals (~980px, two-column body) — only Records changes; other modules' drawers (Reports upload, Instruments, Schedule booking) stay as they are. Component names `ChildDrawer`/`ChildForm` are KEPT so every other task's instructions still apply — only their container and internal arrangement change.
15. **Reliability trio (user-approved)**: duplicate/returning-child detection warns from BOTH active and archived records as staff type the name (staff see "ask an administrator to reopen" for archived matches — reopen stays admin-only per decision #7); one-click first booking lives on the record's next-session chips, defaulting purpose to Pre-Assessment when the child hasn't answered one yet; intake draft autosave is localStorage on the local workstation only (on-prem machine), cleared on successful save, discard, and logout.

---

### Task 1: Backend — psychologist can edit assigned children

**Files:**
- Modify: `backend/accounts/permissions.py` (append after `RecordsAccess`, ~line 37)
- Modify: `backend/children/views.py` (ChildViewSet)
- Modify: `backend/children/serializers.py` (ChildSerializer)
- Test: `backend/children/tests/test_child_collab.py` (new)

**Interfaces:**
- Produces: permission class `ChildRecordAccess`; PATCH/PUT `/api/children/<id>/` now allowed for the child's assigned psychologist; serializer rejects psychologist self-reassignment and any post-create `fullname` change; `updated_at` exposed read-only (needed by Task 2/3).

- [ ] **Step 1: Write the failing tests**

```python
# backend/children/tests/test_child_collab.py
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from accounts.models import Role, User
from children.models import Child


def make_user(email, role_name, **kw):
    role, _ = Role.objects.get_or_create(role_name=role_name)
    return User.objects.create_user(email=email, password="pass12345", role=role, **kw)


class PsychologistEditTests(APITestCase):
    def setUp(self):
        self.admin = make_user("a@t.ph", Role.ADMINISTRATOR)
        self.staff = make_user("s@t.ph", Role.STAFF)
        self.psych = make_user("p@t.ph", Role.PSYCHOLOGIST)
        self.other_psych = make_user("p2@t.ph", Role.PSYCHOLOGIST)
        self.child = Child.objects.create(fullname="Mika Santos",
                                          assigned_psychologist=self.psych)

    def patch(self, user, child, data):
        self.client.force_authenticate(user)
        return self.client.patch(f"/api/children/{child.id}/", data, format="json")

    def test_assigned_psychologist_can_edit(self):
        r = self.patch(self.psych, self.child, {"education_level": "Grade 4"})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.child.refresh_from_db()
        self.assertEqual(self.child.education_level, "Grade 4")

    def test_unassigned_psychologist_cannot_edit(self):
        r = self.patch(self.other_psych, self.child, {"education_level": "x"})
        # queryset scoping means the record 404s for them
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_psychologist_cannot_reassign(self):
        r = self.patch(self.psych, self.child, {"psychologist": self.other_psych.id})
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_psychologist_cannot_create(self):
        self.client.force_authenticate(self.psych)
        r = self.client.post("/api/children/", {"fullname": "New Kid"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_fullname_locked_on_update_for_everyone(self):
        r = self.patch(self.staff, self.child, {"fullname": "Renamed"})
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
```

If `make_user`'s signature doesn't match `accounts.models` (check how existing tests in `backend/children/tests/` build users — e.g. `test_children.py`), copy their factory helper instead; the assertions stay the same.

- [ ] **Step 2: Run tests to verify they fail**

Run (from `backend/`): `./venv/Scripts/python.exe manage.py test children.tests.test_child_collab -v 2`
Expected: FAIL — psychologist PATCH returns 403 (write blocked by `RecordsAccess`), fullname test fails (no lock yet).

- [ ] **Step 3: Implement**

`backend/accounts/permissions.py` — append:

```python
class ChildRecordAccess(RecordsAccess):
    """RecordsAccess plus multidisciplinary collaboration: the child's
    assigned psychologist may edit (PUT/PATCH) the record. Create/archive
    stay Admin/Staff-only; queryset scoping already hides other children."""

    def has_permission(self, request, view):
        if super().has_permission(request, view):
            return True
        return bool(request.user and request.user.is_authenticated
                    and _role_name(request) == Role.PSYCHOLOGIST
                    and request.method in ("PUT", "PATCH"))

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        role = _role_name(request)
        if role in (Role.ADMINISTRATOR, Role.STAFF):
            return True
        return (role == Role.PSYCHOLOGIST
                and request.method in ("PUT", "PATCH")
                and obj.assigned_psychologist_id == request.user.id)
```

`backend/children/views.py` — import and use it on ChildViewSet only:

```python
from accounts.permissions import RecordsAccess, ChildRecordAccess
...
class ChildViewSet(_ArchivableViewSet):
    model = Child
    serializer_class = ChildSerializer
    permission_classes = [ChildRecordAccess]
```

(Note: `_ArchivableViewSet.archive` is a POST action → for a psychologist `has_object_permission` returns False because method is POST, keeping archive Admin/Staff. `terminate`/`advance_status` keep their own `IsAuthenticated` + in-body rule via `get_permissions` — unchanged.)

`backend/children/serializers.py` — add to `ChildSerializer`:

```python
    class Meta:
        model = Child
        fields = [
            ...existing fields...,
            "updated_at",
        ]
        read_only_fields = ["case_status", "updated_at"]

    def validate(self, attrs):
        request = self.context.get("request")
        role = getattr(getattr(getattr(request, "user", None), "role", None),
                       "role_name", None) if request else None
        if self.instance:
            new_name = attrs.get("fullname")
            if new_name and new_name != self.instance.fullname:
                raise serializers.ValidationError(
                    {"fullname": "The child's name cannot be changed after the record is created."})
            if role == "Psychologist":
                if ("assigned_psychologist" in attrs
                        and attrs["assigned_psychologist"] != self.instance.assigned_psychologist):
                    raise serializers.ValidationError(
                        {"psychologist": "Only administrators or staff can reassign a psychologist."})
                attrs.pop("assignee_sees_history", None)
                attrs.pop("status", None)
        return attrs
```

(Use `Role.PSYCHOLOGIST` via `from accounts.models import Role` and compare `role == Role.PSYCHOLOGIST` if the constant exists — check `accounts/models.py`; the string literal is the fallback.)

- [ ] **Step 4: Run tests — new file passes AND the whole suite stays green**

Run: `./venv/Scripts/python.exe manage.py test`
Expected: PASS, 223+ tests (218 + 5 new).

- [ ] **Step 5: Commit**

```bash
git add backend/accounts/permissions.py backend/children/views.py backend/children/serializers.py backend/children/tests/test_child_collab.py
git commit -m "feat(records): assigned psychologist can edit their child's record"
```

---

### Task 2: Backend — concurrent-edit safety (409) + presence heartbeat

**Files:**
- Modify: `backend/children/views.py` (ChildViewSet)
- Test: append to `backend/children/tests/test_child_collab.py`

**Interfaces:**
- Consumes: `updated_at` exposed by Task 1.
- Produces: writes carrying `expected_updated_at` (ISO string) get **409 + `{"detail", "current": <fresh record>}`** when stale; `GET/POST /api/children/<id>/presence/` — POST registers a 30s heartbeat, GET returns `{"others": [{"name","role"}]}` excluding self.

- [ ] **Step 1: Write the failing tests** (append to test_child_collab.py)

```python
class ConcurrencyPresenceTests(APITestCase):
    def setUp(self):
        self.staff = make_user("s2@t.ph", Role.STAFF)
        self.psych = make_user("p3@t.ph", Role.PSYCHOLOGIST)
        self.child = Child.objects.create(fullname="Ana Cruz",
                                          assigned_psychologist=self.psych)

    def test_stale_write_conflicts(self):
        self.client.force_authenticate(self.staff)
        stale = "2000-01-01T00:00:00+00:00"
        r = self.client.patch(f"/api/children/{self.child.id}/",
                              {"education_level": "G1", "expected_updated_at": stale},
                              format="json")
        self.assertEqual(r.status_code, 409)
        self.assertIn("current", r.data)

    def test_fresh_write_passes(self):
        self.client.force_authenticate(self.staff)
        current = self.client.get(f"/api/children/{self.child.id}/").data["updated_at"]
        r = self.client.patch(f"/api/children/{self.child.id}/",
                              {"education_level": "G1", "expected_updated_at": current},
                              format="json")
        self.assertEqual(r.status_code, 200)

    def test_presence_roundtrip(self):
        self.client.force_authenticate(self.psych)
        self.client.post(f"/api/children/{self.child.id}/presence/")
        self.client.force_authenticate(self.staff)
        r = self.client.get(f"/api/children/{self.child.id}/presence/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data["others"]), 1)
```

- [ ] **Step 2: Run to verify failure** — `manage.py test children.tests.test_child_collab -v 2` → 409 test fails (PATCH returns 200), presence 404s (no route).

- [ ] **Step 3: Implement** — in `backend/children/views.py`, inside `ChildViewSet`:

```python
import time
from django.core.cache import cache
from children.serializers import ChildSerializer
...
    def update(self, request, *args, **kwargs):
        expected = request.data.get("expected_updated_at")
        if expected:
            instance = self.get_object()
            if instance.updated_at.isoformat() != expected:
                return Response(
                    {"detail": "This record was updated by someone else while you were editing.",
                     "current": self.get_serializer(instance).data},
                    status=status.HTTP_409_CONFLICT)
        return super().update(request, *args, **kwargs)

    PRESENCE_TTL = 30  # seconds a heartbeat stays visible

    @action(detail=True, methods=["get", "post"])
    def presence(self, request, pk=None):
        child = self.get_object()
        key = f"child-presence:{child.id}"
        now = time.time()
        entries = {k: v for k, v in (cache.get(key) or {}).items()
                   if now - v["ts"] < self.PRESENCE_TTL}
        if request.method == "POST":
            entries[str(request.user.id)] = {
                "name": getattr(request.user, "fullname", "") or request.user.get_username(),
                "role": getattr(getattr(request.user, "role", None), "role_name", "") or "",
                "ts": now,
            }
            cache.set(key, entries, self.PRESENCE_TTL * 2)
        others = [{"name": v["name"], "role": v["role"]}
                  for k, v in entries.items() if k != str(request.user.id)]
        return Response({"others": others})
```

`presence` must be reachable by all three roles on records they can see: add it to the `get_permissions` special-case so psychologists aren't blocked by write rules — it only needs `IsAuthenticated` + queryset scoping:

```python
    def get_permissions(self):
        if self.action in ("terminate", "advance_status", "presence"):
            return [IsAuthenticated()]
        return super().get_permissions()
```

(Queryset note: `presence` is not in the `("retrieve", "terminate")` special-case, so psychologists resolve only their own children — correct. Staff/Admin resolve all active.)

- [ ] **Step 4: Run tests** — full suite green.

- [ ] **Step 5: Commit**

```bash
git add backend/children/views.py backend/children/tests/test_child_collab.py
git commit -m "feat(records): optimistic-lock 409 on stale saves + presence heartbeat"
```

---

### Task 3: Frontend — collab UI (psychologist edit, conflict banner, presence chip)

**Files:**
- Modify: `frontend/src/pages/Children.jsx`

**Interfaces:**
- Consumes: Task 1 permission (psych PATCH), Task 2 `expected_updated_at` 409 + `/presence/`.

- [ ] **Step 1: Enable edit for the assigned psychologist.** In `Children.jsx`:

```jsx
const canEditRecord = (c) => canManage
  || (isPsych && c.status === 'active' && String(c.psychologist) === String(user?.id));
```

Use it for: the row pencil button (line ~220, replace the `canManage &&` guard), and the drawer's Edit button — pass `canEdit={canEditRecord(sel)}` into `ChildDrawer` and render Edit when `canEdit` (drawer currently keys off `canManage`).

- [ ] **Step 2: Psychologist-safe form.** In `ChildForm`, accept a new prop `isPsych`; when true, replace the "Assign Psychologist" select + carry-history block with a read-only row showing the current assignment ("Reassignment is done by admin/staff."). In `save()` keep sending the unchanged `psychologist` value.

- [ ] **Step 3: Conflict-aware save.** In `save()`:

```jsx
const payload = { ...form, expected_updated_at: form.updated_at };
// existing `delete payload.x` lines stay; also: delete payload.updated_at;
...
} catch (err) {
  if (err.response?.status === 409) {
    const fresh = err.response.data.current;
    setError('');
    setForm((f) => ({ ...f, _conflict: fresh }));
    toast.error('Someone updated this record while you were editing.');
    return;
  }
  ...existing handling...
}
```

In `ChildForm`, when `form._conflict` render an `<Alert tone="warning">` at the top: "**{conflict.psychologist_name ? '' : ''}This record was just changed by a teammate.** Load their latest version, then re-apply your edits." with a Button "Load latest" → `setForm({ ...EMPTY, ...form._conflict, psychologist: form._conflict.psychologist || '', _origPsychologist: form._conflict.psychologist || '' })`.

- [ ] **Step 4: Presence hook.** Top of `Children.jsx` (module scope):

```jsx
function usePresence(childId) {
  const [others, setOthers] = useState([]);
  useEffect(() => {
    if (!childId) { setOthers([]); return; }
    let alive = true;
    const beat = () => api.post(`/children/${childId}/presence/`)
      .then((r) => alive && setOthers(r.data.others || [])).catch(() => {});
    beat();
    const t = setInterval(beat, 10000);
    return () => { alive = false; clearInterval(t); };
  }, [childId]);
  return others;
}
```

Call `const others = usePresence(form?.id || sel?.id);` in `Children()`, pass `others` to both `ChildDrawer` and `ChildForm`; each renders under its header when non-empty:

```jsx
{others.length > 0 && (
  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', padding: '8px 20px', background: 'var(--blue-50)', borderBottom: '1px solid var(--blue-100)' }}>
    <Icon name="users" size={14} style={{ color: 'var(--blue-600)' }} />
    {others.map((o, i) => <Badge key={i} tone="brand" size="sm" dot>{o.name} ({o.role}) is here</Badge>)}
  </div>
)}
```

- [ ] **Step 5: Verify** — `npm run build` passes. Live check (two browsers: staff + psychologist on the same child): psychologist edits an assigned child, staff sees "is here" chip, staff save after psychologist save triggers the conflict alert; "Load latest" pulls fresh values.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/Children.jsx
git commit -m "feat(records): multidisciplinary co-editing — psych edit, presence chips, conflict recovery"
```

---

### Task 4: Backend — termination archive history + admin reopen

**Files:**
- Modify: `backend/children/serializers.py`, `backend/children/views.py`
- Test: `backend/children/tests/test_reopen.py` (new)

**Interfaces:**
- Produces: `ChildSerializer.terminations` (full history list, newest first: `{date, reason_category, note, terminated_by}`); `POST /api/children/<id>/reopen/` (Admin-only) → 200 `{status:"active", case_status:"pre_assessment"}`; TerminationRecords are never deleted.

- [ ] **Step 1: Failing tests**

```python
# backend/children/tests/test_reopen.py
from rest_framework import status
from rest_framework.test import APITestCase
from accounts.models import Role
from children.models import Child, TerminationRecord
from children.tests.test_child_collab import make_user


class ReopenTests(APITestCase):
    def setUp(self):
        self.admin = make_user("ra@t.ph", Role.ADMINISTRATOR)
        self.psych = make_user("rp@t.ph", Role.PSYCHOLOGIST)
        self.child = Child.objects.create(
            fullname="Back Again", status=Child.INACTIVE,
            case_status=Child.STAGE_TERMINATED, assigned_psychologist=self.psych)
        TerminationRecord.objects.create(
            child=self.child, terminated_by=self.psych,
            reason_category="Services completed", note="Done for now.")

    def test_admin_reopen_restores_active_and_keeps_history(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post(f"/api/children/{self.child.id}/reopen/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.child.refresh_from_db()
        self.assertEqual(self.child.status, Child.ACTIVE)
        self.assertEqual(self.child.case_status, Child.STAGE_PRE_ASSESSMENT)
        self.assertEqual(self.child.terminations.count(), 1)  # history kept

    def test_non_admin_cannot_reopen(self):
        self.client.force_authenticate(self.psych)
        r = self.client.post(f"/api/children/{self.child.id}/reopen/")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_reopen_active_child_400(self):
        self.client.force_authenticate(self.admin)
        active = Child.objects.create(fullname="Still Active")
        r = self.client.post(f"/api/children/{active.id}/reopen/")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_serializer_exposes_termination_history(self):
        self.client.force_authenticate(self.admin)
        r = self.client.get(f"/api/children/{self.child.id}/")
        self.assertEqual(len(r.data["terminations"]), 1)
        self.assertEqual(r.data["terminations"][0]["reason_category"], "Services completed")
```

- [ ] **Step 2: Run to verify failure** — reopen 404s (no route), `terminations` KeyError.

- [ ] **Step 3: Implement.** Serializer — add method field (keep the existing singular `termination` for back-compat):

```python
    terminations = serializers.SerializerMethodField()
    # add "terminations" to Meta.fields

    def get_terminations(self, obj):
        out = []
        for t in obj.terminations.all():  # Meta.ordering: newest first
            by = t.terminated_by
            out.append({
                "date": t.date, "reason_category": t.reason_category, "note": t.note,
                "terminated_by": (getattr(by, "fullname", "") or getattr(by, "username", "")) or None,
            })
        return out
```

Views — `ChildViewSet`: allow the action through permissions/queryset like terminate, then:

```python
    def get_permissions(self):
        if self.action in ("terminate", "advance_status", "presence", "reopen"):
            return [IsAuthenticated()]
        return super().get_permissions()

    # in get_queryset, widen the retrieve special-case:
        if self.action in ("retrieve", "terminate", "reopen"):
            qs = self.model.objects.all().order_by("fullname")

    @action(detail=True, methods=["post"])
    def reopen(self, request, pk=None):
        """Admin-only: a terminated child returned to the clinic. Reactivate
        the case on top of the archived record — history is retained."""
        child = self.get_object()
        role = getattr(getattr(request.user, "role", None), "role_name", None)
        if role != Role.ADMINISTRATOR:
            return Response({"detail": "Only an administrator can reopen a terminated case."},
                            status=status.HTTP_403_FORBIDDEN)
        if child.status != Child.INACTIVE:
            return Response({"detail": "This case is already active."},
                            status=status.HTTP_400_BAD_REQUEST)
        child.status = Child.ACTIVE
        child.case_status = Child.STAGE_PRE_ASSESSMENT
        child.save(update_fields=["status", "case_status", "updated_at"])
        self._log(child, ActivityLog.UPDATED)
        return Response({"status": child.status, "case_status": child.case_status})
```

Also update the stale message in `advance_status` ("reactivation is not supported") → "This case is terminated; an administrator can reopen it from the child's record."

- [ ] **Step 4: Full suite green.**

- [ ] **Step 5: Commit** — `feat(records): termination history + admin reopen for returning children`

---

### Task 5: Frontend — admin archive view & reopen

**Files:**
- Modify: `frontend/src/pages/Children.jsx`

**Interfaces:** Consumes Task 4 (`terminations`, `/reopen/`).

- [ ] **Step 1:** Rename the status filter label `Inactive` → `Archived` (`STATUS_FILTERS`, and `StatusChip` inactive text → `Archived (Terminated)`), so the roster's Inactive tab reads as the archive. (Terminated records are already retained and listed — this makes it explicit.)

- [ ] **Step 2:** In `ChildDrawer`, replace the single-termination block with a full history list driven by `child.terminations`:

```jsx
{child.status === 'inactive' && (child.terminations || []).length > 0 && (
  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
    <div className="racco-eyebrow" style={{ fontSize: 10 }}>Termination history ({child.terminations.length})</div>
    {child.terminations.map((t, i) => (
      <div key={i} style={{ padding: '12px 14px', borderRadius: 'var(--radius-lg)', background: 'var(--ink-50)', border: '1px solid var(--border)' }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-strong)' }}>{t.reason_category}</div>
        <p style={{ fontSize: 12.5, color: 'var(--text-body)', margin: '4px 0 0', lineHeight: 1.5 }}>{t.note}</p>
        <div style={{ fontSize: 11.5, color: 'var(--text-faint)', marginTop: 6 }}>{t.date}{t.terminated_by ? ` · by ${t.terminated_by}` : ''}</div>
      </div>
    ))}
  </div>
)}
```

- [ ] **Step 3:** Reopen button. Pass `isAdmin` into `ChildDrawer`; when `isAdmin && child.status === 'inactive'` show footer `<Button variant="primary" fullWidth iconLeft={<Icon name="rotate-ccw" size={16} />}>Reopen Case</Button>` → `window.confirm('Reopen this case? All previous records and termination history are kept.')` then:

```jsx
const reopen = async (c) => {
  try {
    await api.post(`/children/${c.id}/reopen/`);
    toast.success(`${c.fullname}'s case is active again — previous records retained`);
    setSel(null); load(); refreshActivity();
  } catch (err) { toast.error(err.response?.data?.detail || 'Could not reopen the case.'); }
};
```

- [ ] **Step 4: Verify** — build + browser: terminate a seed child as admin, see it under Archived with history, reopen it, confirm history still shows if terminated again.

- [ ] **Step 5: Commit** — `feat(records): archived-case history view + admin reopen`

---

### Task 6: Child record panel — Previous Custodian, Address, Recommendation

**Files:**
- Modify: `backend/children/models.py`, `backend/children/serializers.py` (+ auto migration)
- Modify: `frontend/src/pages/Children.jsx`
- Test: append one test to `backend/children/tests/test_child_collab.py`

**Interfaces:** Produces `Child.recommendation` (TextField, blank) in API.

- [ ] **Step 1: Failing test** — append:

```python
    def test_recommendation_field_roundtrip(self):
        r = self.patch(self.staff, self.child, {"recommendation": "Refer for art therapy."})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["recommendation"], "Refer for art therapy.")
```

- [ ] **Step 2:** Model: after `medical_notes` add

```python
    # Free-text recommendations + fields not part of the agency's intake
    # interview live under the "Recommendation" section in the UI.
    recommendation = models.TextField(blank=True)
```

Run `./venv/Scripts/python.exe manage.py makemigrations children` then `migrate`. Add `"recommendation"` to `ChildSerializer.Meta.fields`.

- [ ] **Step 3: Frontend labels + regrouping** in `Children.jsx`:
  - `EMPTY` gains `recommendation: ''`.
  - Drawer `fields`: `['Surrendered By', ...]` → `['Previous Custodian', child.surrendered_by || '—']`; `['Location', location]` → `['Address', location]` (keep the barangay/municipality/province join). Remove `Referral Source`, `Education Level`, `Current Placement` from the main `fields` list.
  - Drawer: after the fields loop add a "Recommendation" group:

```jsx
<div>
  <div className="racco-eyebrow" style={{ fontSize: 10, marginBottom: 8 }}>Recommendation</div>
  {child.recommendation && <p style={{ fontSize: 13, color: 'var(--text-body)', margin: '0 0 10px', lineHeight: 1.55 }}>{child.recommendation}</p>}
  {[['Referral Source', child.referral_source], ['Education Level', child.education_level], ['Current Placement', child.current_placement]]
    .filter(([, v]) => v).map(([k, v]) => (
      <div key={k} style={{ display: 'flex', justifyContent: 'space-between', gap: 16, paddingBottom: 10, borderBottom: '1px solid var(--ink-100)', marginBottom: 10 }}>
        <span style={{ fontSize: 13, color: 'var(--text-muted)', fontWeight: 600 }}>{k}</span>
        <span style={{ fontSize: 13.5, color: 'var(--text-strong)', fontWeight: 700, textAlign: 'right' }}>{v}</span>
      </div>
  ))}
</div>
```

  (Referral reason + medical notes blocks stay where they are, but move them visually below the Recommendation group.)
  - Form: label `"Who Surrendered the Child"` → `"Previous Custodian"`; the `Profiling` eyebrow → `Recommendation` with hint text "Details beyond the agency's intake interview." and add at its end:

```jsx
<FormField label="Recommendation" hint="Follow-ups, referrals, and notes outside the intake timeline.">
  <textarea value={form.recommendation || ''} onChange={(e) => setForm({ ...form, recommendation: e.target.value })} rows={3} style={textarea} />
</FormField>
```

- [ ] **Step 4:** Backend suite green; `npm run build`; browser check drawer + form labels.

- [ ] **Step 5: Commit** — `feat(records): previous-custodian/address labels + recommendation section`

---

### Task 7: Backend — shared instrument catalog, audience, official title seeds

**Files:**
- Modify: `backend/clinical/models.py` (InstrumentCatalog), `backend/clinical/views.py` (InstrumentCatalogViewSet), instrument serializer in `backend/clinical/serializers.py` (+ auto migration)
- Create: `backend/clinical/management/commands/seed_instrument_titles.py`
- Test: `backend/clinical/tests/test_instrument_sharing.py` (new)

**Interfaces:**
- Produces: `InstrumentCatalog.audience` ∈ `child|adoptive_parent|both` (default `child`, exposed in API); psychologists see own + shared (`owner=NULL`) instruments; admins may create shared ones; `manage.py seed_instrument_titles` idempotently seeds 10 shared titles.

- [ ] **Step 1: Failing tests**

```python
# backend/clinical/tests/test_instrument_sharing.py
from django.core.management import call_command
from rest_framework.test import APITestCase
from accounts.models import Role
from children.tests.test_child_collab import make_user
from clinical.models import InstrumentCatalog


class InstrumentSharingTests(APITestCase):
    def setUp(self):
        self.admin = make_user("ia@t.ph", Role.ADMINISTRATOR)
        self.psych = make_user("ip@t.ph", Role.PSYCHOLOGIST)
        self.shared = InstrumentCatalog.objects.create(
            title="Raven's Progressive Matrices", owner=None, audience="both")
        self.own = InstrumentCatalog.objects.create(
            title="My Checklist", owner=self.psych, audience="child")

    def test_psychologist_sees_shared_plus_own(self):
        self.client.force_authenticate(self.psych)
        titles = [i["title"] for i in self.client.get("/api/instruments/").data]
        self.assertIn("Raven's Progressive Matrices", titles)
        self.assertIn("My Checklist", titles)

    def test_psychologist_cannot_edit_shared(self):
        self.client.force_authenticate(self.psych)
        r = self.client.patch(f"/api/instruments/{self.shared.id}/", {"title": "X"}, format="json")
        self.assertIn(r.status_code, (403, 404))

    def test_admin_create_without_owner_is_shared(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post("/api/instruments/", {"title": "Shared One"}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertIsNone(InstrumentCatalog.objects.get(title="Shared One").owner)

    def test_seed_command_idempotent(self):
        call_command("seed_instrument_titles")
        first = InstrumentCatalog.objects.filter(owner__isnull=True).count()
        call_command("seed_instrument_titles")
        self.assertEqual(InstrumentCatalog.objects.filter(owner__isnull=True).count(), first)
        self.assertTrue(InstrumentCatalog.objects.filter(
            title="Children's Apperception Test", audience="child").exists())
        self.assertTrue(InstrumentCatalog.objects.filter(
            title="Marital Satisfaction Inventory", audience="adoptive_parent").exists())
```

- [ ] **Step 2: Run to verify failure.**

- [ ] **Step 3: Implement.** Model — add to `InstrumentCatalog`:

```python
    AUDIENCE_CHOICES = [
        ("child", "For children"),
        ("adoptive_parent", "For prospective adoptive parents"),
        ("both", "Both"),
    ]
    audience = models.CharField(max_length=20, choices=AUDIENCE_CHOICES, default="child")
```

`makemigrations clinical && migrate`. Serializer: add `"audience"` to fields; make `owner` optional/nullable if it isn't.

Views — `InstrumentCatalogViewSet.get_queryset` psychologist branch (line ~46) becomes:

```python
            qs = qs.filter(Q(owner=self.request.user) | Q(owner__isnull=True))
```

(`from django.db.models import Q` already imported for templates.) `perform_create`: psychologist → `serializer.save(owner=self.request.user)` (unchanged); admin → `serializer.save(owner=serializer.validated_data.get("owner"))` — **delete** the "Select the psychologist who owns this instrument." ValidationError (no owner now means shared). Add write guard mirroring the template pattern:

```python
    def perform_update(self, serializer):
        obj = self.get_object()
        if _role(self.request) == Role.PSYCHOLOGIST and obj.owner_id != self.request.user.id:
            raise PermissionDenied("Shared instruments are managed by the administrator.")
        ...existing save...
```

Apply the same owner check inside the `deactivate` action if it exists (grep for `def deactivate` in the viewset).

Seed command:

```python
# backend/clinical/management/commands/seed_instrument_titles.py
from django.core.management.base import BaseCommand
from clinical.models import InstrumentCatalog

# RACCO I's official pre-assessment battery (titles only — copyright policy).
TITLES = [
    # For children
    ("Children's Problem Checklist", "behavioral", "child"),
    ("Adolescent Problem Checklist", "behavioral", "child"),
    ("Multiscore Depression Inventory for Children", "personality", "child"),
    ("Slosson Intelligence Test", "cognitive", "child"),
    ("Children's Apperception Test", "projective", "child"),
    # Used with both children and prospective adoptive parents
    ("Raven's Progressive Matrices", "cognitive", "both"),
    ("Sentence Completion Series", "projective", "both"),
    # For prospective adoptive parents
    ("Basic Personality Inventory", "personality", "adoptive_parent"),
    ("Marital Satisfaction Inventory", "other", "adoptive_parent"),
    ("Thematic Apperception Test", "projective", "adoptive_parent"),
]


class Command(BaseCommand):
    help = "Seed the shared (agency-wide) instrument title catalog. Idempotent."

    def handle(self, *args, **options):
        created = 0
        for title, category, audience in TITLES:
            _, was_created = InstrumentCatalog.objects.get_or_create(
                title=title, owner=None,
                defaults={"category": category, "audience": audience})
            created += int(was_created)
        self.stdout.write(self.style.SUCCESS(
            f"seed_instrument_titles: {created} created, {len(TITLES) - created} already present."))
```

- [ ] **Step 4:** Full suite green. Then seed the dev DB: `./venv/Scripts/python.exe manage.py seed_instrument_titles`.

- [ ] **Step 5: Commit** — `feat(instruments): shared agency catalog + audience + official title seeds`

---

### Task 8: Frontend — instrument module inside pre-assessment step 4

**Files:**
- Create: `frontend/src/components/InstrumentFormDrawer.jsx` (extracted from Instruments.jsx)
- Modify: `frontend/src/pages/Instruments.jsx`, `frontend/src/pages/PreAssessment.jsx`, `frontend/src/components/Sidebar.jsx`

**Interfaces:** Consumes Task 7 (`audience`, shared catalog). Produces `<InstrumentFormDrawer form setForm psychologists isAdmin error onSave onClose />`.

- [ ] **Step 1: Extract the drawer.** Move the instrument add/edit drawer JSX (Instruments.jsx lines ~201-237) plus its `CATEGORIES` list into the new component; add an Audience select:

```jsx
// frontend/src/components/InstrumentFormDrawer.jsx
import React from 'react';
import { Button, Input, Select, FormField, Alert, Icon, iconBtn, hoverLift } from '../ui';

export const CATEGORIES = [
  { v: 'cognitive', label: 'Cognitive' }, { v: 'behavioral', label: 'Behavioral' },
  { v: 'projective', label: 'Projective' }, { v: 'personality', label: 'Personality' },
  { v: 'developmental', label: 'Developmental' }, { v: 'achievement', label: 'Achievement' },
  { v: 'other', label: 'Other' },
];
export const AUDIENCES = [
  { v: 'child', label: 'For children' },
  { v: 'adoptive_parent', label: 'For prospective adoptive parents' },
  { v: 'both', label: 'Both' },
];
export const EMPTY_INSTRUMENT = { title: '', publisher: '', category: 'other', audience: 'child', age_range: '', notes: '', owner: '' };

export default function InstrumentFormDrawer({ form, setForm, psychologists = [], isAdmin = false, error, onSave, onClose }) {
  /* ...the exact drawer JSX moved from Instruments.jsx, with one added field
     after Category/Age Range:
     <FormField label="Audience">
       <Select value={form.audience || 'child'} onChange={(e) => setForm({ ...form, audience: e.target.value })}>
         {AUDIENCES.map((a) => <option key={a.v} value={a.v}>{a.label}</option>)}
       </Select>
     </FormField>
     and, for isAdmin, the owner select gains
     <option value="">— Shared (all psychologists) —</option> as the empty option. */
}
```

(Copy the JSX verbatim — buttons, save footer, error alert — replacing `saveInstrument`/`setForm(null)` with the `onSave`/`onClose` props.) Update `Instruments.jsx` to import and use it (`import InstrumentFormDrawer, { CATEGORIES, EMPTY_INSTRUMENT } from '../components/InstrumentFormDrawer';`), removing the duplicated JSX and the admin owner-required validation in `saveInstrument` (shared is now legal).

- [ ] **Step 2: Wizard step 4 gets the full module.** In `PreAssessment.jsx` step 3 card:
  - Import: `import InstrumentFormDrawer, { EMPTY_INSTRUMENT } from '../components/InstrumentFormDrawer';` and `useAuth`.
  - State: `const [instForm, setInstForm] = useState(null); const [instError, setInstError] = useState('');`
  - Reload helper: `const reloadInstruments = () => api.get('/instruments/').then((r) => setInstruments(r.data)).catch(() => {});`
  - Header row inside the card: title + `<Button variant="secondary" onClick={() => { setInstError(''); setInstForm({ ...EMPTY_INSTRUMENT }); }} iconLeft={<Icon name="plus" size={15} />}>Add instrument title</Button>`.
  - Render grouped: `const kids = instruments.filter((i) => i.audience !== 'adoptive_parent'); const paps = instruments.filter((i) => i.audience === 'adoptive_parent' || i.audience === 'both');` — two sections with eyebrows "For children" and "For prospective adoptive parents", each reusing the existing checkbox-label rows. Add a pencil `iconBtn` on rows the psychologist owns (`String(i.owner) === String(user?.id)`) → `setInstForm({ ...i, owner: i.owner || '' })`.
  - Save handler:

```jsx
const saveInstrument = async () => {
  setInstError('');
  if (!instForm.title.trim()) { setInstError('Title is required.'); return; }
  const payload = { ...instForm };
  delete payload.owner; delete payload.owner_name; delete payload.updated_at;
  try {
    if (instForm.id) await api.put(`/instruments/${instForm.id}/`, payload);
    else await api.post('/instruments/', payload);
    toast.success(instForm.id ? 'Instrument updated' : 'Instrument added');
    setInstForm(null); reloadInstruments();
  } catch (err) { setInstError(JSON.stringify(err.response?.data || 'Save failed')); }
};
```

  - Render `{instForm && <InstrumentFormDrawer form={instForm} setForm={setInstForm} error={instError} onSave={saveInstrument} onClose={() => setInstForm(null)} />}` at the end of the component.

- [ ] **Step 3: Sidebar + page gating.**
  - `Sidebar.jsx` NAV: replace the instruments row with two rows:

```jsx
{ to: '/instruments', label: 'Instruments & Agency Forms', icon: 'clipboard-pen', roles: ['Administrator'] },
{ to: '/instruments', label: 'Agency Form Templates', icon: 'file-text', roles: ['Psychologist'] },
```

  - `Instruments.jsx`: for psychologists default `tab` to `'forms'` and hide the tab switcher + catalog tab (`const showCatalog = isAdmin;`); the info alert for psychologists reads "Manage your consent and interview form templates. Instrument titles are managed inside the Pre-Assessment wizard (step 4)."

- [ ] **Step 4: Verify** — build; browser as psychologist: wizard step 4 shows both groups incl. the 10 seeded titles, add + edit inline works, selection still saves and completes; `/instruments` shows forms only. As admin: `/instruments` shows both tabs with Audience field and shared owner option.

- [ ] **Step 5: Commit** — `feat(pre-assessment): full instrument module embedded in step 4; sidebar split`

---

### Task 9: Frontend — Results & Reports grouped per child

**Files:**
- Modify: `frontend/src/pages/Report.jsx`

- [ ] **Step 1: Group + expand.** Add state `const [openChild, setOpenChild] = useState(null);` and a grouping memo after `visibleEntries`:

```jsx
const grouped = useMemo(() => {
  const map = new Map();
  for (const e of visibleEntries) {
    if (!map.has(e.child)) map.set(e.child, { child: e.child, child_name: e.child_name, entries: [] });
    map.get(e.child).entries.push(e);
  }
  return [...map.values()].sort((a, b) => (a.child_name || '').localeCompare(b.child_name || ''));
}, [visibleEntries]);
```

Replace the results-tab `<tbody>` with one header row per child + expandable detail rows:

```jsx
<thead><tr style={{ background: 'var(--ink-50)', borderBottom: '1px solid var(--border)' }}>
  {['Child', 'Entries', 'Latest Entry', 'Latest Classification', ''].map((h, i) => <th key={i} style={th}>{h}</th>)}
</tr></thead>
<tbody>
  {grouped.map((g) => {
    const open = openChild === g.child;
    const latest = g.entries[0]; // visibleEntries already sorted newest-first
    return (
      <React.Fragment key={g.child}>
        <tr tabIndex={0} role="button" aria-expanded={open}
          onClick={() => setOpenChild(open ? null : g.child)}
          onKeyDown={(ev) => { if (ev.key === 'Enter') setOpenChild(open ? null : g.child); }}
          style={{ borderBottom: '1px solid var(--ink-100)', cursor: 'pointer' }}
          onMouseEnter={(ev) => (ev.currentTarget.style.background = 'var(--blue-50)')}
          onMouseLeave={(ev) => (ev.currentTarget.style.background = 'transparent')}>
          <td style={{ padding: '12px 16px' }}>
            <div style={{ fontWeight: 700, fontSize: 13.5, color: 'var(--blue-700)' }}>{g.child_name}</div>
            <div className="racco-mono" style={{ fontSize: 11, color: 'var(--text-muted)' }}>{caseRef(g.child)}</div>
          </td>
          <td style={td}><Badge tone="brand" size="sm">{g.entries.length}</Badge></td>
          <td style={td}>{latest?.date || '—'}</td>
          <td style={{ ...td, fontWeight: 600, color: 'var(--text-strong)' }}>{latest?.classification || '—'}</td>
          <td style={{ padding: '12px 16px', textAlign: 'right' }}>
            <Icon name={open ? 'chevron-down' : 'chevron-right'} size={16} style={{ color: 'var(--text-faint)' }} />
          </td>
        </tr>
        {open && g.entries.map((e) => (
          <tr key={e.id} onClick={() => navigate(`/report/child/${e.child}`)}
            style={{ borderBottom: '1px solid var(--ink-100)', cursor: 'pointer', background: 'var(--ink-50)' }}>
            <td style={{ ...td, paddingLeft: 34, fontSize: 12.5 }}>{e.instrument_title || 'No instrument'}</td>
            <td style={td}></td>
            <td style={{ ...td, fontSize: 12.5 }}>{e.date}</td>
            <td style={{ ...td, fontSize: 12.5 }}>{e.classification || '—'}</td>
            <td style={{ ...td, fontSize: 12, color: 'var(--text-muted)', textAlign: 'right' }}>{e.entered_by_name || ''}</td>
          </tr>
        ))}
      </React.Fragment>
    );
  })}
</tbody>
```

Update the tab label to `Result Entries (${grouped.length} children)` — wait, keep count of entries but show children: `['results', `Result Entries (${entries.length})`]` stays fine. CSV export keeps the flat `visibleEntries` (unchanged).

- [ ] **Step 2: Verify** — build; browser: Mika Santos shows one row with entry count; clicking expands all her entries; an expanded entry opens `/report/child/2`.

- [ ] **Step 3: Commit** — `feat(reports): result entries grouped per child with expandable history`

---

### Task 10: Frontend — bento dashboard, mini calendar, calendar off the sidebar

**Files:**
- Create: `frontend/src/components/MiniCalendar.jsx`
- Modify: `frontend/src/pages/Dashboard.jsx`, `frontend/src/components/Sidebar.jsx`

**Interfaces:** Consumes existing `GET /api/reports/dashboard/?range=monthly` and `GET /api/appointments/` (role-scoped). NO backend changes (reports_views.py is touched by the in-flight session).

- [ ] **Step 1: MiniCalendar component** — custom month grid, appointment dots, click → full calendar:

```jsx
// frontend/src/components/MiniCalendar.jsx
import React, { useMemo, useState } from 'react';
import { Icon } from '../ui';

const DOW = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'];
const pad = (n) => String(n).padStart(2, '0');
const key = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;

export default function MiniCalendar({ appointments = [], onOpen }) {
  const [cursor, setCursor] = useState(() => { const d = new Date(); d.setDate(1); return d; });
  const marked = useMemo(() => {
    const s = new Set();
    appointments.forEach((a) => { if (a.start) s.add(String(a.start).slice(0, 10)); });
    return s;
  }, [appointments]);

  const cells = useMemo(() => {
    const first = new Date(cursor.getFullYear(), cursor.getMonth(), 1);
    const out = [];
    for (let i = 0; i < first.getDay(); i++) out.push(null);
    const days = new Date(cursor.getFullYear(), cursor.getMonth() + 1, 0).getDate();
    for (let d = 1; d <= days; d++) out.push(new Date(cursor.getFullYear(), cursor.getMonth(), d));
    return out;
  }, [cursor]);

  const today = key(new Date());
  const nav = (n) => setCursor((c) => new Date(c.getFullYear(), c.getMonth() + n, 1));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, cursor: 'pointer' }}
      role="button" tabIndex={0} title="Open the full calendar"
      onClick={onOpen} onKeyDown={(e) => { if (e.key === 'Enter') onOpen(); }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <button aria-label="Previous month" onClick={(e) => { e.stopPropagation(); nav(-1); }}
          style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: 'var(--text-muted)', padding: 4 }}><Icon name="chevron-left" size={16} /></button>
        <span style={{ fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 13.5, color: 'var(--text-strong)' }}>
          {cursor.toLocaleString('en-US', { month: 'long', year: 'numeric' })}
        </span>
        <button aria-label="Next month" onClick={(e) => { e.stopPropagation(); nav(1); }}
          style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: 'var(--text-muted)', padding: 4 }}><Icon name="chevron-right" size={16} /></button>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7,1fr)', gap: 2, textAlign: 'center' }}>
        {DOW.map((d) => <span key={d} style={{ fontSize: 10, fontWeight: 800, color: 'var(--text-faint)', letterSpacing: '0.04em' }}>{d}</span>)}
        {cells.map((d, i) => d === null ? <span key={`x${i}`} /> : (
          <span key={key(d)} style={{
            position: 'relative', fontSize: 11.5, fontWeight: key(d) === today ? 800 : 600,
            padding: '4px 0', borderRadius: 'var(--radius-sm)', fontFamily: 'var(--font-mono)',
            background: key(d) === today ? 'var(--blue-600)' : 'transparent',
            color: key(d) === today ? '#fff' : 'var(--text-body)',
          }}>
            {d.getDate()}
            {marked.has(key(d)) && <span style={{ position: 'absolute', left: '50%', transform: 'translateX(-50%)', bottom: 0, width: 4, height: 4, borderRadius: '50%', background: key(d) === today ? '#fff' : 'var(--blue-500)' }} />}
          </span>
        ))}
      </div>
      <div style={{ fontSize: 11, color: 'var(--blue-600)', fontWeight: 700, display: 'flex', alignItems: 'center', gap: 4 }}>
        <Icon name="maximize-2" size={12} /> Click to open the full calendar
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Bento Dashboard.** Rework `Dashboard.jsx` around a viewport-fit grid; every existing module is kept but becomes a fixed-height tile with internal scrolling. Add `const [appointments, setAppointments] = useState([]);` and fetch `api.get('/appointments/').then((r) => setAppointments(r.data)).catch(() => {});` alongside the stats fetch. Layout skeleton (replace the current return; reuse the existing tile JSX inside `<Tile>` wrappers):

```jsx
const Tile = ({ children, span = 1, ...cardProps }) => (
  <Card {...cardProps} padding="16px"
    style={{ gridColumn: `span ${span}`, display: 'flex', flexDirection: 'column', minHeight: 0, ...cardProps.style }}>
    <div className="racco-scroll" style={{ flex: 1, minHeight: 0, overflowY: 'auto' }}>{children}</div>
  </Card>
);

return (
  <div style={{ padding: '18px 22px', height: 'calc(100vh - var(--topbar-h, 64px))', display: 'flex', flexDirection: 'column', gap: 14, overflow: 'hidden' }}>
    {/* Row 1 — slim quick actions */}
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', flex: 'none' }}>
      <span style={{ fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 15, color: 'var(--text-strong)', marginRight: 4 }}>Quick actions</span>
      {actions.map((a) => (
        <Button key={a.label} variant={a.variant} onClick={() => navigate(a.to)} iconLeft={<Icon name={a.icon} size={16} />}>{a.label}</Button>
      ))}
    </div>
    {/* Row 2 — stat tiles */}
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,minmax(0,1fr))', gap: 14, flex: 'none' }}>
      {/* the 4 existing StatCards unchanged */}
    </div>
    {/* Bento body — two fixed rows, tiles scroll internally */}
    <div style={{ flex: 1, minHeight: 0, display: 'grid', gap: 14, gridTemplateColumns: 'repeat(4,minmax(0,1fr))', gridTemplateRows: 'minmax(0,1fr) minmax(0,1fr)' }}>
      <Tile eyebrow="Today" title="Schedule" span={2}>{/* today_schedule strip + availability (existing JSX) */}</Tile>
      <Tile eyebrow="Schedule" title="Calendar"><MiniCalendar appointments={appointments} onOpen={() => navigate('/schedule')} /></Tile>
      <Tile eyebrow="Follow-up needed" title="Care-gap alerts">{/* existing gaps list — drop the .slice(0,8), the tile scrolls */}</Tile>
      <Tile eyebrow="Census" title="Intake vs. termination" span={2}>{/* existing BarChart at height 180 + case-mix badges */}</Tile>
      <Tile eyebrow="Clinical team" title="Sessions by psychologist">{/* existing per_psychologist + counseling badges */}</Tile>
      <Tile eyebrow="Live" title="Activity Feed">{/* existing feed — use events.slice(0, 15); tile scrolls */}</Tile>
    </div>
  </div>
);
```

Notes for the implementer: check `frontend/src/ui` for how `Card` handles `style`/`padding` (it already accepts both — Dashboard uses them today). If no `--topbar-h` token exists, measure the Topbar height (grep `Topbar.jsx` for its height) and hardcode `calc(100vh - 64px)` accordingly. Below 1100px width add a fallback: wrap the two grids' style with `window.innerWidth`-independent CSS by adding `minWidth: 0` on tiles; page-level scroll on small screens is acceptable (`overflow: 'hidden auto'` via a `@media`-less inline compromise: set `overflowY: 'auto'` instead of `'hidden'` on the outer div). Chart height: give the intake-vs-termination `ResponsiveContainer` wrapper `height: '100%', minHeight: 150` instead of fixed 220.

- [ ] **Step 3: Sidebar** — delete the Schedule section + Calendar row from `NAV`:

```jsx
// remove these two lines
{ section: 'Schedule' },
{ to: '/schedule', label: 'Calendar', icon: 'calendar', roles: [...] },
```

Route `/schedule` in App.jsx stays (dashboard tiles + quick action navigate to it). Keep the "Calendar" quick-action button.

- [ ] **Step 4: Verify** — build; browser at 1280×800: dashboard fits with NO page scroll, every tile scrolls internally, mini calendar shows dots on appointment days (seed appointment exists on child 2), clicking it opens the full `/schedule` page, sidebar has no Calendar entry for any role (check all 3 accounts).

- [ ] **Step 5: Commit** — `feat(dashboard): no-scroll bento layout + clickable mini calendar; calendar leaves sidebar`

---

### Task 11: Backend — pin Ollama to the local machine (privacy hardening)

**Files:**
- Modify: `backend/ai/views.py` (`AISettingSerializer`, line ~25), `backend/config/settings.py`
- Modify: `frontend/src/pages/Settings.jsx` (hint copy)
- Test: append to an existing file in `backend/ai/tests/` (pick the one covering AISetting; else create `backend/ai/tests/test_settings_guard.py`)

**Why:** The DPA-compliance claim ("data never leaves the building") currently depends on an admin-editable URL that could silently point at a remote host. Enforce it.

- [ ] **Step 1: Failing test**

```python
# backend/ai/tests/test_settings_guard.py
from rest_framework.test import APITestCase
from accounts.models import Role
from children.tests.test_child_collab import make_user


class OllamaUrlGuardTests(APITestCase):
    def setUp(self):
        self.admin = make_user("ou@t.ph", Role.ADMINISTRATOR)
        self.client.force_authenticate(self.admin)

    def test_remote_url_rejected(self):
        r = self.client.patch("/api/ai/settings/", {"ollama_url": "http://203.0.113.5:11434"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_localhost_accepted(self):
        r = self.client.patch("/api/ai/settings/", {"ollama_url": "http://127.0.0.1:11434"}, format="json")
        self.assertEqual(r.status_code, 200)
```

(Check the actual settings endpoint path/method in `backend/ai/urls.py` first and adjust — it may be PUT on `/api/ai/settings/`.)

- [ ] **Step 2: Implement.** `backend/config/settings.py`: `ALLOW_REMOTE_OLLAMA = os.environ.get("ALLOW_REMOTE_OLLAMA", "false").lower() == "true"` (near the other env reads). `AISettingSerializer`:

```python
from urllib.parse import urlparse
from django.conf import settings as django_settings

    def validate_ollama_url(self, value):
        host = (urlparse(value).hostname or "").lower()
        if host in ("localhost", "127.0.0.1", "::1") or django_settings.ALLOW_REMOTE_OLLAMA:
            return value
        raise serializers.ValidationError(
            "AI must run on this machine (Data Privacy Act commitment). "
            "Use http://localhost:11434, or set ALLOW_REMOTE_OLLAMA=true in the "
            "server environment if the agency knowingly hosts Ollama elsewhere on-premises.")
```

`Settings.jsx`: under the Ollama URL input, set/extend the hint: "Must point to this machine (localhost) — child data never leaves RACCO I's hardware."

- [ ] **Step 3:** Full suite green; build.

- [ ] **Step 4: Commit** — `feat(ai): enforce localhost-only Ollama endpoint (DPA guarantee)`

---

### Task 12: Backend + frontend — split child name into First / M.I. / Last

**Files:**
- Modify: `backend/children/models.py`, `backend/children/serializers.py` (+ schema migration + data migration)
- Modify: `frontend/src/pages/Children.jsx`
- Test: append to `backend/children/tests/test_child_collab.py`

**Interfaces:**
- Produces: `Child.first_name`, `Child.middle_initial`, `Child.last_name` (API-writable); `fullname` becomes read-only in the API, auto-composed as `"First M. Last"` on save. Everything that reads `fullname`/`child_name` (reports, schedule, AI briefs) is untouched.

- [ ] **Step 1: Failing tests** — append:

```python
class NameSplitTests(APITestCase):
    def setUp(self):
        self.staff = make_user("ns@t.ph", Role.STAFF)
        self.client.force_authenticate(self.staff)

    def test_create_composes_fullname(self):
        r = self.client.post("/api/children/", {
            "first_name": "Mika", "middle_initial": "R", "last_name": "Santos",
            "birth_date": "2016-01-10", "gender": "Female", "case_type": "Foster Care",
        }, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["fullname"], "Mika R. Santos")

    def test_name_parts_locked_after_create(self):
        r = self.client.post("/api/children/", {
            "first_name": "Ana", "last_name": "Cruz",
            "birth_date": "2016-01-10", "gender": "Female", "case_type": "Foster Care",
        }, format="json")
        r2 = self.client.patch(f"/api/children/{r.data['id']}/",
                               {"last_name": "Reyes"}, format="json")
        self.assertEqual(r2.status_code, 400)
```

- [ ] **Step 2: Run to verify failure.**

- [ ] **Step 3: Implement.** Model — before `fullname`:

```python
    # Name parts (adviser): fullname stays as the composed display column so
    # every existing consumer keeps working.
    first_name = models.CharField(max_length=100, blank=True)
    middle_initial = models.CharField(max_length=5, blank=True)
    last_name = models.CharField(max_length=100, blank=True)

    def save(self, *args, **kwargs):
        if self.first_name or self.last_name:
            mi = f"{self.middle_initial.rstrip('.')}." if self.middle_initial else ""
            self.fullname = " ".join(p for p in (self.first_name, mi, self.last_name) if p)
        super().save(*args, **kwargs)
```

`makemigrations children`, then a data migration (`manage.py makemigrations children --empty -n split_existing_fullnames`):

```python
def split_names(apps, schema_editor):
    Child = apps.get_model("children", "Child")
    for c in Child.objects.all():
        parts = (c.fullname or "").split()
        if not parts:
            continue
        c.last_name = parts[-1] if len(parts) > 1 else ""
        c.first_name = " ".join(parts[:-1]) if len(parts) > 1 else parts[0]
        c.save(update_fields=["first_name", "last_name"])

# operations = [migrations.RunPython(split_names, migrations.RunPython.noop)]
```

Serializer: add `"first_name", "middle_initial", "last_name"` to fields; move `"fullname"` into `read_only_fields`; extend the Task 1 `validate()` name-lock to the three parts:

```python
        if self.instance:
            for f in ("first_name", "middle_initial", "last_name", "fullname"):
                if f in attrs and attrs[f] != getattr(self.instance, f):
                    raise serializers.ValidationError(
                        {f: "The child's name cannot be changed after the record is created."})
```

(Replace the previous fullname-only check.)

- [ ] **Step 4: Frontend.** `Children.jsx` `EMPTY` gains `first_name: '', middle_initial: '', last_name: ''` (drop `fullname` from EMPTY). Create-mode name block becomes:

```jsx
<div style={{ display: 'grid', gridTemplateColumns: '2fr 64px 2fr', gap: 10 }}>
  <FormField label="First Name" required>
    <Input value={form.first_name} onChange={(e) => setForm({ ...form, first_name: e.target.value })} required />
  </FormField>
  <FormField label="M.I.">
    <Input value={form.middle_initial} maxLength={3} onChange={(e) => setForm({ ...form, middle_initial: e.target.value })} />
  </FormField>
  <FormField label="Last Name" required>
    <Input value={form.last_name} onChange={(e) => setForm({ ...form, last_name: e.target.value })} required />
  </FormField>
</div>
```

Edit mode keeps the locked composed `form.fullname` display (unchanged). In `save()` also `delete payload.fullname;` on edit.

- [ ] **Step 5:** Full backend suite green (composition must not break existing fullname-based tests); build; browser: add a child with parts, roster/drawer show "Mika R. Santos".

- [ ] **Step 6: Commit** — `feat(records): first/MI/last name fields with composed fullname`

---

### Task 13: Input constraints (age 5–17, required *) + specific field labels

**Files:**
- Modify: `backend/children/serializers.py`
- Modify: `frontend/src/pages/Children.jsx`
- Test: append to `backend/children/tests/test_child_collab.py`

**Interfaces:** Consumes Task 12 (name parts required on create).

- [ ] **Step 1: Failing tests** — append (inside `NameSplitTests` or a new class with the same staff setup):

```python
    def _payload(self, **over):
        base = {"first_name": "Leo", "last_name": "Diaz", "birth_date": "2016-01-10",
                "gender": "Male", "case_type": "Foster Care"}
        base.update(over)
        return base

    def test_age_below_5_rejected(self):
        r = self.client.post("/api/children/", self._payload(birth_date="2024-01-01"), format="json")
        self.assertEqual(r.status_code, 400)

    def test_age_above_17_rejected(self):
        r = self.client.post("/api/children/", self._payload(birth_date="2000-01-01"), format="json")
        self.assertEqual(r.status_code, 400)

    def test_required_fields_on_create(self):
        r = self.client.post("/api/children/", {"first_name": "Solo"}, format="json")
        self.assertEqual(r.status_code, 400)
        for f in ("last_name", "birth_date", "gender", "case_type"):
            self.assertIn(f, r.data)
```

- [ ] **Step 2: Run to verify failure.**

- [ ] **Step 3: Implement** in `ChildSerializer`:

```python
from django.utils import timezone

    def validate_birth_date(self, value):
        if value is None:
            return value
        today = timezone.localdate()
        age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))
        if not (5 <= age <= 17):
            raise serializers.ValidationError(
                "The child must be between 5 and 17 years old.")
        return value

    def validate(self, attrs):
        ...existing Task 1/12 checks...
        if not self.instance:  # create: enforce the agency's required fields
            missing = {f: "This field is required."
                       for f in ("first_name", "last_name", "birth_date", "gender", "case_type")
                       if not attrs.get(f)}
            if missing:
                raise serializers.ValidationError(missing)
        return attrs
```

- [ ] **Step 4: Frontend.** In `ChildForm`:
  - Add `required` to the FormFields for Birth Date, Gender, Case Type (First/Last already from Task 12) — `FormField`'s `required` prop renders the red `*` ([ui/index.jsx:258](frontend/src/ui/index.jsx)). All other fields stay optional (no `*`).
  - Birth Date input gets `min`/`max` bounds: `max` = today minus 5 years, `min` = today minus 18 years (compute with `new Date()` + `toISOString().slice(0,10)`).
  - Label renames everywhere in `Children.jsx` (form + drawer + the Task 6 Recommendation group): `"Education Level"` → `"Educational Placement"`, `"Current Placement"` → `"Place of Recovery"` (placeholder: "e.g. Foster family, residential facility" stays).
  - Save button disabled until required fields are filled: `disabled={!form.id && !(form.first_name && form.last_name && form.birth_date && form.gender && form.case_type)}`.

- [ ] **Step 5:** Suite green; build; browser: `*` markers show, 3-year-old birth date rejected with the message, labels updated.

- [ ] **Step 6: Commit** — `feat(records): age 5-17 validation, required-field markers, specific labels`

---

### Task 14: Records list — Last-In-First-Out ordering

**Files:**
- Modify: `frontend/src/pages/Children.jsx`

- [ ] **Step 1:** Add `const [sortMode, setSortMode] = useState('newest');` and replace the `.sort(...)` in `visible` with:

```jsx
.sort((a, b) => sortMode === 'newest'
  ? b.id - a.id  // LIFO: newest record first
  : a.fullname.localeCompare(b.fullname, undefined, { sensitivity: 'base' }));
```

Next to the status filter pills add a small toggle:

```jsx
<div style={{ display: 'inline-flex', gap: 4, background: 'var(--ink-50)', border: '1px solid var(--border)', borderRadius: 'var(--radius-pill)', padding: 3 }}>
  {[['newest', 'Newest first'], ['az', 'A–Z']].map(([k, label]) => (
    <button key={k} onClick={() => setSortMode(k)} style={{ padding: '5px 12px', borderRadius: 'var(--radius-pill)', border: 'none', cursor: 'pointer', fontFamily: 'var(--font-sans)', fontWeight: 700, fontSize: 12, background: sortMode === k ? 'var(--blue-600)' : 'transparent', color: sortMode === k ? '#fff' : 'var(--text-muted)' }}>{label}</button>
  ))}
</div>
```

- [ ] **Step 2:** Build + browser: default order is newest record on top; toggle restores A–Z.

- [ ] **Step 3: Commit** — `feat(records): LIFO default ordering with A-Z toggle`

---

### Task 15: Scheduling upgrades — weekday checkboxes, next-slot suggestions, slot-click booking

**Files:**
- Modify: `backend/scheduling/views.py` (AvailabilityBlockViewSet)
- Modify: `frontend/src/pages/Schedule.jsx`, `frontend/src/pages/Children.jsx` (drawer)
- Test: `backend/scheduling/tests/test_next_slots.py` (new; put beside existing scheduling tests — check the folder layout first)

**Interfaces:**
- Produces: `GET /api/availability/next-slots/?child=<id>` → `{"psychologist": "<name>", "slots": [{"date","weekday","start","end","remaining"}]}` (next 14 days, max 6 slots, capacity-aware). 400 if the child has no assigned psychologist.

- [ ] **Step 1: Failing test**

```python
# backend/scheduling/tests/test_next_slots.py
import datetime
from django.utils import timezone
from rest_framework.test import APITestCase
from accounts.models import Role
from children.tests.test_child_collab import make_user
from children.models import Child
from scheduling.models import AvailabilityBlock


class NextSlotsTests(APITestCase):
    def setUp(self):
        self.staff = make_user("sl@t.ph", Role.STAFF)
        self.psych = make_user("pl@t.ph", Role.PSYCHOLOGIST)
        self.child = Child.objects.create(fullname="Slot Kid", assigned_psychologist=self.psych)
        tomorrow = timezone.localdate() + datetime.timedelta(days=1)
        AvailabilityBlock.objects.create(
            psychologist=self.psych, weekday=tomorrow.weekday(),
            start_time=datetime.time(9), end_time=datetime.time(12), capacity=2)
        self.client.force_authenticate(self.staff)

    def test_returns_upcoming_slots(self):
        r = self.client.get(f"/api/availability/next-slots/?child={self.child.id}")
        self.assertEqual(r.status_code, 200)
        self.assertGreaterEqual(len(r.data["slots"]), 1)
        self.assertEqual(r.data["slots"][0]["remaining"], 2)

    def test_unassigned_child_400(self):
        solo = Child.objects.create(fullname="No Psych")
        r = self.client.get(f"/api/availability/next-slots/?child={solo.id}")
        self.assertEqual(r.status_code, 400)
```

- [ ] **Step 2: Run to verify failure** (404 — no route).

- [ ] **Step 3: Backend.** In `AvailabilityBlockViewSet`:

```python
import datetime
from django.utils import timezone
from rest_framework.decorators import action
from children.models import Child
from scheduling.models import Appointment

    @action(detail=False, methods=["get"], url_path="next-slots")
    def next_slots(self, request):
        """Upcoming bookable windows for a child's assigned psychologist —
        staff/psychologist see at a glance when the child can be counseled."""
        child_id = request.query_params.get("child")
        try:
            child = Child.objects.get(pk=child_id)
        except (Child.DoesNotExist, ValueError, TypeError):
            return Response({"detail": "Unknown child."}, status=400)
        psych = child.assigned_psychologist
        if psych is None:
            return Response({"detail": "This child has no assigned psychologist yet."}, status=400)
        blocks = AvailabilityBlock.objects.filter(psychologist=psych, active=True)
        today = timezone.localdate()
        slots = []
        for offset in range(0, 14):
            day = today + datetime.timedelta(days=offset)
            for b in blocks:
                if b.date is not None and b.date != day:
                    continue
                if b.date is None and (b.weekday is None or b.weekday != day.weekday()):
                    continue
                booked = Appointment.objects.filter(
                    psychologist=psych, status=Appointment.SCHEDULED,
                    start__date=day, start__time__gte=b.start_time,
                    start__time__lt=b.end_time).count()
                remaining = b.capacity - booked
                if remaining > 0:
                    slots.append({
                        "date": day.isoformat(),
                        "weekday": day.strftime("%A"),
                        "start": str(b.start_time)[:5], "end": str(b.end_time)[:5],
                        "remaining": remaining,
                    })
            if len(slots) >= 6:
                break
        return Response({
            "psychologist": getattr(psych, "fullname", "") or psych.get_username(),
            "slots": slots[:6],
        })
```

(Match `_validate_booking`'s counting semantics — read it first and mirror how it filters statuses/time windows so the suggestion never contradicts the booking validator.)

- [ ] **Step 4: Weekday checkboxes (create mode).** `Schedule.jsx` — `openCreateBlock` seeds `weekdays: []` instead of `weekday: 0`; the weekly branch of the drawer becomes (create only — edit keeps the single-weekday select bound to `blockForm.weekday`):

```jsx
{blockForm.mode === 'weekly' && !blockForm.id ? (
  <FormField label="Weekdays" required hint="Tick every day this window repeats — one block is created per day.">
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
      {WEEKDAYS.map((d, i) => {
        const on = blockForm.weekdays.includes(i);
        return (
          <label key={d} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '6px 11px', borderRadius: 'var(--radius-pill)', border: `1px solid ${on ? 'var(--blue-500)' : 'var(--border)'}`, background: on ? 'var(--blue-50)' : 'var(--surface)', fontSize: 12.5, fontWeight: 700, color: on ? 'var(--blue-700)' : 'var(--text-body)', cursor: 'pointer' }}>
            <input type="checkbox" checked={on} style={{ accentColor: 'var(--blue-600)' }}
              onChange={() => setBlockForm((f) => ({ ...f, weekdays: on ? f.weekdays.filter((x) => x !== i) : [...f.weekdays, i] }))} />
            {d.slice(0, 3)}
          </label>
        );
      })}
    </div>
  </FormField>
) : blockForm.mode === 'weekly' ? (
  /* existing single-weekday Select for edit */
) : (
  /* existing date input */
)}
```

`saveBlock` create-path loops: `for (const wd of blockForm.weekdays) { await api.post('/availability/', { ...payload, weekday: wd, date: null }); }` (validate `blockForm.weekdays.length > 0` first, error "Tick at least one weekday."). Edit path unchanged.

- [ ] **Step 5: Booking optimization.** In `Schedule.jsx`:
  - When staff/admin picks a child, auto-select their assigned psychologist: in the Child `<Select>` onChange, also `const c = children.find((x) => String(x.id) === e.target.value); setBooking({ ...booking, child: e.target.value, psychologist: booking.psychologist || (c?.psychologist ?? '') });`
  - Under the Date/Time grid, suggest slots: state `const [slotHints, setSlotHints] = useState(null);` — `useEffect` on `booking?.child`: `api.get(`/availability/next-slots/?child=${booking.child}`).then((r) => setSlotHints(r.data)).catch(() => setSlotHints(null));` Render:

```jsx
{slotHints?.slots?.length > 0 && (
  <div>
    <div className="racco-eyebrow" style={{ fontSize: 10, marginBottom: 6 }}>Next openings — {slotHints.psychologist}</div>
    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
      {slotHints.slots.map((s, i) => (
        <button key={i} type="button" onClick={() => setBooking({ ...booking, date: s.date, time: s.start })}
          style={{ padding: '5px 10px', borderRadius: 'var(--radius-pill)', border: '1px solid var(--blue-300)', background: 'var(--blue-50)', color: 'var(--blue-700)', fontFamily: 'var(--font-sans)', fontWeight: 700, fontSize: 11.5, cursor: 'pointer' }}>
          {s.weekday.slice(0, 3)} {s.date.slice(5)} · {s.start} ({s.remaining} open)
        </button>
      ))}
    </div>
  </div>
)}
```

  - Slot-click "add event" (adviser #13): on the `<Calendar>` add `selectable onSelectSlot={(slot) => { if (!canBook) return; setError(''); setBooking({ child: '', psychologist: isPsych ? '' : '', date: format(slot.start, 'yyyy-MM-dd'), time: format(slot.start, 'HH:mm') === '00:00' ? '09:00' : format(slot.start, 'HH:mm'), purpose: 'session', duration: 60, notes: '' }); }}` (`format` is already imported from date-fns). Status buttons (Completed/No-show/Cancel) already exist in the detail modal — verify only.

- [ ] **Step 6: Child drawer "when can they be counseled" (adviser #6).** In `Children.jsx` `ChildDrawer`, when `child.status === 'active' && child.psychologist_name`, fetch on mount `api.get(`/availability/next-slots/?child=${child.id}`)` into local state `slots`; render after the fields list:

```jsx
{slots?.slots?.length > 0 && (
  <div>
    <div className="racco-eyebrow" style={{ fontSize: 10, marginBottom: 8 }}>Next possible sessions — {slots.psychologist}</div>
    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
      {slots.slots.map((s, i) => <Badge key={i} tone="success" size="sm" dot>{s.weekday.slice(0, 3)} {s.date.slice(5)} · {s.start}–{s.end}</Badge>)}
    </div>
  </div>
)}
```

  - Adviser #7 (staff sees psychologist availability): ALREADY works — `/availability/` returns all blocks to staff/admin and Schedule.jsx lists them with psychologist names ("Psychologist availability" card); the dashboard shows `availability_today`. Verify in browser as staff, no code change expected.

- [ ] **Step 7:** Backend suite green; build; live checks per steps 4–6.

- [ ] **Step 8: Commit** — `feat(schedule): weekday multi-select, next-slot suggestions, slot-click booking`

---

### Task 16: Clickable notifications that navigate to their subject

**Files:**
- Modify: `frontend/src/components/Topbar.jsx`, `frontend/src/pages/Dashboard.jsx` (activity feed rows)

- [ ] **Step 1:** In `Topbar.jsx` add beside `eventText` (module scope, exported):

```jsx
export function eventDestination(e, role) {
  const type = (e.entity_type || '').toLowerCase();
  if (type === 'child') return e.entity_id ? `/report/child/${e.entity_id}` : '/children';
  if (type === 'guardian') return '/children';
  if (type === 'appointment' || type === 'availabilityblock') return '/schedule';
  if (['instrumentcatalog', 'instrument', 'agencyformtemplate', 'questionnaire'].includes(type)) return '/instruments';
  if (e.category === 'user' || e.category === 'security' || type === 'user')
    return role === 'Administrator' ? '/users' : '/';
  return '/';
}
```

Convert each notification row (the element rendering `eventText(n)` around line 158) from a `<span>`-in-`<div>` into a `<button>` with the row's existing styles plus `border: 'none', background: 'transparent', width: '100%', textAlign: 'left', cursor: 'pointer'` and `onClick={() => { setNotifOpen(false); navigate(eventDestination(n, role)); }}` — `role` is already derived in the component (check for `user?.role_name`; add it if not). Add a hover tint (`hoverTint('var(--blue-50)')` is already imported/used at line 165).

- [ ] **Step 2:** Dashboard Activity Feed tile rows get the same behavior: `import { eventText, timeAgo, eventDestination } from '../components/Topbar';` and wrap each feed row in a clickable element navigating to `eventDestination(a, role)`.

- [ ] **Step 3:** Build; browser: a "created child X" notification opens X's report page; a security/login event as admin opens `/users`; a psychologist clicking a user event lands on the dashboard, not a 403 page.

- [ ] **Step 4: Commit** — `feat(notifications): click-through navigation to the notification's subject`

---

### Task 17: Consent step rework — single flow, consents table, scan upload + preview

**Files:**
- Modify: `backend/clinical/serializers.py` (ConsentRecord serializer), `backend/clinical/views.py` (Consent viewset)
- Modify: `frontend/src/pages/PreAssessment.jsx` (`ConsentStep` rewritten)
- Test: append to the clinical test file covering consents (grep `ConsentRecord` under `backend/clinical/tests/`)

**Interfaces:**
- Consumes: `ConsentRecord.scan` FileField (already in the model, unused).
- Produces: consent create accepts multipart `scan`; serializer exposes `has_scan` + `scan_filename`; `GET /api/consents/<id>/download/` streams the scan (auth same as consent read).

- [ ] **Step 1: Failing test**

```python
from django.core.files.uploadedfile import SimpleUploadedFile

    def test_consent_scan_upload_and_download(self):
        # authenticate as the psychologist used by this test class
        scan = SimpleUploadedFile("consent.pdf", b"%PDF-1.4 test", content_type="application/pdf")
        r = self.client.post("/api/consents/", {
            "child": self.child.id, "signer_name": "Guardian G",
            "status": "signed", "scan": scan,
        }, format="multipart")
        self.assertEqual(r.status_code, 201)
        self.assertTrue(r.data["has_scan"])
        d = self.client.get(f"/api/consents/{r.data['id']}/download/")
        self.assertEqual(d.status_code, 200)
```

(Adapt `self.child`/auth to the existing consent test class's setUp. Uploaded files land in `media/consents/` — mirror how PsychologicalReport tests override storage/cleanup if they do.)

- [ ] **Step 2: Run to verify failure.**

- [ ] **Step 3: Backend.** Serializer — ensure fields include `"scan"` (write-only), plus:

```python
    has_scan = serializers.SerializerMethodField()
    scan_filename = serializers.SerializerMethodField()

    def get_has_scan(self, obj):
        return bool(obj.scan)

    def get_scan_filename(self, obj):
        return obj.scan.name.rsplit("/", 1)[-1] if obj.scan else ""
    # add "has_scan", "scan_filename" to Meta.fields; keep "scan" write_only:
    # extra_kwargs = {"scan": {"write_only": True, "required": False}}
```

Viewset — add a download action modeled EXACTLY on `PsychologicalReport`'s authenticated download in `backend/clinical/views.py` (find `def download` there and copy its FileResponse + permission pattern):

```python
    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        consent = self.get_object()
        if not consent.scan:
            return Response({"detail": "No scan attached."}, status=404)
        return FileResponse(consent.scan.open("rb"),
                            as_attachment=False,
                            filename=consent.scan.name.rsplit("/", 1)[-1])
```

(`as_attachment=False` so the browser/blob can render it inline for preview.)

- [ ] **Step 4: Frontend — rewrite `ConsentStep`** in `PreAssessment.jsx` (replace the whole function):

```jsx
function ConsentStep({ child, consents, templates, onLinked, onRefresh, setError }) {
  const toast = useToast();
  const [form, setForm] = useState({ template: '', signer_name: '', signer_relationship: '', status: 'signed', fileObj: null });
  const [preview, setPreview] = useState(null); // { url, type, title }
  const [busy, setBusy] = useState(false);
  const tpl = templates.find((t) => String(t.id) === String(form.template));

  const recordNew = async () => {
    setError('');
    if (!form.signer_name.trim()) { setError('Enter the signer’s name.'); return; }
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append('child', child.id);
      if (form.template) fd.append('template', form.template);
      fd.append('signer_name', form.signer_name);
      fd.append('signer_relationship', form.signer_relationship);
      fd.append('status', form.status);
      if (form.fileObj) fd.append('scan', form.fileObj);
      const { data } = await api.post('/consents/', fd, { headers: { 'Content-Type': 'multipart/form-data' } });
      await onRefresh();
      if (data.status === 'signed') onLinked(data.id);
      else setError('Consent recorded but not signed — a signed consent is required to complete the pre-assessment.');
    } catch (err) {
      setError(JSON.stringify(err.response?.data || 'Could not record consent.'));
    } finally { setBusy(false); }
  };

  const openPreview = async (c) => {
    try {
      const res = await api.get(`/consents/${c.id}/download/`, { responseType: 'blob' });
      setPreview({ url: URL.createObjectURL(res.data), type: res.data.type, title: c.scan_filename || c.signer_name });
    } catch { toast.error('Could not load the file.'); }
  };
  const closePreview = () => { if (preview) URL.revokeObjectURL(preview.url); setPreview(null); };

  const th = { textAlign: 'left', padding: '9px 12px', fontSize: 10.5, fontWeight: 800, letterSpacing: '0.05em', textTransform: 'uppercase', color: 'var(--text-muted)', whiteSpace: 'nowrap' };
  const td = { padding: '9px 12px', fontSize: 12.5, color: 'var(--text-body)' };

  return (
    <Card eyebrow="Step 2" title={`Consent — ${child.fullname}`} padding="22px">
      <p style={{ fontSize: 13, color: 'var(--text-muted)', margin: '0 0 14px' }}>
        The agency&apos;s consent document is embedded below — read it with the guardian, record the signed paper consent, and attach a scan if available.
      </p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <FormField label="Consent form template" hint="Your agency-authored consent form.">
          <Select value={form.template} onChange={(e) => setForm({ ...form, template: e.target.value })}>
            <option value="">— None / generic —</option>
            {templates.map((t) => <option key={t.id} value={t.id}>{t.title} (v{t.version})</option>)}
          </Select>
        </FormField>
        {tpl && (
          <div style={{ marginBottom: 4 }}>
            <FormBody body={tpl.body} />
            <Button variant="ghost" onClick={() => printBlankForm(tpl)} iconLeft={<Icon name="printer" size={15} />}>Print blank form</Button>
          </div>
        )}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <FormField label="Signer name" required><Input value={form.signer_name} onChange={(e) => setForm({ ...form, signer_name: e.target.value })} /></FormField>
          <FormField label="Relationship to child"><Input value={form.signer_relationship} onChange={(e) => setForm({ ...form, signer_relationship: e.target.value })} placeholder="e.g. Foster mother" /></FormField>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <FormField label="Status" required>
            <Select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}>
              <option value="signed">Signed</option>
              <option value="pending">Pending</option>
              <option value="declined">Declined</option>
            </Select>
          </FormField>
          <FormField label="Scanned signed form" hint="Optional — PDF or photo of the signed paper.">
            <input type="file" accept=".pdf,.jpg,.jpeg,.png" onChange={(e) => setForm({ ...form, fileObj: e.target.files?.[0] || null })} style={{ fontSize: 13, fontFamily: 'var(--font-sans)' }} />
          </FormField>
        </div>
        <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
          <Button variant="primary" onClick={recordNew} disabled={busy} iconLeft={<Icon name="save" size={16} />}>Record consent & continue</Button>
        </div>
      </div>

      {/* All consents on file — tabular, at the bottom (adviser #11) */}
      <div style={{ marginTop: 20, paddingTop: 14, borderTop: '1px solid var(--border)' }}>
        <div className="racco-eyebrow" style={{ fontSize: 10, marginBottom: 8 }}>Consents on file ({consents.length})</div>
        {consents.length === 0 ? (
          <div style={{ fontSize: 12.5, color: 'var(--text-muted)' }}>No consents recorded for {child.fullname} yet.</div>
        ) : (
          <div className="racco-scroll" style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', minWidth: 640, borderCollapse: 'collapse' }}>
              <thead><tr style={{ background: 'var(--ink-50)', borderBottom: '1px solid var(--border)' }}>
                {['Signer', 'Relationship', 'Template', 'Date', 'Status', 'File', ''].map((h, i) => <th key={i} style={th}>{h}</th>)}
              </tr></thead>
              <tbody>
                {consents.map((c) => (
                  <tr key={c.id} style={{ borderBottom: '1px solid var(--ink-100)' }}>
                    <td style={{ ...td, fontWeight: 700, color: 'var(--text-strong)' }}>{c.signer_name || '—'}</td>
                    <td style={td}>{c.signer_relationship || '—'}</td>
                    <td style={td}>{c.template_title || '—'}</td>
                    <td style={td}>{c.date}</td>
                    <td style={td}><Badge tone={c.status === 'signed' ? 'success' : c.status === 'declined' ? 'amber' : 'neutral'} size="sm" dot>{c.status}</Badge></td>
                    <td style={td}>
                      {c.has_scan
                        ? <Button variant="ghost" onClick={() => openPreview(c)} iconLeft={<Icon name="eye" size={14} />}>Preview</Button>
                        : <span style={{ color: 'var(--text-faint)' }}>—</span>}
                    </td>
                    <td style={{ ...td, textAlign: 'right' }}>
                      {c.status === 'signed' && (
                        <Button variant="secondary" onClick={() => onLinked(c.id)} iconLeft={<Icon name="check" size={14} />}>Use this consent</Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Scan preview modal (adviser #12) */}
      {preview && (
        <div onClick={closePreview} style={{ position: 'fixed', inset: 0, background: 'rgba(14,19,29,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 90 }}>
          <div onClick={(e) => e.stopPropagation()} style={{ width: 720, maxWidth: '94%', height: '86vh', background: 'var(--surface)', borderRadius: 'var(--radius-xl)', boxShadow: 'var(--shadow-xl)', display: 'flex', flexDirection: 'column' }}>
            <div style={{ padding: '14px 18px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 15, color: 'var(--text-strong)' }}>Consent scan — {preview.title}</span>
              <button onClick={closePreview} aria-label="Close preview" style={iconBtn('var(--text-muted)')}><Icon name="x" size={16} /></button>
            </div>
            <div style={{ flex: 1, minHeight: 0, background: 'var(--ink-50)' }}>
              {preview.type.startsWith('image/')
                ? <img src={preview.url} alt="Consent scan" style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
                : <iframe title="Consent scan" src={preview.url} style={{ width: '100%', height: '100%', border: 'none' }} />}
            </div>
          </div>
        </div>
      )}
    </Card>
  );
}
```

Imports needed at the top of PreAssessment.jsx: `iconBtn` from `'../ui'` and `useToast` is already imported (the step uses the page-level `toast` today — pass it in or call `useToast()` inside the component as shown). Check `ConsentRecordSerializer` exposes `template_title` (the old UI used it — it does).

- [ ] **Step 5:** Backend suite green; build; browser: consent step shows the embedded document, no On-file/Record-new toggle, consents table at the bottom with Preview opening the scan inline (test with a photo AND a PDF), "Use this consent" advances the wizard.

- [ ] **Step 6: Commit** — `feat(consent): unified consent step, on-file table, scan upload with in-app preview`

---

### Task 18: Assignment-time availability picker in the child record form

**Why:** When staff add (or reassign) a child, they must see each psychologist's availability BEFORE choosing who to assign — pick someone who actually has open hours, not just the smallest caseload.

**Files:**
- Modify: `frontend/src/pages/Children.jsx`

**Interfaces:**
- Consumes: existing `GET /api/availability/` (staff/admin already receive ALL psychologists' active blocks — verified: `AvailabilityBlockViewSet` is `IsAuthenticated` with no role filter) and existing `GET /api/psychologists/` (`{id, name, caseload}`). NO backend changes.

- [ ] **Step 1: Load blocks.** In `Children()` add `const [blocks, setBlocks] = useState([]);` and in `load()` (only when `canManage`):

```jsx
if (canManage) api.get('/availability/').then((r) => setBlocks(r.data)).catch(() => {});
```

Pass `blocks` into `<ChildForm ... blocks={blocks} />`.

- [ ] **Step 2: Availability comparison panel.** In `ChildForm` (which receives `blocks`), add helpers at the top of the function:

```jsx
const DAY_ABBR = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']; // matches AvailabilityBlock 0=Monday
const availFor = (pid) => blocks.filter((b) => String(b.psychologist) === String(pid));
const blockLabel = (b) => `${b.date || DAY_ABBR[b.weekday]} ${String(b.start_time).slice(0, 5)}–${String(b.end_time).slice(0, 5)}`;
```

Directly BELOW the "Assign Psychologist" `<Select>` (Task 3 already hides that select for psychologists — this panel is likewise admin/staff-only by construction), render a clickable comparison list; clicking a row selects that psychologist in the form:

```jsx
{psychologists.length > 0 && (
  <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: 12, background: 'var(--ink-50)', display: 'flex', flexDirection: 'column', gap: 8 }}>
    <div className="racco-eyebrow" style={{ fontSize: 10 }}>Availability — check before you assign</div>
    {psychologists.map((p) => {
      const av = availFor(p.id);
      const on = String(form.psychologist) === String(p.id);
      return (
        <button type="button" key={p.id}
          onClick={() => setForm({ ...form, psychologist: String(p.id) })}
          aria-pressed={on}
          style={{ textAlign: 'left', padding: '9px 11px', borderRadius: 'var(--radius-md)', cursor: 'pointer', fontFamily: 'var(--font-sans)', border: `1px solid ${on ? 'var(--blue-500)' : 'var(--border)'}`, background: on ? 'var(--blue-50)' : 'var(--surface)', transition: 'var(--transition-base)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, marginBottom: 5 }}>
            <span style={{ fontWeight: 700, fontSize: 13, color: on ? 'var(--blue-700)' : 'var(--text-strong)' }}>{p.name}</span>
            <Badge tone={p.caseload >= 5 ? 'amber' : 'neutral'} size="sm">{p.caseload} case{p.caseload === 1 ? '' : 's'}</Badge>
          </div>
          {av.length === 0 ? (
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 11.5, color: 'var(--amber-600, #b45309)', fontWeight: 600 }}>
              <Icon name="alert-triangle" size={12} /> No availability set — sessions can’t be booked yet
            </span>
          ) : (
            <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
              {av.map((b) => <Badge key={b.id} tone="success" size="sm">{blockLabel(b)}</Badge>)}
            </div>
          )}
        </button>
      );
    })}
  </div>
)}
```

(If the design tokens lack `--amber-600`, use `var(--amber-500)`. The select and the panel stay in sync because both read/write `form.psychologist`.)

- [ ] **Step 3: Verify** — `npm run build`; browser as staff: Add Record → the panel lists every psychologist with weekly/dated availability chips and caseload; clicking a row selects them in the dropdown; a psychologist with no blocks shows the amber warning; same panel appears when reassigning via Edit.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/Children.jsx
git commit -m "feat(records): psychologist availability panel at assignment time"
```

---

### Task 19: Records module — centered full-screen case modals (replace side drawers)

**Why:** The 400–420px right-side drawers cram a whole case file into one narrow scrolling column. A large centered modal reads like an actual case record: identity at the top, details in two columns, actions always visible.

**Files:**
- Modify: `frontend/src/pages/Children.jsx` (`ChildDrawer` + `ChildForm` containers/layout — keep both function names and all internal content blocks)
- Modify: `frontend/src/index.css` (one responsive utility class)

**Interfaces:**
- Consumes: nothing new. All other Children.jsx tasks (T3 presence strip, T5 termination history, T6 recommendation group, T12 name grid, T15 next-sessions, T18 availability panel) drop into the regions named below unchanged.

- [ ] **Step 1: Responsive grid utility.** Append to `frontend/src/index.css`:

```css
/* Centered case-modal two-column body; collapses on small screens. */
.racco-case-grid { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 16px 24px; align-items: start; }
@media (max-width: 760px) { .racco-case-grid { grid-template-columns: 1fr; } }
```

- [ ] **Step 2: `ChildDrawer` becomes a centered case modal.** Replace its outer two wrappers (the `position:fixed` overlay + the `width:400` panel) with:

```jsx
<div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(14,19,29,0.45)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20, zIndex: 60, animation: 'racco-fade-in var(--dur-base) var(--ease-out)' }}>
  <div role="dialog" aria-modal="true" aria-label={`Case record for ${child.fullname}`} onClick={(e) => e.stopPropagation()}
    style={{ width: 'min(980px, 96vw)', height: 'min(86vh, 820px)', background: 'var(--surface)', borderRadius: 'var(--radius-xl)', boxShadow: 'var(--shadow-xl)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
```

Inside, keep the existing header bar (avatar + name + ref + close button) and add the status chip + case type + age inline in the header (they currently sit in the body). Body becomes:

```jsx
<div className="racco-scroll" style={{ flex: 1, minHeight: 0, overflowY: 'auto', padding: '20px 24px' }}>
  <div className="racco-case-grid">
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* LEFT column: the existing `fields` rows (identity/case/address facts) */}
    </div>
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* RIGHT column, in this order: termination history (T5) · Recommendation group (T6) ·
          next possible sessions (T15) · instruments used · referral reason · medical notes */}
    </div>
  </div>
</div>
```

Footer (Edit / Terminate / Reopen buttons) stays a fixed bar at the bottom, right-aligned buttons (drop `fullWidth`). The T3 presence strip renders directly under the header, full width.

- [ ] **Step 3: `ChildForm` becomes a centered intake modal.** Same overlay/container as Step 2 (the inner element stays a `<form>`). Body uses grouped two-column sections — move every existing field into these groups without changing any field code:

```jsx
<div className="racco-scroll" style={{ flex: 1, minHeight: 0, overflowY: 'auto', padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: 18 }}>
  {error && <Alert .../>}
  {/* conflict alert (T3) full width */}
  <section>
    <div className="racco-eyebrow" style={{ fontSize: 10, marginBottom: 10 }}>Identity</div>
    <div className="racco-case-grid">{/* name grid (T12) spans; birth date; gender */}</div>
  </section>
  <section>
    <div className="racco-eyebrow" style={{ fontSize: 10, marginBottom: 10 }}>Address</div>
    <div className="racco-case-grid">{/* province / municipality / barangay */}</div>
  </section>
  <section>
    <div className="racco-eyebrow" style={{ fontSize: 10, marginBottom: 10 }}>Case</div>
    <div className="racco-case-grid">{/* case type / case category / previous custodian */}</div>
  </section>
  <section>
    <div className="racco-eyebrow" style={{ fontSize: 10, marginBottom: 10 }}>Recommendation</div>
    <div className="racco-case-grid">{/* referral source / educational placement / place of recovery;
        referral reason, medical notes, recommendation textareas get style={{ gridColumn: '1 / -1' }} */}</div>
  </section>
  <section>
    <div className="racco-eyebrow" style={{ fontSize: 10, marginBottom: 10 }}>Assignment</div>
    {/* psychologist select + T18 availability panel + T3 psych read-only variant + carry-history box — full width */}
  </section>
</div>
```

Footer: `<div style={{ padding: '14px 24px', borderTop: '1px solid var(--border)', display: 'flex', justifyContent: 'flex-end', gap: 10 }}>` with a Cancel `Button variant="secondary"` (calls `onClose`) and the Save button (drop `fullWidth`).

- [ ] **Step 4: Remove the slide-left animation references** (`racco-slide-left`) from both components — the centered modal uses the fade only (or an existing pop/scale keyframe if one exists in index.css; check first, do not invent one inline).

- [ ] **Step 5: Verify** — build; browser at desktop AND ~700px width: open a record (two columns → one column collapse), open Add Record, tab through fields, Escape and click-outside still close, terminate/reopen/edit buttons reachable without scrolling the footer.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/Children.jsx frontend/src/index.css
git commit -m "feat(records): centered full-screen case modals replace side drawers"
```

---

### Task 20: Duplicate / returning-child detection at intake

**Files:**
- Modify: `backend/children/views.py` (ChildViewSet), `frontend/src/pages/Children.jsx`
- Test: append to `backend/children/tests/test_child_collab.py`

**Interfaces:**
- Consumes: T12 name parts, T4 reopen, T19 modal Identity section.
- Produces: `GET /api/children/check-duplicate/?first_name=&last_name=&birth_date=` (Admin/Staff only) → `{"matches": [{id, fullname, status, birth_date, psychologist_name}]}` searching ALL records including archived, max 5.

- [ ] **Step 1: Failing tests** — append:

```python
class DuplicateCheckTests(APITestCase):
    def setUp(self):
        self.staff = make_user("dc@t.ph", Role.STAFF)
        self.psych = make_user("dp@t.ph", Role.PSYCHOLOGIST)
        self.archived = Child.objects.create(
            fullname="Mika R. Santos", first_name="Mika", last_name="Santos",
            birth_date="2016-01-10", status=Child.INACTIVE)

    def test_finds_archived_record(self):
        self.client.force_authenticate(self.staff)
        r = self.client.get("/api/children/check-duplicate/?first_name=mika&last_name=santos")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data["matches"]), 1)
        self.assertEqual(r.data["matches"][0]["status"], "inactive")

    def test_birth_date_plus_last_name_matches(self):
        self.client.force_authenticate(self.staff)
        r = self.client.get("/api/children/check-duplicate/?last_name=santos&birth_date=2016-01-10")
        self.assertEqual(len(r.data["matches"]), 1)

    def test_psychologist_forbidden(self):
        self.client.force_authenticate(self.psych)
        r = self.client.get("/api/children/check-duplicate/?first_name=mika&last_name=santos")
        self.assertEqual(r.status_code, 403)
```

- [ ] **Step 2: Run to verify failure** (404 — no route).

- [ ] **Step 3: Backend.** In `ChildViewSet`:

```python
from django.db.models import Q as _Q  # if Q not already imported in this module

    @action(detail=False, methods=["get"], url_path="check-duplicate")
    def check_duplicate(self, request):
        """Intake helper: does a record (active OR archived) already exist for
        this child? Staff/Admin only — powers the 'reopen instead of
        duplicating' warning on the Add Record form."""
        role = getattr(getattr(request.user, "role", None), "role_name", None)
        if role not in (Role.ADMINISTRATOR, Role.STAFF):
            return Response({"detail": "Staff or administrators only."},
                            status=status.HTTP_403_FORBIDDEN)
        first = (request.query_params.get("first_name") or "").strip()
        last = (request.query_params.get("last_name") or "").strip()
        birth = (request.query_params.get("birth_date") or "").strip()
        if not last:
            return Response({"matches": []})
        q = _Q(last_name__iexact=last) if not first else \
            _Q(last_name__iexact=last, first_name__iexact=first)
        if birth and not first:
            q &= _Q(birth_date=birth)
        elif not first:
            return Response({"matches": []})  # last name alone is too broad
        matches = Child.objects.filter(q).order_by("-updated_at")[:5]
        return Response({"matches": [{
            "id": c.id, "fullname": c.fullname, "status": c.status,
            "birth_date": c.birth_date,
            "psychologist_name": getattr(c.assigned_psychologist, "fullname", None),
        } for c in matches]})
```

- [ ] **Step 4: Frontend.** In `ChildForm` (create mode only), debounce-check while typing — add near the top:

```jsx
const [dupes, setDupes] = useState([]);
useEffect(() => {
  if (form.id || !form.last_name?.trim() || !(form.first_name?.trim() || form.birth_date)) { setDupes([]); return; }
  const t = setTimeout(() => {
    const p = new URLSearchParams({ first_name: form.first_name || '', last_name: form.last_name, birth_date: form.birth_date || '' });
    api.get(`/children/check-duplicate/?${p}`).then((r) => setDupes(r.data.matches || [])).catch(() => setDupes([]));
  }, 600);
  return () => clearTimeout(t);
}, [form.first_name, form.last_name, form.birth_date, form.id]);
```

Render inside the Identity section, under the name grid, when `dupes.length > 0` (needs props: `isAdmin`, `onReopen(match)`, `onOpenExisting(match)` passed from `Children()`):

```jsx
<Alert tone="warning" icon={<Icon name="alert-triangle" size={18} />} title="A similar record already exists" style={{ gridColumn: '1 / -1' }}>
  <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 6 }}>
    {dupes.map((m) => (
      <div key={m.id} style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
        <strong style={{ fontSize: 13 }}>{m.fullname}</strong>
        <Badge tone={m.status === 'inactive' ? 'neutral' : 'success'} size="sm" dot>
          {m.status === 'inactive' ? 'Archived (Terminated)' : 'Active'}
        </Badge>
        {m.birth_date && <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>b. {m.birth_date}</span>}
        {m.status === 'inactive'
          ? (isAdmin
              ? <Button variant="secondary" onClick={() => onReopen(m)} iconLeft={<Icon name="rotate-ccw" size={14} />}>Reopen this record instead</Button>
              : <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Ask an administrator to reopen this archived record instead of creating a new one.</span>)
          : <Button variant="secondary" onClick={() => onOpenExisting(m)} iconLeft={<Icon name="eye" size={14} />}>Open existing record</Button>}
      </div>
    ))}
  </div>
</Alert>
```

In `Children()`: `onReopen = async (m) => { await reopen({ id: m.id, fullname: m.fullname }); setForm(null); }` (reuse T5's `reopen`); `onOpenExisting = (m) => { setForm(null); const c = rows.find((r) => r.id === m.id); if (c) setSel(c); }`.

- [ ] **Step 5:** Backend suite green; build; browser as staff: typing an archived child's name in Add Record shows the warning with the admin-hint; as admin the Reopen button reactivates the old record and closes the form.

- [ ] **Step 6: Commit** — `feat(records): duplicate/returning-child detection with reopen shortcut at intake`

---

### Task 21: One-click first booking from the record

**Files:**
- Modify: `frontend/src/pages/Children.jsx` (`ChildDrawer` next-sessions block)

**Interfaces:**
- Consumes: T15's next-slots fetch in `ChildDrawer` and the existing `POST /api/appointments/` (capacity-validated server-side). Runs AFTER T15.

- [ ] **Step 1:** In `ChildDrawer`, upgrade the T15 "Next possible sessions" badges into buttons with an inline confirm. Add state `const [pendingSlot, setPendingSlot] = useState(null); const [purpose, setPurpose] = useState(null); const [bookingBusy, setBookingBusy] = useState(false);` and default purpose from the child: `const defaultPurpose = child.pre_assessment_status === 'Answered' ? 'session' : 'pre_assessment';`

Replace the slot badges with:

```jsx
<div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
  {slots.slots.map((s, i) => (
    <button key={i} type="button" onClick={() => { setPendingSlot(s); setPurpose(defaultPurpose); }}
      style={{ padding: '5px 11px', borderRadius: 'var(--radius-pill)', border: '1px solid var(--success-100)', background: 'var(--success-50)', color: 'var(--success-600)', fontFamily: 'var(--font-sans)', fontWeight: 700, fontSize: 11.5, cursor: 'pointer' }}>
      {s.weekday.slice(0, 3)} {s.date.slice(5)} · {s.start}–{s.end}
    </button>
  ))}
</div>
{pendingSlot && (
  <div style={{ marginTop: 10, padding: '11px 13px', borderRadius: 'var(--radius-md)', background: 'var(--blue-50)', border: '1px solid var(--blue-200)', display: 'flex', flexDirection: 'column', gap: 9 }}>
    <span style={{ fontSize: 12.5, color: 'var(--text-strong)', fontWeight: 600 }}>
      Book {child.fullname} with {slots.psychologist} — {pendingSlot.weekday} {pendingSlot.date} at {pendingSlot.start}?
    </span>
    <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
      <Select value={purpose} onChange={(e) => setPurpose(e.target.value)} style={{ maxWidth: 180 }}>
        <option value="pre_assessment">Pre-Assessment</option>
        <option value="session">Session</option>
        <option value="follow_up">Follow-up</option>
      </Select>
      <Button variant="primary" disabled={bookingBusy} onClick={bookSlot} iconLeft={<Icon name="calendar" size={15} />}>Book</Button>
      <Button variant="ghost" onClick={() => setPendingSlot(null)}>Cancel</Button>
    </div>
  </div>
)}
```

With the handler (needs `toast` — `useToast()` inside `ChildDrawer` — and the slots re-fetch from T15 extracted into a `loadSlots()` it can call again):

```jsx
const bookSlot = async () => {
  setBookingBusy(true);
  try {
    await api.post('/appointments/', {
      child: child.id, psychologist: child.psychologist,
      start: `${pendingSlot.date}T${pendingSlot.start}:00`,
      duration_minutes: 60, purpose, notes: '',
    });
    toast.success(`Booked — ${pendingSlot.weekday} ${pendingSlot.date} at ${pendingSlot.start}`);
    setPendingSlot(null);
    loadSlots();
  } catch (err) {
    const d = err.response?.data;
    toast.error(d?.start || d?.psychologist || d?.detail || 'Could not book this slot.');
  } finally { setBookingBusy(false); }
};
```

- [ ] **Step 2:** Build; browser: assign a psychologist with availability, open the child's record, click a slot chip → confirm → appointment appears on `/schedule` and the slot's remaining count drops on re-open; booking a full slot surfaces the server's capacity error as a toast.

- [ ] **Step 3: Commit** — `feat(records): one-click first booking from the child's next-session slots`

---

### Task 22: Intake draft autosave (never lose a half-typed record)

**Files:**
- Modify: `frontend/src/pages/Children.jsx`, `frontend/src/context/AuthContext.jsx` (logout cleanup)

**Interfaces:** Create-mode only (edits live server-side). Draft key: `nacc-child-draft:<userId>` in localStorage — the on-prem workstation only; cleared on save, discard, and logout.

- [ ] **Step 1:** In `Children()`:

```jsx
const draftKey = `nacc-child-draft:${user?.id ?? 'anon'}`;

const openCreate = () => {
  setError('');
  let draft = null;
  try { draft = JSON.parse(localStorage.getItem(draftKey) || 'null'); } catch { /* corrupt draft */ }
  const meaningful = draft && Object.entries(draft).some(([k, v]) => k !== 'assignee_sees_history' && v);
  setForm({ ...EMPTY, _draft: meaningful ? draft : null });
};
```

In `save()`, also `delete payload._draft;` and on success `localStorage.removeItem(draftKey);`. Pass `draftKey` to `<ChildForm draftKey={draftKey} ... />`.

- [ ] **Step 2:** In `ChildForm`, autosave (debounced) + restore banner:

```jsx
useEffect(() => {
  if (form.id) return; // edits are server-backed; drafts are create-only
  const t = setTimeout(() => {
    const { _draft, _conflict, ...data } = form;
    if (Object.entries(data).some(([k, v]) => k !== 'assignee_sees_history' && v)) {
      try { localStorage.setItem(draftKey, JSON.stringify(data)); } catch { /* storage full */ }
    }
  }, 500);
  return () => clearTimeout(t);
}, [form, draftKey]);
```

Banner at the top of the modal body when `form._draft`:

```jsx
{form._draft && (
  <Alert tone="info" icon={<Icon name="history" size={18} />} title="Unsaved draft found" style={{ marginBottom: 4 }}>
    You started a record earlier that wasn’t saved. Continue where you left off?
    <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
      <Button variant="secondary" onClick={() => setForm({ ...EMPTY, ...form._draft, _draft: null })} iconLeft={<Icon name="rotate-ccw" size={14} />}>Restore draft</Button>
      <Button variant="ghost" onClick={() => { localStorage.removeItem(draftKey); setForm((f) => ({ ...f, _draft: null })); }}>Discard</Button>
    </div>
  </Alert>
)}
```

(`EMPTY` must be importable inside `ChildForm` — it's module-scope in Children.jsx already. If the `history` icon name doesn't exist in the Icon set, use `rotate-ccw`.)

- [ ] **Step 3: Logout cleanup.** In `frontend/src/context/AuthContext.jsx`, find the `logout` function and add before/after token clearing:

```jsx
Object.keys(localStorage)
  .filter((k) => k.startsWith('nacc-child-draft:'))
  .forEach((k) => localStorage.removeItem(k));
```

- [ ] **Step 4:** Build; browser: type half a record, close the modal, reopen Add Record → banner offers the draft; Restore brings every field back; saving clears it (reopen shows no banner); logging out clears it.

- [ ] **Step 5: Commit** — `feat(records): intake draft autosave with restore banner`

---

## Self-Review (done at plan time)

- **Spec coverage (first batch):** psychologist edits assigned child → T1/T3; multidisciplinary "Google-Docs-like" collab → T2/T3 (scoped decision #1); calendar off sidebar + dashboard mini widget + click-to-fullscreen → T10; bento no-scroll dashboard + per-module scrolling → T10; grouped result entries per child → T9; terminated records archived for admin + reuse when a child returns → T4/T5; Previous Custodian / Address / Recommendation → T6; instrument module inside pre-assessment step 4 → T7/T8; new instrument title lists (children + PAP) → T7; ethical-consideration check → answered in chat + hardening T11.
- **Spec coverage (adviser suggestions 1–13):** #1 name split → T12; #2 age 5–17 + required `*` → T13; #3 specific labels (Educational Placement, Place of Recovery) → T13; #4 LIFO records → T14; #5 weekday checkboxes → T15 step 4; #6 assigned child's next counseling slots → T15 steps 3/5/6; #7 staff sees psychologist availability → T15 step 6 (already works, verify); #8 clickable notifications → T16; #9 embedded readable consent → T17 (document text already renders; kept front-and-center); #10 remove Record New / On file toggle → T17; #11 consents in a bottom table → T17; #12 consent file preview → T17; #13 status function / add event → T15 step 5 (status actions already exist; slot-click booking added).
- **Spec coverage (follow-up requests):** availability visible BEFORE assigning a psychologist on the child record form → T18 (frontend-only; staff already have read access to all availability blocks); Records detail/edit as centered full-screen modals instead of side drawers → T19 (decision #14); user-approved reliability trio → T20 duplicate/returning-child detection, T21 one-click first booking, T22 intake draft autosave (decision #15).
- **Known ambiguities intentionally flagged:** decisions #1–#13 at the top; confirm with the user before executing if any look wrong.
- **Type consistency:** `expected_updated_at` (write-only, ISO string) and `updated_at` (read-only) used consistently across T1–T3; `terminations` list shape identical in T4 backend and T5 frontend; `audience` values `child|adoptive_parent|both` identical in T7 model, seed, and T8 filters; `InstrumentFormDrawer` props match both call sites; `next-slots` response shape identical in T15 backend, Schedule hints, and Children drawer; `has_scan`/`scan_filename`/`download` consistent between T17 backend and ConsentStep; T12's name-lock `validate()` REPLACES T1's fullname-only check (implement T1's version first, extend it in T12).
- **Execution order:** T1→T2→T3 sequential; T4→T5 sequential; T7→T8 sequential; T12→T13 sequential (validation builds on name parts). `Children.jsx` is touched by T3, T5, T6, T12, T13, T14, T15-step-6 — run those serially, never in parallel subagents. `PreAssessment.jsx` is touched by T8 and T17 — serialize. `Schedule.jsx`/`Topbar.jsx`/`Dashboard.jsx` overlap across T10, T15, T16 — serialize T10→T15→T16. Do T10 last among dashboard tasks if the in-flight Sidebar change hasn't landed yet. T18–T22 also touch `Children.jsx` — include them in that serial chain; run T19 (layout) right after T3 so the later Children tasks land inside the new modal regions. T20 needs T12 (name parts) and T4 (reopen); T21 needs T15 (next-slots in the drawer); T22 is independent. Suggested overall order: T1, T2, T3, T19, T4, T5, T6, T12, T13, T14, T18, T20, T22, T7, T8, T17, T9, T10, T15, T21, T16, T11.
