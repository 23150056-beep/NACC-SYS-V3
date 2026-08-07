# Activity Log & Categorized Notifications — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Record real create/edit/archive/login events server-side and surface them, split by category, in the existing notification bell.

**Architecture:** A new Django `activity` app owns an append-only `ActivityLog` model, a `log_activity()` helper, and a read-only `/api/activity/` endpoint. Existing DRF viewsets (children/guardians, users) and the login serializer call the helper. A React `ActivityContext` fetches the feed; the Topbar bell renders it with category tabs and per-action icons.

**Tech Stack:** Django 5 + DRF + SimpleJWT (backend, SQLite); React + Vite (frontend, no test harness — verified by build + browser).

**Spec:** [2026-06-26-activity-log-notifications-design.md](../specs/2026-06-26-activity-log-notifications-design.md)

**Conventions:** Backend runs from `backend/` as `./venv/Scripts/python.exe manage.py <cmd>` (Windows). Commits in this repo must NOT include a Claude co-author trailer.

**Login-hook note:** the spec planned to log the login in `LoginView`, but at login time the request is anonymous (`request.user` is `AnonymousUser`). The clean handle to the authenticated user is `self.user` inside `LoginSerializer.validate`, so login logging lives there.

---

## File Structure

**New (backend `activity` app):**
- `backend/activity/__init__.py` — empty
- `backend/activity/apps.py` — `ActivityConfig`
- `backend/activity/models.py` — `ActivityLog`
- `backend/activity/services.py` — `log_activity(...)`
- `backend/activity/serializers.py` — `ActivityLogSerializer`
- `backend/activity/views.py` — `ActivityLogViewSet`
- `backend/activity/urls.py` — router → `/api/activity/`
- `backend/activity/migrations/__init__.py` + generated `0001_initial.py`
- `backend/activity/tests/__init__.py` + `backend/activity/tests/test_activity.py`

**New (frontend):**
- `frontend/src/context/ActivityContext.jsx`

**Modified:**
- `backend/config/settings.py` (INSTALLED_APPS), `backend/config/urls.py` (include)
- `backend/children/views.py`, `backend/accounts/views.py`, `backend/accounts/serializers.py`
- `frontend/src/App.jsx`, `frontend/src/components/Topbar.jsx`, `frontend/src/pages/Children.jsx`, `frontend/src/pages/Users.jsx`, `frontend/src/pages/Dashboard.jsx`, `frontend/src/data/seedData.js`

---

## Task 1: Create the `activity` app with the `ActivityLog` model

**Files:**
- Create: `backend/activity/__init__.py`, `backend/activity/apps.py`, `backend/activity/models.py`, `backend/activity/tests/__init__.py`, `backend/activity/tests/test_activity.py`
- Modify: `backend/config/settings.py` (INSTALLED_APPS)

- [ ] **Step 1: Create the app package files**

`backend/activity/__init__.py` — empty file.

`backend/activity/apps.py`:
```python
from django.apps import AppConfig


class ActivityConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "activity"
```

`backend/activity/models.py`:
```python
from django.conf import settings
from django.db import models


class ActivityLog(models.Model):
    CREATED, UPDATED, ARCHIVED, LOGIN = "created", "updated", "archived", "login"
    ACTION_CHOICES = [
        (CREATED, "Created"), (UPDATED, "Updated"),
        (ARCHIVED, "Archived"), (LOGIN, "Login"),
    ]

    RECORD, USER, SECURITY = "record", "user", "security"
    CATEGORY_CHOICES = [
        (RECORD, "Record"), (USER, "User"), (SECURITY, "Security"),
    ]

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="activities")
    actor_label = models.CharField(max_length=150, blank=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    entity_type = models.CharField(max_length=50, blank=True)
    entity_label = models.CharField(max_length=255, blank=True)
    entity_id = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "tbl_activity_log"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.actor_label} {self.action} {self.entity_type} {self.entity_label}".strip()
```

`backend/activity/tests/__init__.py` — empty file.

`backend/activity/tests/test_activity.py`:
```python
from django.test import TestCase
from activity.models import ActivityLog


class ActivityLogModelTest(TestCase):
    def test_create_minimal_log(self):
        log = ActivityLog.objects.create(
            actor=None, actor_label="System",
            action=ActivityLog.LOGIN, category=ActivityLog.SECURITY)
        self.assertEqual(log.category, "security")
        self.assertIsNotNone(log.created_at)
```

