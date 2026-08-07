# Progress Monitoring (Phase 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enrich each child's record with a **progress log** (dated session notes), **treatment goals** (ongoing/met), and a real **next-session date**, writable by the assigned Psychologist or an Administrator (Staff read-only), surfaced in the per-child report and (for next session) the Progress Monitoring overview.

**Architecture:** Two new models in the `children` app (`ProgressNote`, `Goal`) exposed through role-scoped DRF `ModelViewSet`s guarded by a new `ProgressRecordAccess` permission; a `next_session` `DateField` added to `Assessment` with a dedicated `schedule` action. The React per-child report (`ChildProgressReport.jsx`) gains three sections; the monitoring endpoint + page gain a next-session column.

**Tech Stack:** Django REST Framework, React + Vite. Backend tests via Django `APITestCase`; frontend verified via ESLint + the preview dev server (no JS test runner in this repo).

---

## Spec reference & decisions

Design outline: [2026-06-30-progress-monitoring-design.md](../specs/2026-06-30-progress-monitoring-design.md) §5 (Phase 2). Decisions locked for this plan (flag any you want changed before execution):

1. **Model location:** `ProgressNote` and `Goal` live in the existing `children` app (they FK to `Child`; no new app to register).
2. **Next session storage:** a nullable `next_session` `DateField` on `Assessment`. The child's "next session" = the latest assessment's `next_session`. (Matches the field `Report.jsx` already reads.) Children with no assessments have no scheduled session.
3. **Write access:** create/update/delete allowed for an **Administrator** or the child's **assigned Psychologist**; **Staff read-only**. Enforced by `ProgressRecordAccess` (`has_permission` + `has_object_permission`) plus an explicit child-ownership check on create.
4. **Frontend write gate:** since `ChildReportView` only returns a child to its assigned psychologist (404 otherwise), the report page can treat `canWrite = ['Administrator','Psychologist'].includes(user.role_name)` — a viewing psychologist is necessarily the assignee.
5. **Records are editable/deletable** (not append-only). Goals toggle between `ongoing`/`met`.

Sub-features are independent; ship in order A → B → C. Each is a backend task (TDD) then a frontend task.

## File Structure

- **Modify** `backend/children/models.py` — add `ProgressNote`, `Goal`.
- **Modify** `backend/accounts/permissions.py` — add `ProgressRecordAccess`.
- **Modify** `backend/children/serializers.py` — add `ProgressNoteSerializer`, `GoalSerializer`.
- **Modify** `backend/children/views.py` — add `ProgressNoteViewSet`, `GoalViewSet`.
- **Modify** `backend/children/urls.py` — register both routes.
- **Create** `backend/children/tests.py` — model/API tests (create if absent, else append).
- **Modify** `backend/assessments/models.py` — add `Assessment.next_session`.
- **Modify** `backend/assessments/serializers.py` — expose `next_session`; allow editing.
- **Modify** `backend/assessments/views.py` — add `schedule` action; add `next_session` to `MonitoringListView`.
- **Modify** `backend/assessments/tests/test_reports.py` — next-session tests.
- **Modify** `frontend/src/pages/ChildProgressReport.jsx` — progress-log, goals, next-session sections.
- **Modify** `frontend/src/pages/Monitoring.jsx` — "Next session" column.

> Backend commands run from `backend/`; venv Python is `venv/Scripts/python.exe`.

---

## Task 1: Backend — Progress log (`ProgressNote`) API (TDD)

**Files:** Modify `children/models.py`, `accounts/permissions.py`, `children/serializers.py`, `children/views.py`, `children/urls.py`; create/append `children/tests.py`.

- [ ] **Step 1: Write the failing tests**

Create `backend/children/tests.py` (or append if it exists):

