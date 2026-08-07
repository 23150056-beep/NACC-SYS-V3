# Activity Log & Categorized Notifications — Design

- **Date:** 2026-06-26
- **Status:** Approved (design)
- **Type:** Additive, cross-cutting feature (not one of the original Phase 1–4 roadmap items). Complements the existing "Compliance & Audit" theme.
- **Related:** [System Design](2026-06-22-nacc-system-design.md)

---

## 1. Problem & Goal

The notification box already exists in the UI ([Topbar.jsx](../../../frontend/src/components/Topbar.jsx)) — a bell with an unread badge and a dropdown — but it is wired to a **static `activity` array** in `frontend/src/data/seedData.js`. It never reflects anything that actually happens in the system.

**Goal:** record real system events server-side and surface them in the notification box so any authenticated user can keep track of what is going on — who added, edited, archived, or signed in. Notifications are **split by category** so it is clear at a glance which kind of activity each entry is.

## 2. Scope

**Tracked actions:** `created`, `updated`, `archived`, `login`.

**Tracked entities → category:**
- Children, Guardians → category **`record`**
- Users → category **`user`**
- Logins → category **`security`**

**Out of scope:**
- Assessments and their results (Phase 2/3) — not yet built.
- Per-user server-side read/unread state (handled client-side via `localStorage`).
- Editing/deleting log entries (the log is append-only; archive is a soft-delete elsewhere, the log itself is immutable).
- Guardian creation has no dedicated UI yet, so guardian events appear only when created via API. This is acceptable.

## 3. Architecture

Logging happens **server-side inside the DRF viewsets**, not from the frontend. This captures every action regardless of source and records the acting user from the request. Django signals were rejected because they cannot cleanly see the request user.

A new lightweight Django app, **`activity`**, owns the model, a `log_activity(...)` helper, a serializer, and a read-only API endpoint.

```
backend/
└── activity/
    ├── __init__.py
    ├── apps.py
    ├── models.py          # ActivityLog
    ├── serializers.py     # ActivityLogSerializer
    ├── services.py        # log_activity(...) helper
    ├── views.py           # ActivityLogViewSet (read-only list)
    ├── urls.py            # /api/activity/
    ├── migrations/
    └── tests/
        └── test_activity.py
```

## 4. Data Model — `tbl_activity_log`

| Field | Type | Purpose |
|---|---|---|
| `id` | BigAuto PK | — |
| `actor` | FK → User, `null=True`, `on_delete=SET_NULL`, `related_name="activities"` | Who performed the action. Nullable so deleting a user never destroys history. |
| `actor_label` | CharField(150), blank | Snapshot of the actor's display name at event time (`fullname` or `username`), so the log still reads correctly if the user is later renamed or removed. |
| `action` | CharField(20), choices | `created` / `updated` / `archived` / `login`. |
| `category` | CharField(20), choices | `record` / `user` / `security`. Drives the dropdown split. |
| `entity_type` | CharField(50), blank | e.g. `"Child"`, `"Guardian"`, `"User"`. Blank for logins. |
| `entity_label` | CharField(255), blank | Human label, e.g. the child's fullname or the user's email. |
| `entity_id` | PositiveIntegerField, `null=True` | The affected row's id, when applicable. |
| `created_at` | DateTimeField(`auto_now_add=True`) | Timestamp; relative time ("just now", "2 hours ago") is computed on the frontend. |

`Meta`: `db_table = "tbl_activity_log"`, `ordering = ["-created_at"]`.

### `log_activity` helper (`activity/services.py`)

```python
def log_activity(actor, action, category, *, entity_type="", entity_label="", entity_id=None):
    is_user = bool(getattr(actor, "is_authenticated", False))
    ActivityLog.objects.create(
        actor=actor if is_user else None,
        actor_label=(getattr(actor, "fullname", "") or getattr(actor, "username", "") or "System") if is_user else "System",
        action=action,
        category=category,
        entity_type=entity_type,
        entity_label=entity_label,
        entity_id=entity_id,
    )
```

Logging must never break the primary request: callers wrap it so a logging failure is swallowed (defensive `try/except` in the hook sites, or the helper logs to stderr and returns). The primary write has already succeeded by the time we log.

## 5. Backend Hook Points

| Where | Method | Logged event |
|---|---|---|
| `children/views.py` → `_ArchivableViewSet` (covers Child **and** Guardian) | `perform_create` | `created`, category `record`, entity_type from `self.model.__name__` |
| same | `perform_update` | `updated`, category `record` |
| same | `archive` action | `archived`, category `record` |
| `accounts/views.py` → `UserViewSet` | `perform_create` | `created`, category `user`, entity_type `"User"` |
| same | `perform_update` | `updated`, category `user` |
| same | `archive` action | `archived`, category `user` |
| `accounts/views.py` → `LoginView.post` | on `200` response | `login`, category `security`, no entity |