- [ ] **Step 2: Register the app**

In `backend/config/settings.py`, add `"activity",` to `INSTALLED_APPS` directly after `"assessments",`:
```python
    "accounts",
    "children",
    "assessments",
    "activity",
]
```

- [ ] **Step 3: Make migrations**

Run: `./venv/Scripts/python.exe manage.py makemigrations activity`
Expected: `Migrations for 'activity':` ... `Create model ActivityLog`.

- [ ] **Step 4: Run the model test (it should pass after migrate)**

Run: `./venv/Scripts/python.exe manage.py test activity -v 2`
Expected: 1 test, OK (the test DB applies the new migration automatically).

- [ ] **Step 5: Commit**

```bash
git add backend/activity backend/config/settings.py
git commit -m "feat(activity): add ActivityLog model + app scaffolding"
```

---

## Task 2: Read-only `/api/activity/` endpoint

**Files:**
- Create: `backend/activity/serializers.py`, `backend/activity/views.py`, `backend/activity/urls.py`
- Modify: `backend/config/urls.py`
- Test: `backend/activity/tests/test_activity.py`

- [ ] **Step 1: Add the failing endpoint test**

Append to `backend/activity/tests/test_activity.py`:
```python
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from accounts.models import Role

User = get_user_model()


class ActivityApiTest(APITestCase):
    def setUp(self):
        self.role = Role.objects.create(role_name=Role.STAFF)
        self.user = User.objects.create_user(
            email="staff@racco1.gov.ph", username="staff", password="staff1234",
            role=self.role)
        ActivityLog.objects.create(
            actor=self.user, actor_label="Staff",
            action=ActivityLog.CREATED, category=ActivityLog.RECORD,
            entity_type="Child", entity_label="Juan")
        ActivityLog.objects.create(
            actor=self.user, actor_label="Staff",
            action=ActivityLog.LOGIN, category=ActivityLog.SECURITY)

    def _auth(self):
        token = self.client.post("/api/auth/login/", {
            "email": "staff@racco1.gov.ph", "password": "staff1234"}).data["access"]
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + token)

    def test_requires_authentication(self):
        resp = self.client.get("/api/activity/")
        self.assertEqual(resp.status_code, 401)

    def test_lists_newest_first(self):
        self._auth()
        resp = self.client.get("/api/activity/")
        self.assertEqual(resp.status_code, 200)
        # login row was created last in setUp, plus the login from _auth()
        self.assertEqual(resp.data[0]["category"], "security")

    def test_filters_by_category(self):
        self._auth()
        resp = self.client.get("/api/activity/?category=record")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(all(r["category"] == "record" for r in resp.data))
        self.assertEqual(len(resp.data), 1)
```

- [ ] **Step 2: Run it to verify failure**

Run: `./venv/Scripts/python.exe manage.py test activity.tests.test_activity.ActivityApiTest -v 2`
Expected: FAIL (404/no URL — `/api/activity/` not wired yet).

- [ ] **Step 3: Create serializer, view, urls**

`backend/activity/serializers.py`:
```python
from rest_framework import serializers
from activity.models import ActivityLog


class ActivityLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivityLog
        fields = [
            "id", "actor_label", "action", "category",
            "entity_type", "entity_label", "entity_id", "created_at",
        ]
```

`backend/activity/views.py`:
```python
from rest_framework import mixins, viewsets, permissions
from activity.models import ActivityLog
from activity.serializers import ActivityLogSerializer


class ActivityLogViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None
    serializer_class = ActivityLogSerializer

    def get_queryset(self):
        qs = ActivityLog.objects.all()
        category = self.request.query_params.get("category")
        if category:
            qs = qs.filter(category=category)
        return qs[:50]
```

`backend/activity/urls.py`:
```python
from rest_framework.routers import DefaultRouter
from activity.views import ActivityLogViewSet

router = DefaultRouter()
router.register("activity", ActivityLogViewSet, basename="activity")

urlpatterns = router.urls
```

- [ ] **Step 4: Wire the URLs into the project**

In `backend/config/urls.py`, add the include after the children include:
```python
urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("accounts.urls")),
    path("api/", include("children.urls")),
    path("api/", include("activity.urls")),
]
```

