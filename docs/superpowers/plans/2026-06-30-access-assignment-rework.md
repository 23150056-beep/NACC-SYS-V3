# Access, Assignment & Instrument Rework — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make child→psychologist assignment govern access so psychologists are isolated to their assigned children across the whole system, instruments are owned per-psychologist, reassignment is explicit with a carry-history choice, assessment-taking is psychologist-only, notifications are role-scoped, plus three assessment-area UX refinements.

**Architecture:** Enforce scoping **server-side** in DRF viewset querysets + serializer validation (never trust the client). Three small model fields drive everything: `Questionnaire.owner`, `Child.assignee_sees_history`, `ActivityLog.recipient`. Frontend changes mostly fall out of the now-scoped API responses; a few targeted UI edits add the carry-history toggle, owner picker, nav move, View Results shortcut, and answers recap.

**Tech Stack:** Django REST Framework + SQLite (backend, `backend/venv`), React + Vite (frontend), pytest/Django test runner.

**Spec:** `docs/superpowers/specs/2026-06-30-access-assignment-rework-design.md`

---

## File Structure

**Backend (modify):**
- `backend/assessments/models.py` — add `Questionnaire.owner` FK
- `backend/children/models.py` — add `Child.assignee_sees_history`
- `backend/activity/models.py` — add `ActivityLog.recipient` FK
- `backend/activity/services.py` — `log_activity(..., recipient=None)`
- `backend/accounts/permissions.py` — `ASSESSMENT_TAKER_ROLES = (Role.PSYCHOLOGIST,)`
- `backend/children/views.py` — scope `ChildViewSet.get_queryset`; set recipient + assignee_sees_history on save
- `backend/children/serializers.py` — expose `assignee_sees_history`
- `backend/assessments/views.py` — scope `AssessmentViewSet`, `QuestionnaireViewSet`, `ActiveQuestionnaireListView`; owner on create
- `backend/assessments/serializers.py` — add `owner`; validate assigned-child + owned-instrument
- `backend/activity/views.py` — role-scope `ActivityLogViewSet.get_queryset`
- migrations under each app

**Frontend (modify):**
- `frontend/src/components/Sidebar.jsx` — nav move
- `frontend/src/pages/Children.jsx` — carry-history toggle
- `frontend/src/pages/Assessment.jsx` — View Results button + answers recap
- `frontend/src/pages/Questionnaires.jsx` — owner column + owner picker
- `frontend/src/components/Topbar.jsx` — role-aware notification tabs

**Tests (add to existing app test dirs):**
- `backend/children/tests/` , `backend/assessments/tests/` , `backend/activity/tests/`

---

## Execution order (phases)

1. Backend model fields + migrations
2. Backend permissions (psychologist-only taking)
3. Backend records scoping
4. Backend instrument ownership + scoping
5. Backend assessment scoping + take-validation (carry-history)
6. Backend notifications (recipient + feed scoping)
7. Backend assignment serializer (assignee_sees_history)
8. Frontend changes
9. Full-stack verification

> **Convention:** every task = write test → run (fail) → implement → run (pass) → commit. Run backend tests with `backend/venv/Scripts/python.exe manage.py test <app>`. Read the file named in each task before editing — exact line numbers shift.

---

## Phase 1 — Model fields + migrations

### Task 1: `Questionnaire.owner`
**Files:** Modify `backend/assessments/models.py`; Migrate.
- [ ] Read `assessments/models.py`; add to `Questionnaire`:
```python
owner = models.ForeignKey(
    "accounts.User", on_delete=models.SET_NULL, null=True, blank=True,
    related_name="owned_instruments",
)
```
- [ ] `python manage.py makemigrations assessments` → expect `000X_questionnaire_owner`.
- [ ] `python manage.py migrate`; commit.

### Task 2: `Child.assignee_sees_history`
**Files:** Modify `backend/children/models.py`.
- [ ] Add to `Child`: `assignee_sees_history = models.BooleanField(default=True)`
- [ ] makemigrations children → migrate → commit.