```python
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from accounts.models import Role
from children.models import Child, ProgressNote

User = get_user_model()


class ProgressNoteApiTest(APITestCase):
    def setUp(self):
        self.admin_role = Role.objects.create(role_name=Role.ADMINISTRATOR)
        self.psy_role = Role.objects.create(role_name=Role.PSYCHOLOGIST)
        self.staff_role = Role.objects.create(role_name=Role.STAFF)
        self.admin = User.objects.create_user(email="a@racco1.gov.ph", username="a", password="pass1234", role=self.admin_role)
        self.psy = User.objects.create_user(email="p@racco1.gov.ph", username="p", password="pass1234", role=self.psy_role)
        self.other = User.objects.create_user(email="o@racco1.gov.ph", username="o", password="pass1234", role=self.psy_role)
        self.staff = User.objects.create_user(email="s@racco1.gov.ph", username="s", password="pass1234", role=self.staff_role)
        self.mine = Child.objects.create(fullname="Ana", assigned_psychologist=self.psy)
        self.theirs = Child.objects.create(fullname="Ben", assigned_psychologist=self.other)

    def _auth(self, email):
        token = self.client.post("/api/auth/login/", {"email": email, "password": "pass1234"}).data["access"]
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + token)

    def test_assigned_psychologist_adds_note(self):
        self._auth("p@racco1.gov.ph")
        resp = self.client.post("/api/progress-notes/", {"child": self.mine.id, "text": "Good session."}, format="json")
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data["author_name"], self.psy.fullname)
        self.assertEqual(ProgressNote.objects.count(), 1)

    def test_psychologist_cannot_add_to_unassigned_child(self):
        self._auth("p@racco1.gov.ph")
        resp = self.client.post("/api/progress-notes/", {"child": self.theirs.id, "text": "x"}, format="json")
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(ProgressNote.objects.count(), 0)

    def test_admin_can_add_note(self):
        self._auth("a@racco1.gov.ph")
        resp = self.client.post("/api/progress-notes/", {"child": self.mine.id, "text": "Admin note."}, format="json")
        self.assertEqual(resp.status_code, 201)

    def test_staff_read_only(self):
        self._auth("s@racco1.gov.ph")
        self.assertEqual(self.client.post("/api/progress-notes/", {"child": self.mine.id, "text": "x"}, format="json").status_code, 403)
        self.assertEqual(self.client.get("/api/progress-notes/").status_code, 200)

    def test_psychologist_list_scoped_and_filtered(self):
        ProgressNote.objects.create(child=self.mine, author=self.psy, text="mine")
        ProgressNote.objects.create(child=self.theirs, author=self.other, text="theirs")
        self._auth("p@racco1.gov.ph")
        resp = self.client.get("/api/progress-notes/")
        self.assertEqual(len(resp.data), 1)  # only their assigned child's note
        resp2 = self.client.get(f"/api/progress-notes/?child={self.mine.id}")
        self.assertEqual(len(resp2.data), 1)

    def test_other_psychologist_cannot_delete(self):
        note = ProgressNote.objects.create(child=self.mine, author=self.psy, text="mine")
        self._auth("o@racco1.gov.ph")
        resp = self.client.delete(f"/api/progress-notes/{note.id}/")
        self.assertIn(resp.status_code, (403, 404))
        self.assertEqual(ProgressNote.objects.count(), 1)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `venv/Scripts/python manage.py test children -v 2`
Expected: FAIL — `ProgressNote` import error / 404s (model + route don't exist).

- [ ] **Step 3: Add the model**

In `backend/children/models.py`, add `from django.utils import timezone` at the top (below `from django.db import models`), then append:

```python
class ProgressNote(models.Model):
    """A dated progress/session note on a child's record (Phase 2 monitoring)."""
    child = models.ForeignKey(Child, on_delete=models.CASCADE, related_name="progress_notes")
    author = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="authored_progress_notes")
    date = models.DateField(default=timezone.localdate)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tbl_progress_note"
        ordering = ["-date", "-id"]
```

- [ ] **Step 4: Add the permission**

In `backend/accounts/permissions.py`, append:

```python
class ProgressRecordAccess(BasePermission):
    """Progress log & goals. Read: admin/staff/psychologist. Write: admin or the
    child's assigned psychologist (Staff read-only). Object-level restricts a
    psychologist to their assigned children's records."""

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        role = _role_name(request)
        if request.method in SAFE_METHODS:
            return role in (Role.ADMINISTRATOR, Role.STAFF, Role.PSYCHOLOGIST)
        return role in (Role.ADMINISTRATOR, Role.PSYCHOLOGIST)

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        role = _role_name(request)
        if role == Role.ADMINISTRATOR:
            return True
        return obj.child.assigned_psychologist_id == request.user.id