- [ ] **Step 5: Run the endpoint tests to verify pass**

Run: `./venv/Scripts/python.exe manage.py test activity.tests.test_activity.ActivityApiTest -v 2`
Expected: 3 tests, OK.

- [ ] **Step 6: Commit**

```bash
git add backend/activity backend/config/urls.py
git commit -m "feat(activity): read-only /api/activity endpoint with category filter"
```

---

## Task 3: `log_activity` helper + children/guardian hooks

**Files:**
- Create: `backend/activity/services.py`
- Modify: `backend/children/views.py`
- Test: `backend/activity/tests/test_activity.py`

- [ ] **Step 1: Add the failing hook test**

Append to `backend/activity/tests/test_activity.py`:
```python
from children.models import Child


class RecordHookTest(APITestCase):
    def setUp(self):
        self.role = Role.objects.create(role_name=Role.STAFF)
        self.user = User.objects.create_user(
            email="staff@racco1.gov.ph", username="staff", password="staff1234",
            role=self.role)
        token = self.client.post("/api/auth/login/", {
            "email": "staff@racco1.gov.ph", "password": "staff1234"}).data["access"]
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + token)

    def test_create_child_logs_record_created(self):
        self.client.post("/api/children/", {
            "fullname": "Juan Cruz", "case_type": "Foster"})
        logs = ActivityLog.objects.filter(category="record", action="created")
        self.assertEqual(logs.count(), 1)
        self.assertEqual(logs.first().entity_type, "Child")
        self.assertEqual(logs.first().entity_label, "Juan Cruz")

    def test_archive_child_logs_record_archived(self):
        child = Child.objects.create(fullname="Ana Lopez", case_type="Adoption")
        self.client.post(f"/api/children/{child.id}/archive/")
        self.assertEqual(
            ActivityLog.objects.filter(category="record", action="archived").count(), 1)
```

- [ ] **Step 2: Run it to verify failure**

Run: `./venv/Scripts/python.exe manage.py test activity.tests.test_activity.RecordHookTest -v 2`
Expected: FAIL (0 logs — hooks not added yet).

- [ ] **Step 3: Create the `log_activity` helper**

`backend/activity/services.py`:
```python
import logging
from activity.models import ActivityLog

logger = logging.getLogger(__name__)


def log_activity(actor, action, category, *, entity_type="", entity_label="", entity_id=None):
    """Record an activity event. Never raises — logging must not break the request."""
    try:
        is_user = bool(getattr(actor, "is_authenticated", False))
        label = ((getattr(actor, "fullname", "") or getattr(actor, "username", ""))
                 if is_user else "System") or "System"
        ActivityLog.objects.create(
            actor=actor if is_user else None,
            actor_label=label,
            action=action,
            category=category,
            entity_type=entity_type,
            entity_label=entity_label or "",
            entity_id=entity_id,
        )
    except Exception:  # pragma: no cover - defensive
        logger.exception("Failed to write activity log")
```

- [ ] **Step 4: Hook the children/guardian viewset**

Replace the entire contents of `backend/children/views.py` with:
```python
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from accounts.permissions import RecordsAccess
from activity.models import ActivityLog
from activity.services import log_activity
from children.models import Guardian, Child
from children.serializers import GuardianSerializer, ChildSerializer


class _ArchivableViewSet(viewsets.ModelViewSet):
    permission_classes = [RecordsAccess]
    pagination_class = None
    model = None

    def get_queryset(self):
        qs = self.model.objects.all().order_by("fullname")
        if self.request.query_params.get("include_archived") != "true":
            qs = qs.exclude(status=self.model.ARCHIVED)
        return qs

    def _log(self, obj, action_name):
        log_activity(
            self.request.user, action_name, ActivityLog.RECORD,
            entity_type=self.model.__name__,
            entity_label=getattr(obj, "fullname", ""),
            entity_id=obj.id)

    def perform_create(self, serializer):
        obj = serializer.save()
        self._log(obj, ActivityLog.CREATED)

    def perform_update(self, serializer):
        obj = serializer.save()
        self._log(obj, ActivityLog.UPDATED)

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        obj = self.get_object()
        obj.status = self.model.ARCHIVED
        obj.save(update_fields=["status", "updated_at"])
        self._log(obj, ActivityLog.ARCHIVED)
        return Response({"status": "archived"}, status=status.HTTP_200_OK)


class GuardianViewSet(_ArchivableViewSet):
    model = Guardian
    serializer_class = GuardianSerializer


class ChildViewSet(_ArchivableViewSet):
    model = Child
    serializer_class = ChildSerializer
```