### Task 3: `ActivityLog.recipient`
**Files:** Modify `backend/activity/models.py`.
- [ ] Read the model; add:
```python
recipient = models.ForeignKey(
    "accounts.User", on_delete=models.SET_NULL, null=True, blank=True,
    related_name="notifications",
)
```
- [ ] makemigrations activity → migrate → commit.

---

## Phase 2 — Permissions

### Task 4: Restrict assessment-taking to psychologists
**Files:** Modify `backend/accounts/permissions.py:53`; Test `backend/assessments/tests/`.
- [ ] Write test: an Administrator POSTing `/api/assessments/` gets 403; a Psychologist is allowed (assigned child + owned instrument).
- [ ] Run → fail.
- [ ] Change `ASSESSMENT_TAKER_ROLES = (Role.ADMINISTRATOR, Role.PSYCHOLOGIST)` → `ASSESSMENT_TAKER_ROLES = (Role.PSYCHOLOGIST,)`.
- [ ] Run → pass; commit.

---

## Phase 3 — Records scoping

### Task 5: Psychologist sees only assigned children
**Files:** Modify `backend/children/views.py` (`_ArchivableViewSet`/`ChildViewSet.get_queryset`); Test `backend/children/tests/`.
- [ ] Write test: create children A (assigned to psyA) and B (assigned to psyB); `GET /api/children/` as psyA returns only A; as Admin/Staff returns both. Retrieving B's id as psyA → 404.
- [ ] Run → fail.
- [ ] In `ChildViewSet`, override `get_queryset` to filter for psychologists:
```python
def get_queryset(self):
    qs = super().get_queryset()
    role = getattr(getattr(self.request.user, "role", None), "role_name", None)
    if role == Role.PSYCHOLOGIST:
        qs = qs.filter(assigned_psychologist=self.request.user)
    return qs
```
(Import `Role`. Keep `GuardianViewSet` unscoped — guardians stay admin/staff-managed.)
- [ ] Run → pass; commit.

---

## Phase 4 — Instrument ownership

### Task 6: Owner on create + owner-scoped lists
**Files:** Modify `backend/assessments/serializers.py` (`QuestionnaireSerializer`), `backend/assessments/views.py`; Test `backend/assessments/tests/`.
- [ ] Write tests: (a) psychologist creating a questionnaire → `owner == self`; (b) `GET /api/questionnaires/` as psyA returns only psyA-owned; admin returns all; (c) `GET /api/active-questionnaires/` as psyA returns only psyA's active ones; (d) admin create requires `owner` in payload.
- [ ] Run → fail.
- [ ] Add `owner` to `QuestionnaireSerializer.Meta.fields`; in `QuestionnaireViewSet.perform_create`, set owner = self for psychologist, else require payload owner. Scope `QuestionnaireViewSet.get_queryset` and `ActiveQuestionnaireListView.get_queryset` by `owner=self.request.user` when role is psychologist.
- [ ] Run → pass; commit.

---

## Phase 5 — Assessment scoping + take validation

### Task 7: Results scoped by assigned child + carry-history
**Files:** Modify `backend/assessments/views.py` (`AssessmentViewSet.get_queryset`); Test.
- [ ] Write tests: child C assigned to psyB. With `assignee_sees_history=True`, psyB sees C's assessment authored by psyA; with `False`, psyB sees only own-authored. psyA (no longer assigned) sees neither via the list. Admin/Staff see all.
- [ ] Run → fail.
- [ ] Replace the psychologist branch:
```python
from django.db.models import Q
...
if role == Role.PSYCHOLOGIST:
    qs = qs.filter(child__assigned_psychologist=self.request.user).filter(
        Q(child__assignee_sees_history=True) | Q(psychologist=self.request.user))
```
- [ ] Run → pass; commit.

### Task 8: Take-assessment validation (assigned child + owned instrument)
**Files:** Modify `backend/assessments/serializers.py` (`AssessmentWriteSerializer.validate`); Test.
- [ ] Write tests: psychologist POST with an unassigned child → 400 "not assigned to you"; with an unowned instrument → 400 "not yours"; with own child + own instrument → 201.
- [ ] Run → fail.
- [ ] In `validate`, read `self.context["request"].user`; if `child.assigned_psychologist_id != user.id` raise `ValidationError`; if `questionnaire.owner_id != user.id` raise `ValidationError`.
- [ ] Run → pass; commit.