```

- [ ] **Step 5: Add the serializer**

In `backend/children/serializers.py`, add `ProgressNote` to the model import (`from children.models import Guardian, Child, ProgressNote`) and append:

```python
class ProgressNoteSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="author.fullname", read_only=True, default=None)

    class Meta:
        model = ProgressNote
        fields = ["id", "child", "author", "author_name", "date", "text", "created_at"]
        read_only_fields = ["author"]
```

- [ ] **Step 6: Add the viewset**

In `backend/children/views.py`, extend the imports:

```python
from rest_framework.exceptions import PermissionDenied
from accounts.permissions import RecordsAccess, ProgressRecordAccess
from children.models import Guardian, Child, ProgressNote
from children.serializers import GuardianSerializer, ChildSerializer, ProgressNoteSerializer
```

Then append:

```python
class ProgressNoteViewSet(viewsets.ModelViewSet):
    """Per-child progress log. Read: admin/staff/psychologist (psychologist scoped to
    assigned children). Write: admin or the child's assigned psychologist."""
    permission_classes = [ProgressRecordAccess]
    pagination_class = None
    serializer_class = ProgressNoteSerializer

    def get_queryset(self):
        qs = ProgressNote.objects.select_related("author", "child").order_by("-date", "-id")
        child_id = self.request.query_params.get("child")
        if child_id:
            qs = qs.filter(child_id=child_id)
        role = getattr(getattr(self.request.user, "role", None), "role_name", None)
        if role == Role.PSYCHOLOGIST:
            qs = qs.filter(child__assigned_psychologist=self.request.user)
        return qs

    def _assert_can_write(self, child):
        role = getattr(getattr(self.request.user, "role", None), "role_name", None)
        if role == Role.ADMINISTRATOR:
            return
        if role == Role.PSYCHOLOGIST and child.assigned_psychologist_id == self.request.user.id:
            return
        raise PermissionDenied("You can only add progress notes for your assigned children.")

    def perform_create(self, serializer):
        self._assert_can_write(serializer.validated_data["child"])
        obj = serializer.save(author=self.request.user)
        log_activity(self.request.user, ActivityLog.CREATED, ActivityLog.RECORD,
                     entity_type="ProgressNote", entity_label=obj.child.fullname,
                     entity_id=obj.id, recipient=obj.child.assigned_psychologist)
```

- [ ] **Step 7: Register the route**

In `backend/children/urls.py`, import `ProgressNoteViewSet` and register it:

```python
from children.views import GuardianViewSet, ChildViewSet, ProgressNoteViewSet
...
router.register("progress-notes", ProgressNoteViewSet, basename="progress-note")
```

- [ ] **Step 8: Make + apply the migration**

Run: `venv/Scripts/python manage.py makemigrations children`
Then: `venv/Scripts/python manage.py migrate`
Expected: a new migration for `ProgressNote` is created and applied.

- [ ] **Step 9: Run the tests to verify they pass**

Run: `venv/Scripts/python manage.py test children -v 2`
Expected: PASS (6 tests OK).

- [ ] **Step 10: Commit**

```bash
git add backend/children/ backend/accounts/permissions.py
git commit -m "feat(monitoring): progress log (ProgressNote) API"
git push origin main
```

---

## Task 2: Frontend — Progress log section in the per-child report

**Files:** Modify `frontend/src/pages/ChildProgressReport.jsx`.

- [ ] **Step 1: Add state, loader, and handlers**

In `ChildProgressReport.jsx`, after the existing `const [edit, setEdit] = useState(null);` line, add:

```jsx
  const canWrite = ['Administrator', 'Psychologist'].includes(user?.role_name);
  const [notes, setNotes] = useState([]);
  const [noteText, setNoteText] = useState('');

  const loadNotes = () => api.get(`/progress-notes/?child=${id}`).then((r) => setNotes(r.data)).catch(() => {});
  useEffect(() => { loadNotes(); /* eslint-disable-next-line */ }, [id]);

  const addNote = async () => {
    if (!noteText.trim()) return;
    try {
      await api.post('/progress-notes/', { child: Number(id), text: noteText.trim() });
      setNoteText(''); loadNotes(); toast.success('Progress note added');
    } catch (err) { toast.error(err.response?.data?.detail || 'Could not add note.'); }
  };
  const deleteNote = async (noteId) => {
    if (!window.confirm('Delete this progress note?')) return;
    try { await api.delete(`/progress-notes/${noteId}/`); loadNotes(); toast.success('Note deleted'); }
    catch (err) { toast.error(err.response?.data?.detail || 'Could not delete.'); }
  };