- [ ] **Step 5: Run the hook tests to verify pass**

Run: `./venv/Scripts/python.exe manage.py test activity.tests.test_activity.RecordHookTest -v 2`
Expected: 2 tests, OK.

- [ ] **Step 6: Commit**

```bash
git add backend/activity/services.py backend/children/views.py backend/activity/tests/test_activity.py
git commit -m "feat(activity): log child/guardian create, update, archive"
```

---

## Task 4: User hooks + login hook

**Files:**
- Modify: `backend/accounts/views.py`, `backend/accounts/serializers.py`
- Test: `backend/activity/tests/test_activity.py`

- [ ] **Step 1: Add the failing tests**

Append to `backend/activity/tests/test_activity.py`:
```python
class UserAndLoginHookTest(APITestCase):
    def setUp(self):
        self.admin_role = Role.objects.create(role_name=Role.ADMINISTRATOR)
        self.staff_role = Role.objects.create(role_name=Role.STAFF)
        self.admin = User.objects.create_superuser(
            email="admin@racco1.gov.ph", username="admin", password="admin1234",
            role=self.admin_role)

    def _auth_admin(self):
        token = self.client.post("/api/auth/login/", {
            "email": "admin@racco1.gov.ph", "password": "admin1234"}).data["access"]
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + token)

    def test_login_logs_security_event(self):
        # the _auth_admin login below is the event under test
        self._auth_admin()
        self.assertEqual(
            ActivityLog.objects.filter(category="security", action="login").count(), 1)

    def test_create_user_logs_user_created(self):
        self._auth_admin()
        self.client.post("/api/users/", {
            "email": "new@racco1.gov.ph", "username": "newbie",
            "first_name": "New", "last_name": "Bie",
            "role": self.staff_role.id, "password": "newpass123"})
        self.assertEqual(
            ActivityLog.objects.filter(category="user", action="created").count(), 1)
```

- [ ] **Step 2: Run to verify failure**

Run: `./venv/Scripts/python.exe manage.py test activity.tests.test_activity.UserAndLoginHookTest -v 2`
Expected: FAIL (0 logs for both).

- [ ] **Step 3: Hook the login serializer**

In `backend/accounts/serializers.py`, add imports near the top (after the existing imports):
```python
from activity.models import ActivityLog
from activity.services import log_activity
```
Then update `LoginSerializer.validate` to log after a successful validation:
```python
    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = UserSerializer(self.user).data
        log_activity(self.user, ActivityLog.LOGIN, ActivityLog.SECURITY)
        return data
```

- [ ] **Step 4: Hook the UserViewSet**

In `backend/accounts/views.py`, add imports after the existing `from accounts.serializers import (...)` block:
```python
from activity.models import ActivityLog
from activity.services import log_activity
```
Then add the create/update hooks and update `archive` inside `UserViewSet` (place the two `perform_*` methods just above `archive`):
```python
    def _log(self, user, action_name):
        log_activity(
            self.request.user, action_name, ActivityLog.USER,
            entity_type="User",
            entity_label=(user.fullname or user.email),
            entity_id=user.id)

    def perform_create(self, serializer):
        user = serializer.save()
        self._log(user, ActivityLog.CREATED)

    def perform_update(self, serializer):
        user = serializer.save()
        self._log(user, ActivityLog.UPDATED)

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        user = self.get_object()
        user.status = User.ARCHIVED
        user.is_active = False
        user.save(update_fields=["status", "is_active", "updated_at"])
        self._log(user, ActivityLog.ARCHIVED)
        return Response({"status": "archived"}, status=status.HTTP_200_OK)
```
(Remove the old `archive` method — it is replaced by the version above.)

- [ ] **Step 5: Run to verify pass**

Run: `./venv/Scripts/python.exe manage.py test activity.tests.test_activity.UserAndLoginHookTest -v 2`
Expected: 2 tests, OK.

- [ ] **Step 6: Run the FULL backend suite (no regressions)**