---

## Phase 6 — Notifications

### Task 9: `recipient` plumbing + role-scoped feed
**Files:** Modify `backend/activity/services.py`, `backend/activity/views.py`, logging call sites; Test `backend/activity/tests/`.
- [ ] Write tests: assigning child to psyP creates an ActivityLog with `recipient=psyP`; `GET /api/activity/` as psyP returns only `recipient=self`; as Staff returns `category=record` & entity in (Child, Guardian, Assessment); as Admin returns all.
- [ ] Run → fail.
- [ ] `log_activity(..., recipient=None)` stores it. `ActivityLogViewSet.get_queryset`:
```python
role = ...
if role == Role.PSYCHOLOGIST:
    qs = qs.filter(recipient=self.request.user)
elif role == Role.STAFF:
    qs = qs.filter(category=ActivityLog.RECORD, entity_type__in=["Child", "Guardian", "Assessment"])
# admin: unchanged
```
- [ ] Run → pass; commit.

---

## Phase 7 — Assignment serializer + recipient on save

### Task 10: `assignee_sees_history` write + assignment notification
**Files:** Modify `backend/children/serializers.py`, `backend/children/views.py`; Test.
- [ ] Write test: PUT a child with a new `psychologist` + `assignee_sees_history=false` persists the flag and creates a `recipient`-targeted "assigned" ActivityLog.
- [ ] Run → fail.
- [ ] Add `assignee_sees_history` to `ChildSerializer.Meta.fields`. In `ChildViewSet.perform_update`/`perform_create`, when `assigned_psychologist` is set/changed, `log_activity(..., recipient=child.assigned_psychologist)`; also set recipient on child create/update logs to the assigned psychologist.
- [ ] Run → pass; commit.

---

## Phase 8 — Frontend

> No tests; verify via run/preview in Phase 9. Read each file before editing.

### Task 11: Sidebar nav move
- [ ] In `Sidebar.jsx` NAV array, move the `Assessment Instruments` item under the `Casework` section directly below `Records`; remove the Compliance & Audit entry. Commit.

### Task 12: Assessment — View Results shortcut + answers recap
- [ ] In `Assessment.jsx`: add a top-of-page "View Results" `Button` → `navigate('/report')`. In step 4, render a read-only list mapping `questions` → `answers[q.id]`. Commit.

### Task 13: Children — carry-history toggle
- [ ] In `Children.jsx` ChildForm: when editing an existing record and the selected `psychologist` differs from the original, show a toggle "Carry assessment history to the new psychologist?" bound to `form.assignee_sees_history` (default true); include it in the save payload. Commit.

### Task 14: Questionnaires — owner column + picker
- [ ] In `Questionnaires.jsx`: for admin, show an Owner column and an owner `<Select>` (psychologist list) on create/edit; for psychologist, owner is implicit (self). Commit.

### Task 15: Topbar — role-aware tabs
- [ ] In `Topbar.jsx`, render the notification category tabs based on role: admin = All/Records/Users/Security; staff = All/Records; psychologist = All only. Commit.

---

## Phase 9 — Verification

### Task 16: Full-stack verification per role
- [ ] Run backend tests: `backend/venv/Scripts/python.exe manage.py test` → all pass.
- [ ] Start backend + frontend (preview tooling). Log in as psychologist (`levi@racco1.gov.ph`) → Records shows only assigned children; Instruments shows only own; notifications show only own. Log in as staff → case-stream notifications. Log in as admin (`admin@racco1.gov.ph`) → full access.
- [ ] Confirm nav placement, View Results shortcut, answers recap, carry-history toggle render.
- [ ] Commit any fixes; push.

---

## Self-Review notes
- Spec coverage: every §-rule maps to a task (records §5→T5, results carry §5→T7, take-validation §5→T8, instruments §5→T6, permissions §13→T4, notifications §7.5→T9, assignment §6→T10, UX §7→T11–T15).
- Reassignment "Admin/Staff choose" → the carry-history toggle (T13) writes `assignee_sees_history` (T10).
- Reporting spec is a separate, later plan.