```

- [ ] **Step 2: Render the Progress log card**

Insert this block immediately **before** the `<Alert disclaimer title="Note." ...>` line near the end of the returned JSX:

```jsx
      <Card eyebrow="Progress log" title="Session notes" padding="20px" style={{ marginTop: 18 }}>
        {canWrite && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: notes.length ? 18 : 0 }} className="racco-no-print">
            <textarea value={noteText} onChange={(e) => setNoteText(e.target.value)} rows={3} placeholder="Add a dated progress note for this child…"
              style={{ width: '100%', resize: 'vertical', padding: '11px 13px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-strong)', fontFamily: 'var(--font-sans)', fontSize: 14, lineHeight: 1.55 }} />
            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <Button variant="primary" onClick={addNote} iconLeft={<Icon name="plus" size={16} />} disabled={!noteText.trim()}>Add note</Button>
            </div>
          </div>
        )}
        {notes.length === 0 ? (
          <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>No progress notes yet.</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {notes.map((n) => (
              <div key={n.id} style={{ borderLeft: '3px solid var(--blue-200)', paddingLeft: 12 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)', fontWeight: 700 }}>{n.date} · {n.author_name || '—'}</div>
                  {canWrite && <button title="Delete note" onClick={() => deleteNote(n.id)} className="racco-no-print" style={iconBtn('var(--red-500)')}><Icon name="trash-2" size={14} /></button>}
                </div>
                <p style={{ fontSize: 13.5, lineHeight: 1.6, color: 'var(--text-strong)', margin: '4px 0 0' }}>{n.text}</p>
              </div>
            ))}
          </div>
        )}
      </Card>
```

(`toast`, `user`, `api`, `Card`, `Button`, `Icon`, `iconBtn` are already imported/available in this file.)

- [ ] **Step 3: Lint**

Run (from `frontend/`): `npm run lint`
Expected: PASS, no new errors.

- [ ] **Step 4: Verify in preview**

Start backend + frontend, log in (admin `admin@racco1.gov.ph` / `admin1234`), open a child's report via Progress Monitoring or Assessment Results, confirm: the Progress log card shows; adding a note persists and appears; delete works; no console errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/ChildProgressReport.jsx
git commit -m "feat(monitoring): progress log section in per-child report"
git push origin main
```

---

## Task 3: Backend — Treatment goals (`Goal`) API (TDD)

**Files:** Modify `children/models.py`, `children/serializers.py`, `children/views.py`, `children/urls.py`; append `children/tests.py`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/children/tests.py`:

```python
from children.models import Goal


class GoalApiTest(APITestCase):
    def setUp(self):
        self.admin_role = Role.objects.create(role_name=Role.ADMINISTRATOR)
        self.psy_role = Role.objects.create(role_name=Role.PSYCHOLOGIST)
        self.staff_role = Role.objects.create(role_name=Role.STAFF)
        self.admin = User.objects.create_user(email="a@racco1.gov.ph", username="a", password="pass1234", role=self.admin_role)
        self.psy = User.objects.create_user(email="p@racco1.gov.ph", username="p", password="pass1234", role=self.psy_role)
        self.staff = User.objects.create_user(email="s@racco1.gov.ph", username="s", password="pass1234", role=self.staff_role)
        self.mine = Child.objects.create(fullname="Ana", assigned_psychologist=self.psy)

    def _auth(self, email):
        token = self.client.post("/api/auth/login/", {"email": email, "password": "pass1234"}).data["access"]
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + token)

    def test_psychologist_creates_goal_defaults_ongoing(self):
        self._auth("p@racco1.gov.ph")
        resp = self.client.post("/api/goals/", {"child": self.mine.id, "text": "Attend school daily"}, format="json")
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data["status"], "ongoing")
        self.assertEqual(Goal.objects.count(), 1)

    def test_toggle_status_to_met(self):
        goal = Goal.objects.create(child=self.mine, author=self.psy, text="x")
        self._auth("p@racco1.gov.ph")
        resp = self.client.patch(f"/api/goals/{goal.id}/", {"status": "met"}, format="json")
        self.assertEqual(resp.status_code, 200)
        goal.refresh_from_db()
        self.assertEqual(goal.status, "met")

    def test_staff_cannot_write(self):
        self._auth("s@racco1.gov.ph")
        resp = self.client.post("/api/goals/", {"child": self.mine.id, "text": "x"}, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_admin_can_create(self):
        self._auth("a@racco1.gov.ph")
        resp = self.client.post("/api/goals/", {"child": self.mine.id, "text": "Admin goal"}, format="json")
        self.assertEqual(resp.status_code, 201)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `venv/Scripts/python manage.py test children.tests.GoalApiTest -v 2`
Expected: FAIL — `Goal` import error / 404s.

- [ ] **Step 3: Add the model**

Append to `backend/children/models.py`:

```python
class Goal(models.Model):
    """A treatment goal on a child's record (Phase 2 monitoring)."""
    ONGOING, MET = "ongoing", "met"
    STATUS_CHOICES = [(ONGOING, "Ongoing"), (MET, "Met")]

    child = models.ForeignKey(Child, on_delete=models.CASCADE, related_name="goals")
    author = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="authored_goals")
    text = models.CharField(max_length=255)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=ONGOING)
    target_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tbl_goal"
        ordering = ["status", "-created_at"]
```

- [ ] **Step 4: Add the serializer**

In `backend/children/serializers.py`, add `Goal` to the model import and append:

```python
class GoalSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="author.fullname", read_only=True, default=None)

    class Meta:
        model = Goal
        fields = ["id", "child", "author", "author_name", "text", "status", "target_date", "created_at"]
        read_only_fields = ["author"]
```

- [ ] **Step 5: Add the viewset**

In `backend/children/views.py`, add `Goal` to the models import and `GoalSerializer` to the serializers import, then append (identical scoping/write rules to `ProgressNoteViewSet`):

```python
class GoalViewSet(viewsets.ModelViewSet):
    """Per-child treatment goals. Same access rules as ProgressNoteViewSet."""
    permission_classes = [ProgressRecordAccess]
    pagination_class = None
    serializer_class = GoalSerializer

    def get_queryset(self):
        qs = Goal.objects.select_related("author", "child").order_by("status", "-created_at")
        child_id = self.request.query_params.get("child")
        if child_id:
            qs = qs.filter(child_id=child_id)
        role = getattr(getattr(self.request.user, "role", None), "role_name", None)
        if role == Role.PSYCHOLOGIST:
            qs = qs.filter(child__assigned_psychologist=self.request.user)
        return qs

    def _assert_can_write(self, child):
        role = getattr(getattr(self.request.user, "role", None), "role_name", None)
        if role == Role.ADMINISTRATOR:
            return
        if role == Role.PSYCHOLOGIST and child.assigned_psychologist_id == self.request.user.id:
            return
        raise PermissionDenied("You can only manage goals for your assigned children.")

    def perform_create(self, serializer):
        self._assert_can_write(serializer.validated_data["child"])
        obj = serializer.save(author=self.request.user)
        log_activity(self.request.user, ActivityLog.CREATED, ActivityLog.RECORD,
                     entity_type="Goal", entity_label=obj.child.fullname,
                     entity_id=obj.id, recipient=obj.child.assigned_psychologist)
```

(Update the imports added in Task 1 to also bring in `Goal` and `GoalSerializer`: `from children.models import Guardian, Child, ProgressNote, Goal` and `from children.serializers import GuardianSerializer, ChildSerializer, ProgressNoteSerializer, GoalSerializer`.)

- [ ] **Step 6: Register the route**

In `backend/children/urls.py`, import `GoalViewSet` and add:

```python
router.register("goals", GoalViewSet, basename="goal")
```

- [ ] **Step 7: Migrate**

Run: `venv/Scripts/python manage.py makemigrations children` then `venv/Scripts/python manage.py migrate`.

- [ ] **Step 8: Run tests**

Run: `venv/Scripts/python manage.py test children -v 2`
Expected: PASS (all `ProgressNoteApiTest` + `GoalApiTest` OK).

- [ ] **Step 9: Commit**

```bash
git add backend/children/
git commit -m "feat(monitoring): treatment goals (Goal) API"
git push origin main
```

---

## Task 4: Frontend — Treatment goals section in the per-child report

**Files:** Modify `frontend/src/pages/ChildProgressReport.jsx`.

- [ ] **Step 1: Add state and handlers**

After the progress-note state added in Task 2, add:

```jsx
  const [goals, setGoals] = useState([]);
  const [goalText, setGoalText] = useState('');

  const loadGoals = () => api.get(`/goals/?child=${id}`).then((r) => setGoals(r.data)).catch(() => {});
  useEffect(() => { loadGoals(); /* eslint-disable-next-line */ }, [id]);

  const addGoal = async () => {
    if (!goalText.trim()) return;
    try { await api.post('/goals/', { child: Number(id), text: goalText.trim() }); setGoalText(''); loadGoals(); toast.success('Goal added'); }
    catch (err) { toast.error(err.response?.data?.detail || 'Could not add goal.'); }
  };
  const toggleGoal = async (g) => {
    try { await api.patch(`/goals/${g.id}/`, { status: g.status === 'met' ? 'ongoing' : 'met' }); loadGoals(); }
    catch (err) { toast.error(err.response?.data?.detail || 'Could not update goal.'); }
  };
  const deleteGoal = async (goalId) => {
    if (!window.confirm('Delete this goal?')) return;
    try { await api.delete(`/goals/${goalId}/`); loadGoals(); toast.success('Goal deleted'); }
    catch (err) { toast.error(err.response?.data?.detail || 'Could not delete.'); }
  };
```

- [ ] **Step 2: Render the Goals card**

Insert immediately **before** the Progress log card added in Task 2:

```jsx
      <Card eyebrow="Treatment goals" title="Goals" padding="20px" style={{ marginTop: 18 }}>
        {canWrite && (
          <div style={{ display: 'flex', gap: 10, marginBottom: goals.length ? 16 : 0 }} className="racco-no-print">
            <input value={goalText} onChange={(e) => setGoalText(e.target.value)} placeholder="Add a treatment goal…"
              style={{ flex: 1, padding: '9px 12px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-strong)', fontFamily: 'var(--font-sans)', fontSize: 14 }} />
            <Button variant="primary" onClick={addGoal} iconLeft={<Icon name="plus" size={16} />} disabled={!goalText.trim()}>Add</Button>
          </div>
        )}
        {goals.length === 0 ? (
          <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>No goals set yet.</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {goals.map((g) => (
              <div key={g.id} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 12px', borderRadius: 'var(--radius-md)', background: 'var(--ink-50)', border: '1px solid var(--border)' }}>
                <button title={g.status === 'met' ? 'Mark ongoing' : 'Mark met'} disabled={!canWrite} onClick={() => toggleGoal(g)}
                  className="racco-no-print" style={{ ...iconBtn(g.status === 'met' ? 'var(--success-600)' : 'var(--text-faint)'), cursor: canWrite ? 'pointer' : 'default' }}>
                  <Icon name={g.status === 'met' ? 'check-circle-2' : 'circle'} size={18} />
                </button>
                <span style={{ flex: 1, fontSize: 13.5, color: 'var(--text-strong)', textDecoration: g.status === 'met' ? 'line-through' : 'none', opacity: g.status === 'met' ? 0.7 : 1 }}>{g.text}</span>
                <Badge tone={g.status === 'met' ? 'success' : 'neutral'} size="sm">{g.status === 'met' ? 'Met' : 'Ongoing'}</Badge>
                {canWrite && <button title="Delete goal" onClick={() => deleteGoal(g.id)} className="racco-no-print" style={iconBtn('var(--red-500)')}><Icon name="trash-2" size={14} /></button>}
              </div>
            ))}
          </div>
        )}
      </Card>
```

(`Badge` is already imported in this file.)

- [ ] **Step 3: Lint + preview verify (add a goal, toggle met/ongoing, delete) + Step 4: Commit**

```bash
git add frontend/src/pages/ChildProgressReport.jsx
git commit -m "feat(monitoring): treatment goals section in per-child report"
git push origin main
```

---

## Task 5: Backend — next-session field, schedule action, monitoring column (TDD)

**Files:** Modify `assessments/models.py`, `assessments/serializers.py`, `assessments/views.py`, `assessments/tests/test_reports.py`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/assessments/tests/test_reports.py` (module already imports `Assessment`, `Child`, `Role`, `User`, `_result`):

```python
class NextSessionTest(APITestCase):
    def setUp(self):
        self.admin_role = Role.objects.create(role_name=Role.ADMINISTRATOR)
        self.psy_role = Role.objects.create(role_name=Role.PSYCHOLOGIST)
        self.admin = User.objects.create_user(email="a@racco1.gov.ph", username="a", password="pass1234", role=self.admin_role)
        self.psy = User.objects.create_user(email="p@racco1.gov.ph", username="p", password="pass1234", role=self.psy_role)
        self.other = User.objects.create_user(email="o@racco1.gov.ph", username="o", password="pass1234", role=self.psy_role)
        self.child = Child.objects.create(fullname="Ana", assigned_psychologist=self.psy)
        self.a = Assessment.objects.create(child=self.child, psychologist=self.psy, status="completed")
        _result(self.a, 50, "Needs Monitoring", "Medium")

    def _auth(self, email):
        token = self.client.post("/api/auth/login/", {"email": email, "password": "pass1234"}).data["access"]
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + token)

    def test_owner_psychologist_can_schedule(self):
        self._auth("p@racco1.gov.ph")
        resp = self.client.patch(f"/api/assessments/{self.a.id}/schedule/", {"next_session": "2026-08-01"}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.a.refresh_from_db()
        self.assertEqual(str(self.a.next_session), "2026-08-01")

    def test_admin_can_schedule(self):
        self._auth("a@racco1.gov.ph")
        resp = self.client.patch(f"/api/assessments/{self.a.id}/schedule/", {"next_session": "2026-08-02"}, format="json")
        self.assertEqual(resp.status_code, 200)

    def test_unrelated_psychologist_cannot_schedule(self):
        self._auth("o@racco1.gov.ph")
        resp = self.client.patch(f"/api/assessments/{self.a.id}/schedule/", {"next_session": "2026-08-03"}, format="json")
        self.assertIn(resp.status_code, (403, 404))

    def test_monitoring_includes_next_session(self):
        self.a.next_session = "2026-08-05"; self.a.save()
        self._auth("a@racco1.gov.ph")
        resp = self.client.get("/api/reports/monitoring/")
        ana = next(r for r in resp.data if r["child_name"] == "Ana")
        self.assertEqual(ana["next_session"], "2026-08-05")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `venv/Scripts/python manage.py test assessments.tests.test_reports.NextSessionTest -v 2`
Expected: FAIL — no `schedule` route / no `next_session` field.

- [ ] **Step 3: Add the model field**

In `backend/assessments/models.py`, in the `Assessment` model, add after `locked_at`:

```python
    next_session = models.DateField(null=True, blank=True)
```

- [ ] **Step 4: Expose in the list serializer**

In `backend/assessments/serializers.py`, add `"next_session"` to `AssessmentListSerializer.Meta.fields` (e.g. after `"assessment_date"`).

- [ ] **Step 5: Add the schedule action**

In `backend/assessments/views.py`, add a method to `AssessmentViewSet` (near `finalize`):

```python
    @action(detail=True, methods=["patch"])
    def schedule(self, request, pk=None):
        assessment = self.get_object()
        role = getattr(getattr(request.user, "role", None), "role_name", None)
        allowed = (role == Role.ADMINISTRATOR) or (assessment.psychologist_id == request.user.id)
        if not allowed:
            return Response({"detail": "You cannot schedule this assessment."},
                            status=status.HTTP_403_FORBIDDEN)
        assessment.next_session = request.data.get("next_session") or None
        assessment.save(update_fields=["next_session", "updated_at"])
        return Response(AssessmentListSerializer(assessment).data)
```

Note: `AssessmentViewSet.get_queryset` scopes a psychologist to `child__assigned_psychologist=self`, so `self.get_object()` already 404s for an unrelated psychologist — the explicit check additionally blocks a non-owner within scope.

- [ ] **Step 6: Add `next_session` to the monitoring endpoint**

In `MonitoringListView.get`, add to each row dict:

```python
                "next_session": latest.next_session if latest else None,
```

- [ ] **Step 7: Migrate + run tests**

Run: `venv/Scripts/python manage.py makemigrations assessments` then `migrate`, then:
`venv/Scripts/python manage.py test assessments -v 1`
Expected: PASS (new `NextSessionTest` + existing suite, including the Phase 1 `MonitoringApiTest`, still green).

- [ ] **Step 8: Commit**

```bash
git add backend/assessments/
git commit -m "feat(monitoring): next-session field, schedule action, monitoring column"
git push origin main
```

---

## Task 6: Frontend — next-session UI (report control + monitoring column)

**Files:** Modify `frontend/src/pages/ChildProgressReport.jsx`, `frontend/src/pages/Monitoring.jsx`.

- [ ] **Step 1: Report — schedule control**

In `ChildProgressReport.jsx`, add a handler (near the other handlers):

```jsx
  const setNextSession = async (val) => {
    if (!latest) return;
    try { await api.patch(`/assessments/${latest.id}/schedule/`, { next_session: val || null }); toast.success('Next session updated'); load(); }
    catch (err) { toast.error(err.response?.data?.detail || 'Could not update.'); }
  };
```

Then, inside the header `<Card>` (after the `{rows.length} assessment(s) …` line), add:

```jsx
        <div style={{ marginTop: 10, display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: 'var(--text-muted)' }} className="racco-no-print">
          <Icon name="calendar" size={15} />
          <span>Next session:</span>
          {canWrite ? (
            <input type="date" defaultValue={latest?.next_session || ''} onChange={(e) => setNextSession(e.target.value)}
              style={{ padding: '5px 9px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-strong)', fontFamily: 'var(--font-sans)', fontSize: 13 }} />
          ) : (
            <strong style={{ color: 'var(--text-strong)' }}>{latest?.next_session || '—'}</strong>
          )}
        </div>
```

- [ ] **Step 2: Monitoring — Next session column**

In `Monitoring.jsx`, add `'Next Session'` to the header array (after `'Last Assessment'`):

```jsx
                  {['Child', 'Case Type', 'Psychologist', 'Trajectory', 'Latest', 'Score', 'Last Assessment', 'Next Session', 'Assessments'].map((h) => (
```

And add the matching cell in each row (after the `last_assessment_date` cell, before the `assessment_count` cell):

```jsx
                      <td style={td}>{r.next_session || '—'}</td>
```

- [ ] **Step 3: Lint + preview verify**

Run `npm run lint` (from `frontend/`). In the preview: set a next-session date on a child's report, confirm it persists and shows in the Progress Monitoring "Next Session" column. No console errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/ChildProgressReport.jsx frontend/src/pages/Monitoring.jsx
git commit -m "feat(monitoring): next-session UI in report and overview"
git push origin main
```

---

## Self-Review (completed during planning)

- **Spec coverage:** progress log (Tasks 1–2) ✓; treatment goals with ongoing/met (Tasks 3–4) ✓; real next-session date + overview column (Tasks 5–6) ✓; write = admin or assigned psychologist, staff read-only (`ProgressRecordAccess` + `schedule` check) ✓; psychologist scoping to assigned children (viewset `get_queryset`) ✓; migrations included (Steps in Tasks 1, 3, 5) ✓.
- **Placeholder scan:** none — every step has concrete code/commands.
- **Type/name consistency:** endpoints `/api/progress-notes/`, `/api/goals/`, `/api/assessments/<id>/schedule/` match between viewsets, `urls.py`, tests, and the frontend `api` calls (axios `baseURL` includes `/api`). Response keys used by the frontend (`author_name`, `date`, `text`, `status`, `next_session`) match the serializers. `canWrite` gate consistent across report sections. The `MonitoringListView` row gains `next_session`, consumed by `Monitoring.jsx`.
- **Scope note:** Tasks 1–2, 3–4, and 5–6 are independent and individually shippable; they can also be split into separate execution runs if preferred.