Run: `./venv/Scripts/python.exe manage.py test`
Expected: all tests OK (16 prior + the new activity tests).

- [ ] **Step 7: Commit**

```bash
git add backend/accounts/views.py backend/accounts/serializers.py backend/activity/tests/test_activity.py
git commit -m "feat(activity): log user create/update/archive and logins"
```

---

## Task 5: Frontend `ActivityContext` + app wiring

**Files:**
- Create: `frontend/src/context/ActivityContext.jsx`
- Modify: `frontend/src/App.jsx`

- [ ] **Step 1: Create the context**

`frontend/src/context/ActivityContext.jsx`:
```jsx
import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import api from '../api/client';
import { useAuth } from './AuthContext';

const ActivityContext = createContext(null);
const SEEN_KEY = 'lastSeenActivityAt';

export function ActivityProvider({ children }) {
  const { user } = useAuth();
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(false);
  const [lastSeen, setLastSeen] = useState(() => localStorage.getItem(SEEN_KEY) || '');

  const refresh = useCallback(() => {
    if (!localStorage.getItem('access')) return;
    setLoading(true);
    api.get('/activity/')
      .then((r) => setEvents(r.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (user) refresh();
    else setEvents([]);
  }, [user, refresh]);

  const unreadCount = events.filter(
    (e) => !lastSeen || new Date(e.created_at) > new Date(lastSeen)
  ).length;

  const markSeen = useCallback(() => {
    const now = new Date().toISOString();
    localStorage.setItem(SEEN_KEY, now);
    setLastSeen(now);
  }, []);

  return (
    <ActivityContext.Provider value={{ events, loading, refresh, unreadCount, markSeen }}>
      {children}
    </ActivityContext.Provider>
  );
}

export function useActivity() {
  return useContext(ActivityContext)
    || { events: [], loading: false, refresh: () => {}, unreadCount: 0, markSeen: () => {} };
}
```

- [ ] **Step 2: Wrap the app**

In `frontend/src/App.jsx`, import the provider and wrap `BrowserRouter` (inside `AuthProvider`):
```jsx
import { AuthProvider } from './context/AuthContext';
import { ActivityProvider } from './context/ActivityContext';
```
```jsx
  return (
    <AuthProvider>
      <ActivityProvider>
        <BrowserRouter>
          <Routes>
            {/* ...unchanged routes... */}
          </Routes>
        </BrowserRouter>
      </ActivityProvider>
    </AuthProvider>
  );
```

- [ ] **Step 3: Verify the build compiles**

Run (from `frontend/`): `npm run build`
Expected: `built in ...` with no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/context/ActivityContext.jsx frontend/src/App.jsx
git commit -m "feat(activity): ActivityContext fetches live feed + unread tracking"
```

---

## Task 6: Topbar bell — live data, category tabs, action icons

**Files:**
- Modify: `frontend/src/components/Topbar.jsx`

- [ ] **Step 1: Swap the data source and add helpers**

In `frontend/src/components/Topbar.jsx`, replace the seed import:
```jsx
import { activity } from '../data/seedData';
```
with:
```jsx
import { useActivity } from '../context/ActivityContext';

const ACTION_META = {
  created: { icon: 'plus', color: 'var(--success-500)' },
  updated: { icon: 'pencil', color: 'var(--blue-500)' },
  archived: { icon: 'archive', color: 'var(--red-500)' },
  login: { icon: 'log-in', color: 'var(--amber-500)' },
};
const NOTIF_TABS = [
  { key: 'all', label: 'All' },
  { key: 'record', label: 'Records' },
  { key: 'user', label: 'Users' },
  { key: 'security', label: 'Security' },
];
function eventText(e) {
  if (e.action === 'login') return 'Signed in';
  const verb = e.action === 'created' ? 'Added' : e.action === 'updated' ? 'Edited' : 'Archived';
  const type = (e.entity_type || '').toLowerCase();
  return `${verb} ${type}${e.entity_label ? ` ${e.entity_label}` : ''}`.trim();
}
function timeAgo(iso) {
  const s = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return 'just now';
  const m = Math.floor(s / 60);
  if (m < 60) return `${m} min ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h} hr ago`;
  const d = Math.floor(h / 24);
  return `${d} day${d > 1 ? 's' : ''} ago`;
}
```

- [ ] **Step 2: Replace `unread`/`activity` state with the context**

In the `Topbar` component body, delete:
```jsx
  const unread = activity.filter((n) => n.tone !== 'success').length;