- `_ArchivableViewSet` derives `entity_type` from `self.model.__name__` (`"Child"` / `"Guardian"`) and `entity_label` from the instance's `fullname`.
- `UserViewSet` uses `entity_label` = the saved user's `fullname` or `email`.
- `LoginView` resolves the authenticated user from the validated serializer (`serializer.user`) to set `actor`.

## 6. API

`GET /api/activity/`
- Read-only list, `IsAuthenticated` (all roles see the bell), no pagination.
- Newest first, **capped at the 50 most recent**.
- Optional `?category=record|user|security` filter.
- Wired in `config/urls.py` via `path("api/", include("activity.urls"))`.

`ActivityLogSerializer` fields: `id`, `actor_label`, `action`, `category`, `entity_type`, `entity_label`, `entity_id`, `created_at`.

## 7. Frontend

### `src/context/ActivityContext.jsx`
- Provider placed **inside** `AuthProvider` (so it can call the authed API).
- On mount and whenever the user becomes available, `GET /api/activity/`.
- Exposes: `events`, `loading`, `refresh()`, `unreadCount`, `markSeen()`.
- **Unread** = count of events with `created_at` newer than `lastSeenActivityAt` (a timestamp in `localStorage`). `markSeen()` sets it to now. No backend read-state.
- A `useActivity()` hook for consumers.

### `Topbar.jsx` (the notification box)
- Replace the `seedData.activity` import with `useActivity()`.
- **Category tabs** at the top of the dropdown: **All · Records · Users · Security** (local `useState`; filters `events` by `category`, mapping Records→`record`, Users→`user`, Security→`security`).
- **Per-action icon + color** for unambiguous reading:
  | action | icon (lucide) | color token |
  |---|---|---|
  | created | `plus` | `--success-500` |
  | updated | `pencil` | `--blue-500` |
  | archived | `archive` | `--red-500` |
  | login | `log-in` | `--amber-500` |
- **Display text** composed from structured fields:
  - record/user `created` → `Added {entity_type_lower} {entity_label}`
  - `updated` → `Edited {entity_type_lower} {entity_label}`
  - `archived` → `Archived {entity_type_lower} {entity_label}`
  - `login` → `Signed in`
  - The secondary line shows `{actor_label} · {relative_time}`.
- Open the dropdown → `markSeen()`. Badge shows `unreadCount`.
- A small `timeAgo(iso)` helper renders relative time.

### Action pages → instant refresh
- [Children.jsx](../../../frontend/src/pages/Children.jsx): after a successful `save` (create/edit) and `archive`, call `refresh()`.
- [Users.jsx](../../../frontend/src/pages/Users.jsx): same after `save` and `archive`.
- Because logging is server-side, `refresh()` re-fetches and the new entry appears immediately.

### Dashboard consistency
- [Dashboard.jsx](../../../frontend/src/pages/Dashboard.jsx) "Activity Feed" currently reads the same static `activity`. Switch it to `useActivity()` `events` (showing the most recent ~6) so the dashboard and the bell agree.
- The static `activity` export in `seedData.js` becomes unused and is removed.

## 8. Testing

Backend (`activity/tests/test_activity.py`, matching existing APITestCase style):
- Creating a child via the API writes one `created` / `record` log.
- Archiving a child writes an `archived` / `record` log.
- Creating a user (as Admin) writes a `created` / `user` log.
- A successful login writes a `login` / `security` log.
- `GET /api/activity/` requires auth and returns newest-first.
- `GET /api/activity/?category=security` returns only login events.

Frontend: verified via `npm run build` + a browser check that the bell shows a new entry after adding/archiving a record and that the category tabs filter.

## 9. File Change Summary

**New:** `backend/activity/` app (models, services, serializers, views, urls, apps, migration, tests); `frontend/src/context/ActivityContext.jsx`.

**Modified:**
- `backend/config/settings.py` — add `"activity"` to `INSTALLED_APPS`.
- `backend/config/urls.py` — include `activity.urls`.
- `backend/children/views.py` — log in `_ArchivableViewSet`.
- `backend/accounts/views.py` — log in `UserViewSet` + `LoginView`.
- `frontend/src/App.jsx` — wrap with `ActivityProvider`.
- `frontend/src/components/Topbar.jsx` — live data, category tabs, action icons, unread.
- `frontend/src/pages/Children.jsx`, `frontend/src/pages/Users.jsx` — `refresh()` after writes.
- `frontend/src/pages/Dashboard.jsx` — live activity feed.
- `frontend/src/data/seedData.js` — remove the static `activity` array.