```
and add (near the other `useState` hooks):
```jsx
  const { events, unreadCount, markSeen } = useActivity();
  const [notifTab, setNotifTab] = useState('all');
  const unread = unreadCount;
  const shownEvents = events.filter((e) => notifTab === 'all' || e.category === notifTab);
```
Update the bell button's `onClick` to mark events seen when opening:
```jsx
            onClick={() => setNotifOpen((o) => { const next = !o; if (next) markSeen(); return next; })}
```

- [ ] **Step 3: Replace the dropdown body**

Replace the dropdown header + list block (the `<div role="menu">...</div>` content) with the tabbed, live version:
```jsx
          {notifOpen && (
            <div role="menu" style={{ position: 'absolute', top: 'calc(100% + 10px)', right: 0, width: 340, background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', boxShadow: 'var(--shadow-xl)', zIndex: 80, overflow: 'hidden', animation: 'racco-pop-in var(--dur-base) var(--ease-out)' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '13px 16px', borderBottom: '1px solid var(--border)' }}>
                <span style={{ fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 14, color: 'var(--text-strong)' }}>Notifications</span>
                <span className="racco-eyebrow" style={{ fontSize: 10 }}>{unread} new</span>
              </div>
              <div style={{ display: 'flex', gap: 4, padding: '8px 12px', borderBottom: '1px solid var(--border)' }}>
                {NOTIF_TABS.map((t) => {
                  const on = notifTab === t.key;
                  return (
                    <button key={t.key} onClick={() => setNotifTab(t.key)} style={{ flex: 1, padding: '5px 6px', borderRadius: 'var(--radius-sm)', border: 'none', cursor: 'pointer', fontFamily: 'var(--font-sans)', fontWeight: 700, fontSize: 11.5, background: on ? 'var(--blue-50)' : 'transparent', color: on ? 'var(--blue-700)' : 'var(--text-muted)', transition: 'var(--transition-base)' }}>{t.label}</button>
                  );
                })}
              </div>
              <div className="racco-scroll" style={{ maxHeight: 320, overflowY: 'auto' }}>
                {shownEvents.length === 0 ? (
                  <div style={{ padding: '24px 16px', textAlign: 'center', fontSize: 12.5, color: 'var(--text-faint)' }}>No activity yet.</div>
                ) : shownEvents.map((n, i) => {
                  const meta = ACTION_META[n.action] || ACTION_META.created;
                  return (
                    <div key={n.id ?? i} role="menuitem"
                      style={{ width: '100%', textAlign: 'left', display: 'flex', gap: 11, padding: '12px 16px', borderBottom: i < shownEvents.length - 1 ? '1px solid var(--ink-100)' : 'none' }}>
                      <span style={{ width: 26, height: 26, borderRadius: '50%', flex: 'none', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', background: 'var(--ink-50)', color: meta.color }}>
                        <Icon name={meta.icon} size={14} />
                      </span>
                      <span style={{ flex: 1, minWidth: 0 }}>
                        <span style={{ display: 'block', fontSize: 13, color: 'var(--text-strong)', fontWeight: 600, lineHeight: 1.4 }}>{eventText(n)}</span>
                        <span style={{ display: 'block', fontSize: 11.5, color: 'var(--text-faint)', marginTop: 2 }}>{n.actor_label} · {timeAgo(n.created_at)}</span>
                      </span>
                    </div>
                  );
                })}
              </div>
              <button onClick={() => { setNotifOpen(false); navigate('/'); }} style={{ width: '100%', padding: '11px 16px', background: 'var(--ink-50)', border: 'none', borderTop: '1px solid var(--border)', cursor: 'pointer', fontFamily: 'var(--font-sans)', fontWeight: 700, fontSize: 12.5, color: 'var(--blue-600)' }}>View all activity</button>
            </div>
          )}
```

- [ ] **Step 4: Verify the build compiles**

Run (from `frontend/`): `npm run build`
Expected: built with no errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/Topbar.jsx
git commit -m "feat(activity): live notification bell with category tabs + action icons"
```

---

## Task 7: Instant refresh on writes + live Dashboard feed + cleanup

**Files:**
- Modify: `frontend/src/pages/Children.jsx`, `frontend/src/pages/Users.jsx`, `frontend/src/pages/Dashboard.jsx`, `frontend/src/data/seedData.js`

- [ ] **Step 1: Refresh the feed after child writes**

In `frontend/src/pages/Children.jsx`, import and use the hook:
```jsx
import { useActivity } from '../context/ActivityContext';
```
Inside `Children()`, after `const { user } = useAuth();`:
```jsx
  const { refresh: refreshActivity } = useActivity();
```
In `save`, after the successful `setForm(null); load();`, add `refreshActivity();`. In `archive`, after `setSel(null); load();`, add `refreshActivity();`.

- [ ] **Step 2: Refresh the feed after user writes**

In `frontend/src/pages/Users.jsx`:
```jsx
import { useActivity } from '../context/ActivityContext';
```
Inside `Users()`, near the top state:
```jsx
  const { refresh: refreshActivity } = useActivity();
```
In `save`, after `setForm(null); load();`, add `refreshActivity();`. In `archive`, after `load();`, add `refreshActivity();`.

- [ ] **Step 3: Point the Dashboard activity feed at live data**

In `frontend/src/pages/Dashboard.jsx`, replace:
```jsx
import { metrics, trend, activity } from '../data/seedData';
```
with:
```jsx
import { metrics, trend } from '../data/seedData';
import { useActivity } from '../context/ActivityContext';
import { eventText, timeAgo } from '../components/Topbar';
```
Inside `Dashboard()`, after the existing hooks:
```jsx
  const { events } = useActivity();
  const feed = events.slice(0, 6);
```
Replace the Activity Feed `.map` over `activity` with `feed`, rendering text via `eventText`/`timeAgo` and `actor_label`:
```jsx
            {feed.length === 0 ? (
              <div style={{ fontSize: 13, color: 'var(--text-faint)', padding: '8px 0' }}>No recent activity.</div>
            ) : feed.map((a, i) => (
              <div key={a.id ?? i} style={{ display: 'flex', gap: 11, padding: '11px 0', borderBottom: i < feed.length - 1 ? '1px solid var(--ink-100)' : 'none' }}>
                <span style={{ width: 8, height: 8, borderRadius: '50%', marginTop: 5, flex: 'none', background: a.action === 'archived' ? 'var(--red-500)' : a.action === 'created' ? 'var(--success-500)' : a.action === 'login' ? 'var(--amber-500)' : 'var(--blue-500)' }} />
                <div>
                  <div style={{ fontSize: 13, color: 'var(--text-strong)', fontWeight: 600, lineHeight: 1.4 }}>{eventText(a)}</div>
                  <div style={{ fontSize: 11.5, color: 'var(--text-faint)', marginTop: 2 }}>{a.actor_label} · {timeAgo(a.created_at)}</div>
                </div>
              </div>
            ))}
```

- [ ] **Step 4: Export the helpers from Topbar and drop the seed `activity`**

In `frontend/src/components/Topbar.jsx`, change `function eventText` → `export function eventText` and `function timeAgo` → `export function timeAgo` so Dashboard can reuse them.

In `frontend/src/data/seedData.js`, delete the `export const activity = [ ... ];` block (now unused).

- [ ] **Step 5: Verify the build compiles**

Run (from `frontend/`): `npm run build`
Expected: built with no errors (no leftover `activity` import references).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/Children.jsx frontend/src/pages/Users.jsx frontend/src/pages/Dashboard.jsx frontend/src/data/seedData.js frontend/src/components/Topbar.jsx
git commit -m "feat(activity): instant bell refresh on writes + live dashboard feed"
```

---

## Task 8: End-to-end verification

- [ ] **Step 1: Full backend suite**

Run (from `backend/`): `./venv/Scripts/python.exe manage.py test`
Expected: all OK.

- [ ] **Step 2: Frontend production build**

Run (from `frontend/`): `npm run build`
Expected: built, no errors.

- [ ] **Step 3: Browser smoke test (preview)**

Start the dev server, log in as admin, add a child, archive it, and open the bell:
- A green "Added child …" and a red "Archived child …" appear.
- The **Records** tab shows them; the **Security** tab shows the login; the **Users** tab is empty until a user is added.
- The unread badge clears after opening the bell and reappears after a new action.
```
