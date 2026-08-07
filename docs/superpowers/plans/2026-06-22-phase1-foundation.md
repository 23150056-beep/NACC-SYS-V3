# Phase 1 — Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the real backend + authentication + data model so users can log in by role, Admins can manage users, and Admin/Staff can manage child + guardian records persisted in a database.

**Architecture:** A Django + Django REST Framework backend (`backend/`) with SQLite and JWT auth exposes a REST API. The existing React + Vite + Tailwind app (`frontend/`, moved from the repo root) consumes that API, with a login screen, JWT handling, and role-based routing/menus. All 10 data-model tables are created now; only Users, Children, and Guardians get full CRUD in this phase.

**Tech Stack:** Python 3.13, Django 5.1, Django REST Framework, djangorestframework-simplejwt, django-cors-headers, SQLite, React 18, Vite, Tailwind, react-router-dom v6, axios.

**Testing approach:** Backend uses Django's `APITestCase` (true TDD — write failing test, then code). The existing frontend has no test harness; adding one is out of Phase 1 scope, so frontend tasks use explicit **manual browser verification** steps (run the app, do X, expect Y) plus `npm run build` as a compile check. This follows the existing-codebase pattern.

**Conventions:**
- Run backend commands from `backend/` with the virtual environment activated.
- Activate venv: Windows PowerShell `./venv/Scripts/Activate.ps1` · Git Bash `source venv/Scripts/activate`.
- The 4th capstone role, **Child Respondent**, is NOT a login account — it is a guided interface tied to a child record, built in Phase 2. Phase 1 seeds three login roles: Administrator, Counselor, Staff.

---

## File Structure

### Backend (new — `backend/`)
```
backend/
├── manage.py
├── requirements.txt
├── .env.example
├── config/
│   ├── settings.py          # project settings, DRF, JWT, CORS, SQLite
│   ├── urls.py              # /api/ root routing
│   ├── wsgi.py / asgi.py
├── accounts/
│   ├── models.py            # Role, User (custom, email login)
│   ├── managers.py          # UserManager
│   ├── serializers.py       # UserSerializer, UserWriteSerializer, LoginSerializer
│   ├── permissions.py       # IsAdministrator, IsAdminOrStaff
│   ├── views.py             # LoginView, MeView, UserViewSet
│   ├── urls.py
│   ├── management/commands/seed_initial_data.py
│   └── tests/               # test_auth.py, test_users.py
├── children/
│   ├── models.py            # Guardian, Child
│   ├── serializers.py
│   ├── views.py             # GuardianViewSet, ChildViewSet
│   ├── urls.py
│   └── tests/               # test_children.py, test_guardians.py
└── assessments/
    └── models.py            # Questionnaire, Question, Assessment, Response, AssessmentResult, Recommendation (models only)
```

### Frontend (`frontend/`, moved from repo root)
```
frontend/
├── .env                     # VITE_API_BASE_URL
├── src/
│   ├── api/client.js        # axios instance + JWT interceptors
│   ├── context/AuthContext.jsx
│   ├── components/ProtectedRoute.jsx
│   ├── components/Sidebar.jsx      # MODIFY: role-based links + user
│   ├── components/Topbar.jsx       # MODIFY: logout + current user
│   ├── pages/Login.jsx             # NEW
│   ├── pages/Children.jsx          # MODIFY: API + forms
│   ├── pages/Users.jsx             # NEW: admin user management
│   ├── App.jsx                     # MODIFY: AuthProvider, routes
│   └── data/mockData.js            # MODIFY: trim to dashboard-only demo data
```

---

## Task 1: Backend project scaffolding

**Files:**
- Create: `backend/requirements.txt`, `backend/.env.example`
- Create (via django-admin): `backend/manage.py`, `backend/config/*`, `backend/accounts/`, `backend/children/`, `backend/assessments/`
- Modify: `backend/config/settings.py`, `backend/config/urls.py`

- [ ] **Step 1: Create the backend folder, virtualenv, and requirements**

Create `backend/requirements.txt`:
```
Django==5.1.4
djangorestframework==3.15.2
djangorestframework-simplejwt==5.3.1
django-cors-headers==4.6.0
python-dotenv==1.0.1
```

Run (from repo root):
```bash
mkdir -p backend && cd backend
python -m venv venv
# activate venv (see Conventions), then:
pip install -r requirements.txt
```
Expected: all packages install without error.

- [ ] **Step 2: Generate the Django project and apps**

Run (from `backend/`, venv active):
```bash
django-admin startproject config .
python manage.py startapp accounts
python manage.py startapp children
python manage.py startapp assessments
```
Expected: `manage.py`, `config/`, `accounts/`, `children/`, `assessments/` exist.

- [ ] **Step 3: Configure settings**

Replace the relevant sections of `backend/config/settings.py`:
```python
import os
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-insecure-change-me")
DEBUG = os.getenv("DJANGO_DEBUG", "True") == "True"
ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "accounts",
    "children",
    "assessments",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# NOTE: AUTH_USER_MODEL is set in Task 2 (after the custom User model exists),
# before the first migration is ever run.

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
}

CORS_ALLOWED_ORIGINS = os.getenv(
    "CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
).split(",")
```
Leave the default `DATABASES` (SQLite) as generated.

- [ ] **Step 4: Create `.env.example`**

Create `backend/.env.example`:
```
DJANGO_SECRET_KEY=dev-insecure-change-me
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```
(The engineer copies this to `backend/.env` locally; `.env` is gitignored.)

- [ ] **Step 5: Verify configuration is valid**

Run: `python manage.py check`
Expected: `System check identified no issues (0 silenced).`
Do **not** run `migrate` yet (the custom user model arrives in Task 2 before the first migration).

- [ ] **Step 6: Commit**

```bash
cd ..
git add backend/requirements.txt backend/.env.example backend/manage.py backend/config backend/accounts backend/children backend/assessments
git commit -m "feat(backend): scaffold Django project, DRF, JWT, CORS settings"
```

---

## Task 2: Roles & custom User model

**Files:**
- Create: `backend/accounts/managers.py`, `backend/accounts/management/__init__.py`, `backend/accounts/management/commands/__init__.py`, `backend/accounts/management/commands/seed_initial_data.py`, `backend/accounts/tests/__init__.py`, `backend/accounts/tests/test_models.py`
- Modify: `backend/accounts/models.py`, `backend/config/settings.py`, `backend/accounts/admin.py`

- [ ] **Step 1: Write the failing test**

Create `backend/accounts/tests/__init__.py` (empty) and `backend/accounts/tests/test_models.py`:
```python
from django.test import TestCase
from django.contrib.auth import get_user_model
from accounts.models import Role

User = get_user_model()


class UserModelTest(TestCase):
    def test_create_user_with_role_and_fullname(self):
        role = Role.objects.create(role_name=Role.COUNSELOR)
        user = User.objects.create_user(
            email="jane@racco1.gov.ph",
            username="jane",
            password="secret123",
            first_name="Jane",
            last_name="Cruz",
            middle_initial="D",
            role=role,
        )
        self.assertTrue(user.check_password("secret123"))
        self.assertEqual(user.fullname, "Jane D Cruz")
        self.assertEqual(user.status, User.ACTIVE)
        self.assertEqual(user.role.role_name, "Counselor")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python manage.py test accounts`
Expected: FAIL/ERROR (`Role` / custom fields do not exist yet).

- [ ] **Step 3: Create the UserManager**

Create `backend/accounts/managers.py`:
```python
from django.contrib.auth.models import BaseUserManager


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        if extra.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True")
        if extra.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True")
        return self._create_user(email, password, **extra)
```

- [ ] **Step 4: Define the Role and User models**

Replace `backend/accounts/models.py`:
```python
from django.contrib.auth.models import AbstractUser
from django.db import models

from accounts.managers import UserManager


class Role(models.Model):
    ADMINISTRATOR = "Administrator"
    COUNSELOR = "Counselor"
    STAFF = "Staff"

    role_name = models.CharField(max_length=50, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tbl_role"

    def __str__(self):
        return self.role_name


class User(AbstractUser):
    ACTIVE = "active"
    ARCHIVED = "archived"
    STATUS_CHOICES = [(ACTIVE, "Active"), (ARCHIVED, "Archived")]

    email = models.EmailField(unique=True)
    middle_initial = models.CharField(max_length=5, blank=True)
    contact_details = models.CharField(max_length=50, blank=True)
    role = models.ForeignKey(
        Role, on_delete=models.PROTECT, null=True, blank=True, related_name="users"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    objects = UserManager()

    class Meta:
        db_table = "tbl_user"

    @property
    def fullname(self):
        parts = [self.first_name, self.middle_initial, self.last_name]
        return " ".join(p for p in parts if p)

    def __str__(self):
        return self.email
```

- [ ] **Step 5: Wire up AUTH_USER_MODEL and register admin**

Add to `backend/config/settings.py` (after the `INSTALLED_APPS` block):
```python
AUTH_USER_MODEL = "accounts.User"
```

Replace `backend/accounts/admin.py`:
```python
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from accounts.models import Role, User

admin.site.register(Role)
admin.site.register(User, UserAdmin)
```

- [ ] **Step 6: Create and run the first migration**

Run:
```bash
python manage.py makemigrations accounts
python manage.py migrate
```
Expected: migrations created and applied with no errors (fresh SQLite DB).

- [ ] **Step 7: Run the test to verify it passes**

Run: `python manage.py test accounts`
Expected: PASS (1 test).

- [ ] **Step 8: Create the seed command**

Create `backend/accounts/management/__init__.py` (empty), `backend/accounts/management/commands/__init__.py` (empty), and `backend/accounts/management/commands/seed_initial_data.py`:
```python
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from accounts.models import Role

User = get_user_model()


class Command(BaseCommand):
    help = "Seed default roles and an initial administrator account."

    def handle(self, *args, **options):
        for name in [Role.ADMINISTRATOR, Role.COUNSELOR, Role.STAFF]:
            Role.objects.get_or_create(role_name=name)
        self.stdout.write(self.style.SUCCESS("Roles seeded."))

        admin_role = Role.objects.get(role_name=Role.ADMINISTRATOR)
        if not User.objects.filter(email="admin@racco1.gov.ph").exists():
            User.objects.create_superuser(
                email="admin@racco1.gov.ph",
                username="admin",
                password="admin1234",
                first_name="System",
                last_name="Administrator",
                role=admin_role,
            )
            self.stdout.write(self.style.SUCCESS("Default admin created: admin@racco1.gov.ph / admin1234"))
        else:
            self.stdout.write("Admin already exists; skipping.")
```

- [ ] **Step 9: Run the seed command**

Run: `python manage.py seed_initial_data`
Expected: "Roles seeded." and "Default admin created: admin@racco1.gov.ph / admin1234".

- [ ] **Step 10: Commit**

```bash
cd ..
git add backend/accounts backend/config/settings.py
git commit -m "feat(accounts): custom email-login User, Role model, seed command"
cd backend
```

---

## Task 3: JWT authentication endpoints

**Files:**
- Create: `backend/accounts/serializers.py`, `backend/accounts/permissions.py`, `backend/accounts/urls.py`, `backend/accounts/tests/test_auth.py`
- Modify: `backend/accounts/views.py`, `backend/config/urls.py`

- [ ] **Step 1: Write the failing test**

Create `backend/accounts/tests/test_auth.py`:
```python
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from accounts.models import Role

User = get_user_model()


class AuthTest(APITestCase):
    def setUp(self):
        self.role = Role.objects.create(role_name=Role.ADMINISTRATOR)
        self.user = User.objects.create_user(
            email="admin@racco1.gov.ph", username="admin",
            password="admin1234", first_name="Sys", last_name="Admin",
            role=self.role,
        )

    def test_login_returns_tokens_and_user(self):
        resp = self.client.post("/api/auth/login/", {
            "email": "admin@racco1.gov.ph", "password": "admin1234"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("access", resp.data)
        self.assertEqual(resp.data["user"]["role_name"], "Administrator")

    def test_me_requires_auth(self):
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 401)

    def test_me_returns_current_user(self):
        login = self.client.post("/api/auth/login/", {
            "email": "admin@racco1.gov.ph", "password": "admin1234"})
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + login.data["access"])
        resp = self.client.get("/api/auth/me/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["email"], "admin@racco1.gov.ph")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python manage.py test accounts.tests.test_auth`
Expected: FAIL (endpoints/serializers do not exist).

- [ ] **Step 3: Create the serializers**

Create `backend/accounts/serializers.py`:
```python
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import get_user_model
from accounts.models import Role

User = get_user_model()


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ["id", "role_name"]


class UserSerializer(serializers.ModelSerializer):
    role_name = serializers.CharField(source="role.role_name", read_only=True)
    fullname = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id", "email", "username", "first_name", "last_name",
            "middle_initial", "contact_details", "role", "role_name",
            "fullname", "status",
        ]


class UserWriteSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = User
        fields = [
            "id", "email", "username", "first_name", "last_name",
            "middle_initial", "contact_details", "role", "status", "password",
        ]

    def create(self, validated_data):
        password = validated_data.pop("password", None) or "changeme123"
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class LoginSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = user.role.role_name if user.role else None
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = UserSerializer(self.user).data
        return data
```

- [ ] **Step 4: Create permission classes**

Create `backend/accounts/permissions.py`:
```python
from rest_framework.permissions import BasePermission
from accounts.models import Role


def _role_name(request):
    role = getattr(request.user, "role", None)
    return role.role_name if role else None


class IsAdministrator(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated
                    and _role_name(request) == Role.ADMINISTRATOR)


class IsAdminOrStaff(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated
                    and _role_name(request) in (Role.ADMINISTRATOR, Role.STAFF))
```

- [ ] **Step 5: Create the views**

Replace `backend/accounts/views.py`:
```python
from rest_framework import generics, permissions
from rest_framework_simplejwt.views import TokenObtainPairView
from accounts.serializers import LoginSerializer, UserSerializer


class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer


class MeView(generics.RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user
```

- [ ] **Step 6: Wire URLs**

Create `backend/accounts/urls.py`:
```python
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from accounts.views import LoginView, MeView

urlpatterns = [
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/me/", MeView.as_view(), name="me"),
]
```

Replace `backend/config/urls.py`:
```python
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("accounts.urls")),
]
```

- [ ] **Step 7: Run the test to verify it passes**

Run: `python manage.py test accounts.tests.test_auth`
Expected: PASS (3 tests).

- [ ] **Step 8: Commit**

```bash
cd ..
git add backend/accounts backend/config/urls.py
git commit -m "feat(accounts): JWT login, token refresh, and /me endpoints"
cd backend
```

---

## Task 4: User Management API (Admin CRUD + archive)

**Files:**
- Create: `backend/accounts/tests/test_users.py`
- Modify: `backend/accounts/views.py`, `backend/accounts/urls.py`

- [ ] **Step 1: Write the failing test**

Create `backend/accounts/tests/test_users.py`:
```python
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from accounts.models import Role

User = get_user_model()


class UserManagementTest(APITestCase):
    def setUp(self):
        self.admin_role = Role.objects.create(role_name=Role.ADMINISTRATOR)
        self.staff_role = Role.objects.create(role_name=Role.STAFF)
        self.admin = User.objects.create_user(
            email="admin@racco1.gov.ph", username="admin", password="admin1234",
            role=self.admin_role)
        self.staff = User.objects.create_user(
            email="staff@racco1.gov.ph", username="staff", password="staff1234",
            role=self.staff_role)

    def _auth(self, email, password):
        token = self.client.post("/api/auth/login/", {
            "email": email, "password": password}).data["access"]
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + token)

    def test_admin_can_create_user(self):
        self._auth("admin@racco1.gov.ph", "admin1234")
        resp = self.client.post("/api/users/", {
            "email": "new@racco1.gov.ph", "username": "newbie",
            "first_name": "New", "last_name": "Bie",
            "role": self.staff_role.id, "password": "pass1234"})
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(User.objects.filter(email="new@racco1.gov.ph").exists())

    def test_staff_cannot_create_user(self):
        self._auth("staff@racco1.gov.ph", "staff1234")
        resp = self.client.post("/api/users/", {
            "email": "x@racco1.gov.ph", "username": "x", "role": self.staff_role.id})
        self.assertEqual(resp.status_code, 403)

    def test_archive_sets_status_and_blocks_login(self):
        self._auth("admin@racco1.gov.ph", "admin1234")
        resp = self.client.post(f"/api/users/{self.staff.id}/archive/")
        self.assertEqual(resp.status_code, 200)
        self.staff.refresh_from_db()
        self.assertEqual(self.staff.status, User.ARCHIVED)
        self.assertFalse(self.staff.is_active)
        # archived user can no longer authenticate
        login = self.client.post("/api/auth/login/", {
            "email": "staff@racco1.gov.ph", "password": "staff1234"})
        self.assertEqual(login.status_code, 401)

    def test_list_excludes_archived_by_default(self):
        self._auth("admin@racco1.gov.ph", "admin1234")
        self.client.post(f"/api/users/{self.staff.id}/archive/")
        resp = self.client.get("/api/users/")
        emails = [u["email"] for u in resp.data]
        self.assertIn("admin@racco1.gov.ph", emails)
        self.assertNotIn("staff@racco1.gov.ph", emails)

    def test_admin_can_list_roles(self):
        self._auth("admin@racco1.gov.ph", "admin1234")
        resp = self.client.get("/api/roles/")
        self.assertEqual(resp.status_code, 200)
        names = [r["role_name"] for r in resp.data]
        self.assertIn("Administrator", names)
        self.assertIn("Staff", names)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python manage.py test accounts.tests.test_users`
Expected: FAIL (no `/api/users/` route).

- [ ] **Step 3: Add the UserViewSet**

Append to `backend/accounts/views.py`:
```python
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from accounts.models import Role
from accounts.permissions import IsAdministrator
from accounts.serializers import UserWriteSerializer, RoleSerializer

User = get_user_model()


class UserViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdministrator]
    pagination_class = None

    def get_queryset(self):
        qs = User.objects.all().order_by("last_name", "first_name")
        if self.request.query_params.get("include_archived") != "true":
            qs = qs.exclude(status=User.ARCHIVED)
        return qs

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return UserWriteSerializer
        return UserSerializer

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        user = self.get_object()
        user.status = User.ARCHIVED
        user.is_active = False
        user.save(update_fields=["status", "is_active", "updated_at"])
        return Response({"status": "archived"}, status=status.HTTP_200_OK)


class RoleListView(generics.ListAPIView):
    permission_classes = [IsAdministrator]
    pagination_class = None
    serializer_class = RoleSerializer

    def get_queryset(self):
        return Role.objects.all().order_by("role_name")
```

> `generics` is already imported at the top of `views.py` (from Task 3); the append block above adds the `Role` / `RoleSerializer` imports it needs.

- [ ] **Step 4: Register the router**

Replace `backend/accounts/urls.py`:
```python
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from accounts.views import LoginView, MeView, UserViewSet, RoleListView

router = DefaultRouter()
router.register("users", UserViewSet, basename="user")

urlpatterns = [
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/me/", MeView.as_view(), name="me"),
    path("roles/", RoleListView.as_view(), name="role-list"),
    path("", include(router.urls)),
]
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `python manage.py test accounts.tests.test_users`
Expected: PASS (5 tests).

- [ ] **Step 6: Commit**

```bash
cd ..
git add backend/accounts
git commit -m "feat(accounts): admin-only user management API with archive"
cd backend
```

---

## Task 5: Guardian & Child models

**Files:**
- Modify: `backend/children/models.py`, `backend/children/admin.py`
- Create: `backend/children/tests/__init__.py`, `backend/children/tests/test_models.py`

- [ ] **Step 1: Write the failing test**

Create `backend/children/tests/__init__.py` (empty) and `backend/children/tests/test_models.py`:
```python
from django.test import TestCase
from children.models import Guardian, Child


class ChildModelTest(TestCase):
    def test_child_links_to_guardian(self):
        g = Guardian.objects.create(fullname="Maria Cruz", gender="Female",
                                    address="Bauang", case_type="Foster")
        c = Child.objects.create(fullname="Juan Cruz", gender="Male",
                                 address="Bauang", case_type="Foster", guardian=g)
        self.assertEqual(c.guardian.fullname, "Maria Cruz")
        self.assertEqual(c.status, Child.ACTIVE)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python manage.py test children`
Expected: FAIL (models do not exist).

- [ ] **Step 3: Define the models**

Replace `backend/children/models.py`:
```python
from django.db import models


class Guardian(models.Model):
    ACTIVE = "active"
    ARCHIVED = "archived"
    STATUS_CHOICES = [(ACTIVE, "Active"), (ARCHIVED, "Archived")]

    fullname = models.CharField(max_length=150)
    birth_date = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, blank=True)
    address = models.CharField(max_length=150, blank=True)
    case_type = models.CharField(max_length=150, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tbl_guardian"

    def __str__(self):
        return self.fullname


class Child(models.Model):
    ACTIVE = "active"
    ARCHIVED = "archived"
    STATUS_CHOICES = [(ACTIVE, "Active"), (ARCHIVED, "Archived")]

    guardian = models.ForeignKey(
        Guardian, on_delete=models.SET_NULL, null=True, blank=True, related_name="children"
    )
    fullname = models.CharField(max_length=150)
    birth_date = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, blank=True)
    address = models.CharField(max_length=150, blank=True)
    case_type = models.CharField(max_length=150, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tbl_child"

    def __str__(self):
        return self.fullname
```

Replace `backend/children/admin.py`:
```python
from django.contrib import admin
from children.models import Guardian, Child

admin.site.register(Guardian)
admin.site.register(Child)
```

- [ ] **Step 4: Make and run migrations**

Run:
```bash
python manage.py makemigrations children
python manage.py migrate
```
Expected: migration created and applied.

- [ ] **Step 5: Run the test to verify it passes**

Run: `python manage.py test children`
Expected: PASS (1 test).

- [ ] **Step 6: Commit**

```bash
cd ..
git add backend/children
git commit -m "feat(children): Guardian and Child models"
cd backend
```

---

## Task 6: Guardian & Child API (CRUD + archive)

**Files:**
- Create: `backend/children/serializers.py`, `backend/children/urls.py`, `backend/children/tests/test_api.py`
- Modify: `backend/children/views.py`, `backend/config/urls.py`

- [ ] **Step 1: Write the failing test**

Create `backend/children/tests/test_api.py`:
```python
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from accounts.models import Role
from children.models import Guardian, Child

User = get_user_model()


class ChildApiTest(APITestCase):
    def setUp(self):
        self.staff_role = Role.objects.create(role_name=Role.STAFF)
        self.counselor_role = Role.objects.create(role_name=Role.COUNSELOR)
        self.staff = User.objects.create_user(
            email="staff@racco1.gov.ph", username="staff", password="staff1234",
            role=self.staff_role)
        self.counselor = User.objects.create_user(
            email="c@racco1.gov.ph", username="c", password="couns1234",
            role=self.counselor_role)

    def _auth(self, email, password):
        token = self.client.post("/api/auth/login/", {
            "email": email, "password": password}).data["access"]
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + token)

    def test_staff_can_create_child(self):
        self._auth("staff@racco1.gov.ph", "staff1234")
        resp = self.client.post("/api/children/", {
            "fullname": "Juan Cruz", "gender": "Male", "case_type": "Foster"})
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(Child.objects.filter(fullname="Juan Cruz").exists())

    def test_counselor_cannot_create_child(self):
        self._auth("c@racco1.gov.ph", "couns1234")
        resp = self.client.post("/api/children/", {"fullname": "X"})
        self.assertEqual(resp.status_code, 403)

    def test_archive_child_hides_from_list(self):
        self._auth("staff@racco1.gov.ph", "staff1234")
        child = Child.objects.create(fullname="Ana Lopez", case_type="Adoption")
        self.client.post(f"/api/children/{child.id}/archive/")
        names = [c["fullname"] for c in self.client.get("/api/children/").data]
        self.assertNotIn("Ana Lopez", names)

    def test_staff_can_create_guardian(self):
        self._auth("staff@racco1.gov.ph", "staff1234")
        resp = self.client.post("/api/guardians/", {
            "fullname": "Maria Cruz", "case_type": "Foster"})
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(Guardian.objects.filter(fullname="Maria Cruz").exists())
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python manage.py test children.tests.test_api`
Expected: FAIL (no `/api/children/` route).

- [ ] **Step 3: Create the serializers**

Create `backend/children/serializers.py`:
```python
from rest_framework import serializers
from children.models import Guardian, Child


class GuardianSerializer(serializers.ModelSerializer):
    class Meta:
        model = Guardian
        fields = [
            "id", "fullname", "birth_date", "gender", "address",
            "case_type", "status",
        ]


class ChildSerializer(serializers.ModelSerializer):
    guardian_name = serializers.CharField(source="guardian.fullname", read_only=True, default=None)

    class Meta:
        model = Child
        fields = [
            "id", "fullname", "birth_date", "gender", "address",
            "case_type", "status", "guardian", "guardian_name",
        ]
```

- [ ] **Step 4: Create the viewsets**

Replace `backend/children/views.py`:
```python
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from accounts.permissions import IsAdminOrStaff
from children.models import Guardian, Child
from children.serializers import GuardianSerializer, ChildSerializer


class _ArchivableViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminOrStaff]
    pagination_class = None
    model = None

    def get_queryset(self):
        qs = self.model.objects.all().order_by("fullname")
        if self.request.query_params.get("include_archived") != "true":
            qs = qs.exclude(status=self.model.ARCHIVED)
        return qs

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        obj = self.get_object()
        obj.status = self.model.ARCHIVED
        obj.save(update_fields=["status", "updated_at"])
        return Response({"status": "archived"}, status=status.HTTP_200_OK)


class GuardianViewSet(_ArchivableViewSet):
    model = Guardian
    serializer_class = GuardianSerializer


class ChildViewSet(_ArchivableViewSet):
    model = Child
    serializer_class = ChildSerializer
```

- [ ] **Step 5: Wire URLs**

Create `backend/children/urls.py`:
```python
from rest_framework.routers import DefaultRouter
from children.views import GuardianViewSet, ChildViewSet

router = DefaultRouter()
router.register("guardians", GuardianViewSet, basename="guardian")
router.register("children", ChildViewSet, basename="child")

urlpatterns = router.urls
```

Modify `backend/config/urls.py` — add the children include:
```python
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("accounts.urls")),
    path("api/", include("children.urls")),
]
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `python manage.py test children.tests.test_api`
Expected: PASS (4 tests).

- [ ] **Step 7: Run the full backend suite + commit**

Run: `python manage.py test`
Expected: all tests PASS (14 total).
```bash
cd ..
git add backend/children backend/config/urls.py
git commit -m "feat(children): Guardian and Child CRUD API with archive"
cd backend
```

---

## Task 7: Remaining assessment models (schema only)

**Files:**
- Modify: `backend/assessments/models.py`, `backend/assessments/admin.py`
- Create: `backend/assessments/tests/__init__.py`, `backend/assessments/tests/test_models.py`

- [ ] **Step 1: Write the failing test**

Create `backend/assessments/tests/__init__.py` (empty) and `backend/assessments/tests/test_models.py`:
```python
from django.test import TestCase
from django.contrib.auth import get_user_model
from accounts.models import Role
from children.models import Child
from assessments.models import (
    Questionnaire, Question, Assessment, Response, AssessmentResult, Recommendation,
)

User = get_user_model()


class AssessmentModelTest(TestCase):
    def test_full_assessment_chain(self):
        role = Role.objects.create(role_name=Role.COUNSELOR)
        counselor = User.objects.create_user(
            email="c@racco1.gov.ph", username="c", password="x", role=role)
        child = Child.objects.create(fullname="Juan", case_type="Foster")
        q = Questionnaire.objects.create(title="Ages 5-8", age_group="5-8")
        question = Question.objects.create(
            questionnaire=q, question_text="How do you feel?", question_type="emotion")
        a = Assessment.objects.create(
            child=child, counselor=counselor, assessment_type="Intake")
        Response.objects.create(assessment=a, question=question, answer="happy")
        result = AssessmentResult.objects.create(
            assessment=a, behavioral_score=12.5, classification="Needs Monitoring")
        rec = Recommendation.objects.create(
            result=result, recommendation_text="Schedule follow-up", priority_level="Medium")
        self.assertEqual(rec.result.assessment.child.fullname, "Juan")
        self.assertEqual(result.classification, "Needs Monitoring")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python manage.py test assessments`
Expected: FAIL (models do not exist).

- [ ] **Step 3: Define the models**

Replace `backend/assessments/models.py`:
```python
from django.conf import settings
from django.db import models
from children.models import Child


class Questionnaire(models.Model):
    title = models.CharField(max_length=150)
    age_group = models.CharField(max_length=50, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tbl_questionnaire"

    def __str__(self):
        return self.title


class Question(models.Model):
    questionnaire = models.ForeignKey(
        Questionnaire, on_delete=models.CASCADE, related_name="questions")
    question_text = models.TextField()
    question_type = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tbl_question"


class Assessment(models.Model):
    child = models.ForeignKey(Child, on_delete=models.CASCADE, related_name="assessments")
    counselor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="assessments")
    assessment_date = models.DateField(auto_now_add=True)
    assessment_type = models.CharField(max_length=50, blank=True)
    status = models.CharField(max_length=50, default="ongoing")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tbl_assessment"


class Response(models.Model):
    assessment = models.ForeignKey(
        Assessment, on_delete=models.CASCADE, related_name="responses")
    question = models.ForeignKey(Question, on_delete=models.PROTECT)
    answer = models.TextField(blank=True)

    class Meta:
        db_table = "tbl_response"


class AssessmentResult(models.Model):
    assessment = models.OneToOneField(
        Assessment, on_delete=models.CASCADE, related_name="result")
    behavioral_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    classification = models.CharField(max_length=50, blank=True)
    assessment_date = models.DateField(null=True, blank=True)
    assessment_type = models.CharField(max_length=50, blank=True)
    generated_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "tbl_assessment_result"


class Recommendation(models.Model):
    result = models.ForeignKey(
        AssessmentResult, on_delete=models.CASCADE, related_name="recommendations")
    recommendation_text = models.TextField(blank=True)
    priority_level = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "tbl_recommendation"
```

Replace `backend/assessments/admin.py`:
```python
from django.contrib import admin
from assessments.models import (
    Questionnaire, Question, Assessment, Response, AssessmentResult, Recommendation,
)

for m in (Questionnaire, Question, Assessment, Response, AssessmentResult, Recommendation):
    admin.site.register(m)
```

- [ ] **Step 4: Make and run migrations**

Run:
```bash
python manage.py makemigrations assessments
python manage.py migrate
```
Expected: migration created and applied.

- [ ] **Step 5: Run the test to verify it passes**

Run: `python manage.py test assessments`
Expected: PASS (1 test).

- [ ] **Step 6: Commit**

```bash
cd ..
git add backend/assessments
git commit -m "feat(assessments): questionnaire, assessment, result, recommendation models"
cd backend
```

---

## Task 8: Move the React prototype into `frontend/`

**Files:**
- Move: repo-root `src/`, `index.html`, `package.json`, `package-lock.json`, `vite.config.js`, `tailwind.config.js`, `postcss.config.js` → `frontend/`
- Modify: `.gitignore` (paths still match since they are not path-anchored)

- [ ] **Step 1: Move the frontend files**

Run (from repo root):
```bash
mkdir -p frontend
git mv index.html package.json package-lock.json vite.config.js tailwind.config.js postcss.config.js src frontend/
```
Move `node_modules` too (not tracked, so use a plain move):
```bash
mv node_modules frontend/ 2>/dev/null || true
```
Expected: `frontend/` now holds the app; repo root holds `frontend/`, `backend/`, `docs/`, `.gitignore`.

- [ ] **Step 2: Verify the frontend still builds**

Run:
```bash
cd frontend
npm install
npm run build
```
Expected: build succeeds (no errors).

- [ ] **Step 3: Commit**

```bash
cd ..
git add -A
git commit -m "chore(frontend): move React app into frontend/ for monorepo layout"
```

---

## Task 9: Frontend API client + Auth context

**Files:**
- Create: `frontend/.env`, `frontend/src/api/client.js`, `frontend/src/context/AuthContext.jsx`
- Modify: `frontend/package.json` (add axios)

- [ ] **Step 1: Install axios**

Run (from `frontend/`):
```bash
npm install axios
```
Expected: axios added to `package.json` dependencies.

- [ ] **Step 2: Create the env file**

Create `frontend/.env`:
```
VITE_API_BASE_URL=http://localhost:8000/api
```

- [ ] **Step 3: Create the API client**

Create `frontend/src/api/client.js`:
```javascript
import axios from 'axios';

const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';

const api = axios.create({ baseURL });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

let refreshing = null;

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config;
    const refresh = localStorage.getItem('refresh');
    if (error.response?.status === 401 && refresh && !original._retry) {
      original._retry = true;
      try {
        refreshing = refreshing || axios.post(`${baseURL}/auth/refresh/`, { refresh });
        const { data } = await refreshing;
        refreshing = null;
        localStorage.setItem('access', data.access);
        original.headers.Authorization = `Bearer ${data.access}`;
        return api(original);
      } catch (e) {
        refreshing = null;
        localStorage.removeItem('access');
        localStorage.removeItem('refresh');
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

export default api;
```

- [ ] **Step 4: Create the Auth context**

Create `frontend/src/context/AuthContext.jsx`:
```javascript
import React, { createContext, useContext, useEffect, useState } from 'react';
import api from '../api/client';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem('access');
    if (!token) { setLoading(false); return; }
    api.get('/auth/me/')
      .then((res) => setUser(res.data))
      .catch(() => { localStorage.removeItem('access'); localStorage.removeItem('refresh'); })
      .finally(() => setLoading(false));
  }, []);

  const login = async (email, password) => {
    const { data } = await api.post('/auth/login/', { email, password });
    localStorage.setItem('access', data.access);
    localStorage.setItem('refresh', data.refresh);
    setUser(data.user);
    return data.user;
  };

  const logout = () => {
    localStorage.removeItem('access');
    localStorage.removeItem('refresh');
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
```

- [ ] **Step 5: Verify it compiles**

Run: `npm run build`
Expected: build succeeds.

- [ ] **Step 6: Commit**

```bash
cd ..
git add frontend/src/api frontend/src/context frontend/package.json frontend/package-lock.json
git commit -m "feat(frontend): API client with JWT interceptors and auth context"
cd frontend
```

---

## Task 10: Login page + protected routes + role-based shell

**Files:**
- Create: `frontend/src/pages/Login.jsx`, `frontend/src/components/ProtectedRoute.jsx`
- Modify: `frontend/src/App.jsx`, `frontend/src/components/Sidebar.jsx`, `frontend/src/components/Topbar.jsx`, `frontend/src/main.jsx`

- [ ] **Step 1: Create the Login page**

Create `frontend/src/pages/Login.jsx`:
```javascript
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError(''); setBusy(true);
    try {
      await login(email, password);
      navigate('/');
    } catch (err) {
      setError('Invalid email or password.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <form onSubmit={submit} className="bg-white p-8 rounded-xl shadow-sm border w-full max-w-sm">
        <h1 className="text-xl font-bold text-brand-700 mb-1">NACC CWMS</h1>
        <p className="text-xs text-gray-500 mb-6">RACCO I — Sign in to your account</p>
        {error && <div className="mb-4 text-sm text-red-600 bg-red-50 border border-red-200 p-2 rounded">{error}</div>}
        <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
        <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required
          className="w-full border p-2.5 rounded-md mb-4 focus:ring-2 focus:ring-brand-500 outline-none" />
        <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required
          className="w-full border p-2.5 rounded-md mb-6 focus:ring-2 focus:ring-brand-500 outline-none" />
        <button type="submit" disabled={busy}
          className="w-full bg-brand-600 text-white py-2.5 rounded-lg font-bold hover:bg-brand-700 disabled:opacity-50 transition">
          {busy ? 'Signing in…' : 'Sign In'}
        </button>
      </form>
    </div>
  );
}
```

- [ ] **Step 2: Create ProtectedRoute**

Create `frontend/src/components/ProtectedRoute.jsx`:
```javascript
import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function ProtectedRoute({ children, roles }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="p-6 text-gray-500">Loading…</div>;
  if (!user) return <Navigate to="/login" replace />;
  if (roles && !roles.includes(user.role_name)) return <Navigate to="/" replace />;
  return children;
}
```

- [ ] **Step 3: Rewrite App.jsx with auth + role-based routes**

Replace `frontend/src/App.jsx`:
```javascript
import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import Sidebar from './components/Sidebar';
import Topbar from './components/Topbar';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Children from './pages/Children';
import Assessment from './pages/Assessment';
import Report from './pages/Report';
import Compliance from './pages/Compliance';
import Settings from './pages/Settings';

function Shell({ children }) {
  return (
    <div className="flex h-screen bg-gray-50 overflow-hidden font-sans">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Topbar />
        <main className="flex-1 overflow-y-auto">{children}</main>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<ProtectedRoute><Shell><Dashboard /></Shell></ProtectedRoute>} />
          <Route path="/children" element={<ProtectedRoute roles={['Administrator', 'Staff', 'Counselor']}><Shell><Children /></Shell></ProtectedRoute>} />
          <Route path="/assessment" element={<ProtectedRoute roles={['Administrator', 'Counselor']}><Shell><Assessment /></Shell></ProtectedRoute>} />
          <Route path="/report" element={<ProtectedRoute><Shell><Report /></Shell></ProtectedRoute>} />
          <Route path="/compliance" element={<ProtectedRoute><Shell><Compliance /></Shell></ProtectedRoute>} />
          {/* /users route is added in Task 11 together with the Users page */}
          <Route path="/settings" element={<ProtectedRoute><Shell><Settings /></Shell></ProtectedRoute>} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
```

- [ ] **Step 4: Update Sidebar for role-based links + current user**

Replace `frontend/src/components/Sidebar.jsx`:
```javascript
import React from 'react';
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, Users, ClipboardList, FileText, CheckSquare, Settings, UserCog } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export default function Sidebar() {
  const { user } = useAuth();
  const role = user?.role_name;

  const links = [
    { to: '/', icon: <LayoutDashboard size={20} />, label: 'Dashboard', roles: null },
    { to: '/children', icon: <Users size={20} />, label: 'Children Records', roles: ['Administrator', 'Staff', 'Counselor'] },
    { to: '/assessment', icon: <ClipboardList size={20} />, label: 'Assessment', roles: ['Administrator', 'Counselor'] },
    { to: '/report', icon: <FileText size={20} />, label: 'Counselor Report', roles: null },
    { to: '/compliance', icon: <CheckSquare size={20} />, label: 'Compliance', roles: null },
    { to: '/users', icon: <UserCog size={20} />, label: 'User Management', roles: ['Administrator'] },
    { to: '/settings', icon: <Settings size={20} />, label: 'Settings', roles: null },
  ].filter((l) => !l.roles || l.roles.includes(role));

  return (
    <div className="w-64 bg-white border-r h-screen overflow-y-auto flex flex-col">
      <div className="p-6 border-b">
        <h1 className="text-xl font-bold text-brand-700">NACC CWMS</h1>
        <p className="text-xs text-gray-500 mt-1">Child Welfare Mgmt</p>
      </div>
      <nav className="flex-1 p-4 space-y-2">
        {links.map((link) => (
          <NavLink key={link.to} to={link.to} end={link.to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                isActive ? 'bg-brand-50 text-brand-700' : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
              }`}>
            {link.icon}
            {link.label}
          </NavLink>
        ))}
      </nav>
      <div className="p-4 border-t">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-brand-100 flex items-center justify-center text-brand-700 font-bold">
            {(user?.first_name?.[0] || 'U')}{(user?.last_name?.[0] || '')}
          </div>
          <div>
            <p className="text-sm font-medium text-gray-800">{user?.fullname || user?.username}</p>
            <p className="text-xs text-gray-500">{role || '—'}</p>
          </div>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Update Topbar with a logout button**

Replace `frontend/src/components/Topbar.jsx` (preserve any existing markup, ensure it includes logout):
```javascript
import React from 'react';
import { LogOut } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export default function Topbar() {
  const { user, logout } = useAuth();
  return (
    <header className="h-16 bg-white border-b flex items-center justify-between px-6">
      <div className="text-sm text-gray-500">NACC-RACCO I — Behavioral Assessment & Counseling Support</div>
      <div className="flex items-center gap-4">
        <span className="text-sm text-gray-700">{user?.fullname || user?.username}</span>
        <button onClick={logout}
          className="flex items-center gap-2 text-sm text-gray-600 hover:text-red-600 transition">
          <LogOut size={18} /> Logout
        </button>
      </div>
    </header>
  );
}
```

- [ ] **Step 6: Manual verification (browser)**

Start the backend (terminal A, from `backend/`, venv active): `python manage.py runserver`
Start the frontend (terminal B, from `frontend/`): `npm run dev`
In the browser at `http://localhost:5173`:
1. You are redirected to `/login`.
2. Sign in with `admin@racco1.gov.ph` / `admin1234`.
3. Expected: redirected to the Dashboard; sidebar shows **User Management** (admin-only); topbar shows your name + Logout.
4. Click Logout → returns to `/login`.

- [ ] **Step 7: Commit**

```bash
cd ..
git add frontend/src
git commit -m "feat(frontend): login page, protected role-based routes, auth shell"
cd frontend
```

---

## Task 11: User Management page (Admin)

**Files:**
- Create: `frontend/src/pages/Users.jsx`

- [ ] **Step 1: Build the Users page**

Create `frontend/src/pages/Users.jsx`:
```javascript
import React, { useEffect, useState } from 'react';
import { X } from 'lucide-react';
import api from '../api/client';

const EMPTY = { email: '', username: '', first_name: '', last_name: '', middle_initial: '', contact_details: '', role: '', password: '' };

export default function Users() {
  const [users, setUsers] = useState([]);
  const [roles, setRoles] = useState([]);
  const [form, setForm] = useState(null); // null = closed, object = open
  const [error, setError] = useState('');

  const load = () => api.get('/users/').then((r) => setUsers(r.data));

  useEffect(() => {
    load();
    api.get('/roles/').then((r) => setRoles(r.data));
  }, []);

  const openCreate = () => { setError(''); setForm({ ...EMPTY }); };
  const openEdit = (u) => { setError(''); setForm({ ...EMPTY, ...u, password: '' }); };

  const save = async (e) => {
    e.preventDefault();
    setError('');
    try {
      const payload = { ...form };
      if (!payload.password) delete payload.password;
      if (form.id) await api.put(`/users/${form.id}/`, payload);
      else await api.post('/users/', payload);
      setForm(null);
      load();
    } catch (err) {
      setError(JSON.stringify(err.response?.data || 'Save failed'));
    }
  };

  const archive = async (u) => {
    if (!window.confirm(`Archive ${u.fullname || u.email}?`)) return;
    await api.post(`/users/${u.id}/archive/`);
    load();
  };

  return (
    <div className="p-6 relative">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold text-gray-800">User Management</h1>
        <button onClick={openCreate} className="bg-brand-600 text-white px-4 py-2 rounded-lg font-medium hover:bg-brand-700 transition">+ Add User</button>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
        <table className="w-full text-left">
          <thead>
            <tr className="bg-gray-50 border-b">
              <th className="p-3 text-sm font-semibold text-gray-600">Name</th>
              <th className="p-3 text-sm font-semibold text-gray-600">Email</th>
              <th className="p-3 text-sm font-semibold text-gray-600">Role</th>
              <th className="p-3 text-sm font-semibold text-gray-600">Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} className="border-b hover:bg-gray-50">
                <td className="p-3 text-sm font-medium text-gray-800">{u.fullname || u.username}</td>
                <td className="p-3 text-sm text-gray-600">{u.email}</td>
                <td className="p-3 text-sm text-gray-600">{u.role_name}</td>
                <td className="p-3 text-sm space-x-3">
                  <button onClick={() => openEdit(u)} className="text-brand-600 hover:underline">Edit</button>
                  <button onClick={() => archive(u)} className="text-red-600 hover:underline">Archive</button>
                </td>
              </tr>
            ))}
            {users.length === 0 && <tr><td colSpan="4" className="p-6 text-center text-gray-500">No users.</td></tr>}
          </tbody>
        </table>
      </div>

      {form && (
        <div className="fixed inset-0 bg-black/30 flex justify-end z-50">
          <form onSubmit={save} className="w-96 bg-white h-full shadow-2xl border-l flex flex-col">
            <div className="p-4 border-b flex justify-between items-center bg-gray-50">
              <h2 className="text-lg font-bold text-gray-800">{form.id ? 'Edit User' : 'Add User'}</h2>
              <button type="button" onClick={() => setForm(null)} className="p-1 hover:bg-gray-200 rounded-full text-gray-500"><X size={20} /></button>
            </div>
            <div className="p-6 flex-1 overflow-y-auto space-y-3">
              {error && <div className="text-xs text-red-600 bg-red-50 border border-red-200 p-2 rounded break-words">{error}</div>}
              {[['first_name', 'First Name'], ['middle_initial', 'Middle Initial'], ['last_name', 'Last Name'], ['username', 'Username'], ['email', 'Email'], ['contact_details', 'Contact Details']].map(([k, label]) => (
                <div key={k}>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
                  <input value={form[k] || ''} onChange={(e) => setForm({ ...form, [k]: e.target.value })}
                    className="w-full border p-2 rounded-md focus:ring-2 focus:ring-brand-500 outline-none" />
                </div>
              ))}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Role</label>
                <select value={form.role || ''} onChange={(e) => setForm({ ...form, role: e.target.value })}
                  className="w-full border p-2 rounded-md focus:ring-2 focus:ring-brand-500 outline-none">
                  <option value="">-- Select role --</option>
                  {roles.map((r) => <option key={r.id} value={r.id}>{r.role_name}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Password {form.id && <span className="text-gray-400">(leave blank to keep)</span>}</label>
                <input type="password" value={form.password || ''} onChange={(e) => setForm({ ...form, password: e.target.value })}
                  className="w-full border p-2 rounded-md focus:ring-2 focus:ring-brand-500 outline-none" />
              </div>
            </div>
            <div className="p-4 border-t bg-gray-50">
              <button type="submit" className="w-full bg-brand-600 text-white py-2 rounded-lg font-medium hover:bg-brand-700 transition">Save</button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Wire the Users page into the router**

In `frontend/src/App.jsx`, add the import alongside the other page imports:
```javascript
import Users from './pages/Users';
```
and replace the placeholder comment line with the route:
```javascript
          <Route path="/users" element={<ProtectedRoute roles={['Administrator']}><Shell><Users /></Shell></ProtectedRoute>} />
```

- [ ] **Step 3: Manual verification (browser)**

With both servers running, signed in as admin:
1. Go to **User Management**.
2. Click **+ Add User**, fill in name/email/username, pick a role, set a password, Save.
3. Expected: the new user appears in the table.
4. Log out, log in as the new user → confirm their sidebar matches their role.
5. Log back in as admin, **Archive** the test user → it disappears from the list, and that user can no longer log in.

- [ ] **Step 4: Commit**

```bash
cd ..
git add frontend/src/pages/Users.jsx frontend/src/App.jsx
git commit -m "feat(frontend): admin user management page + route"
cd frontend
```

---

## Task 12: Children & Guardian management wired to the API

**Files:**
- Modify: `frontend/src/pages/Children.jsx`

- [ ] **Step 1: Rewrite Children.jsx against the API**

Replace `frontend/src/pages/Children.jsx`:
```javascript
import React, { useEffect, useState } from 'react';
import { X } from 'lucide-react';
import api from '../api/client';
import { useAuth } from '../context/AuthContext';

const EMPTY = { fullname: '', birth_date: '', gender: '', address: '', case_type: '', guardian: '' };

export default function Children() {
  const { user } = useAuth();
  const canManage = ['Administrator', 'Staff'].includes(user?.role_name);
  const [children, setChildren] = useState([]);
  const [guardians, setGuardians] = useState([]);
  const [search, setSearch] = useState('');
  const [form, setForm] = useState(null);
  const [error, setError] = useState('');

  const load = () => {
    api.get('/children/').then((r) => setChildren(r.data));
    api.get('/guardians/').then((r) => setGuardians(r.data));
  };
  useEffect(() => { load(); }, []);

  const filtered = children.filter((c) => c.fullname.toLowerCase().includes(search.toLowerCase()));

  const openCreate = () => { setError(''); setForm({ ...EMPTY }); };
  const openEdit = (c) => { setError(''); setForm({ ...EMPTY, ...c, guardian: c.guardian || '' }); };

  const save = async (e) => {
    e.preventDefault();
    setError('');
    const payload = { ...form };
    if (!payload.guardian) payload.guardian = null;
    if (!payload.birth_date) delete payload.birth_date;
    try {
      if (form.id) await api.put(`/children/${form.id}/`, payload);
      else await api.post('/children/', payload);
      setForm(null);
      load();
    } catch (err) {
      setError(JSON.stringify(err.response?.data || 'Save failed'));
    }
  };

  const archive = async (c) => {
    if (!window.confirm(`Archive ${c.fullname}?`)) return;
    await api.post(`/children/${c.id}/archive/`);
    load();
  };

  return (
    <div className="p-6 relative">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold text-gray-800">Children Records</h1>
        {canManage && <button onClick={openCreate} className="bg-brand-600 text-white px-4 py-2 rounded-lg font-medium hover:bg-brand-700 transition">+ Add Child</button>}
      </div>

      <div className="bg-white p-4 rounded-xl shadow-sm border border-gray-100">
        <input type="text" placeholder="Search children..." value={search} onChange={(e) => setSearch(e.target.value)}
          className="border p-2 rounded-md w-full max-w-sm mb-4 focus:outline-brand-500" />
        <table className="w-full text-left border-collapse min-w-max">
          <thead>
            <tr className="bg-gray-50 border-b">
              <th className="p-3 text-sm font-semibold text-gray-600">Name</th>
              <th className="p-3 text-sm font-semibold text-gray-600">Gender</th>
              <th className="p-3 text-sm font-semibold text-gray-600">Case Type</th>
              <th className="p-3 text-sm font-semibold text-gray-600">Guardian</th>
              {canManage && <th className="p-3 text-sm font-semibold text-gray-600">Actions</th>}
            </tr>
          </thead>
          <tbody>
            {filtered.map((child) => (
              <tr key={child.id} className="border-b hover:bg-brand-50 transition-colors">
                <td className="p-3 text-sm font-semibold text-brand-600">{child.fullname}</td>
                <td className="p-3 text-sm text-gray-600">{child.gender || '—'}</td>
                <td className="p-3 text-sm text-gray-600">{child.case_type || '—'}</td>
                <td className="p-3 text-sm text-gray-600">{child.guardian_name || '—'}</td>
                {canManage && (
                  <td className="p-3 text-sm space-x-3">
                    <button onClick={() => openEdit(child)} className="text-brand-600 hover:underline">Edit</button>
                    <button onClick={() => archive(child)} className="text-red-600 hover:underline">Archive</button>
                  </td>
                )}
              </tr>
            ))}
            {filtered.length === 0 && <tr><td colSpan={canManage ? 5 : 4} className="p-6 text-center text-gray-500">No records found.</td></tr>}
          </tbody>
        </table>
      </div>

      {form && (
        <div className="fixed inset-0 bg-black/30 flex justify-end z-50">
          <form onSubmit={save} className="w-96 bg-white h-full shadow-2xl border-l flex flex-col">
            <div className="p-4 border-b flex justify-between items-center bg-gray-50">
              <h2 className="text-lg font-bold text-gray-800">{form.id ? 'Edit Child' : 'Add Child'}</h2>
              <button type="button" onClick={() => setForm(null)} className="p-1 hover:bg-gray-200 rounded-full text-gray-500"><X size={20} /></button>
            </div>
            <div className="p-6 flex-1 overflow-y-auto space-y-3">
              {error && <div className="text-xs text-red-600 bg-red-50 border border-red-200 p-2 rounded break-words">{error}</div>}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Full Name</label>
                <input value={form.fullname} onChange={(e) => setForm({ ...form, fullname: e.target.value })} required
                  className="w-full border p-2 rounded-md focus:ring-2 focus:ring-brand-500 outline-none" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Birth Date</label>
                <input type="date" value={form.birth_date || ''} onChange={(e) => setForm({ ...form, birth_date: e.target.value })}
                  className="w-full border p-2 rounded-md focus:ring-2 focus:ring-brand-500 outline-none" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Gender</label>
                <select value={form.gender} onChange={(e) => setForm({ ...form, gender: e.target.value })}
                  className="w-full border p-2 rounded-md focus:ring-2 focus:ring-brand-500 outline-none">
                  <option value="">--</option><option>Male</option><option>Female</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Address</label>
                <input value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })}
                  className="w-full border p-2 rounded-md focus:ring-2 focus:ring-brand-500 outline-none" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Case Type</label>
                <input value={form.case_type} onChange={(e) => setForm({ ...form, case_type: e.target.value })}
                  placeholder="e.g. Foster, Adoption, Residential"
                  className="w-full border p-2 rounded-md focus:ring-2 focus:ring-brand-500 outline-none" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Guardian</label>
                <select value={form.guardian || ''} onChange={(e) => setForm({ ...form, guardian: e.target.value })}
                  className="w-full border p-2 rounded-md focus:ring-2 focus:ring-brand-500 outline-none">
                  <option value="">-- None --</option>
                  {guardians.map((g) => <option key={g.id} value={g.id}>{g.fullname}</option>)}
                </select>
              </div>
            </div>
            <div className="p-4 border-t bg-gray-50">
              <button type="submit" className="w-full bg-brand-600 text-white py-2 rounded-lg font-medium hover:bg-brand-700 transition">Save</button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Manual verification (browser)**

Signed in as admin (or a Staff user):
1. Go to **Children Records**, click **+ Add Child**, fill in the form, Save.
2. Expected: the child appears in the table, persisted (refresh the page — still there).
3. Edit the child, change the case type, Save → change persists.
4. Archive the child → it disappears from the list.
5. Log in as a **Counselor** → the page is read-only (no Add/Edit/Archive buttons).

- [ ] **Step 3: Commit**

```bash
cd ..
git add frontend/src/pages/Children.jsx
git commit -m "feat(frontend): children & guardian management wired to API"
cd frontend
```

---

## Task 13: Trim mock data, add README, final verification

**Files:**
- Modify: `frontend/src/data/mockData.js`, `frontend/src/pages/Assessment.jsx`
- Create: `README.md` (repo root)

- [ ] **Step 1: Trim mockData to dashboard-only demo data**

The Dashboard still uses `summaryMetrics`, `caseTrends`, and `mockActivityFeed` (real dashboard data arrives in Phase 4). Remove only `mockChildren`, which is no longer used. Edit `frontend/src/data/mockData.js` to delete the `mockChildren` export (keep the other three exports).

- [ ] **Step 2: Detach Assessment.jsx from mockChildren**

`Assessment.jsx` imports `mockChildren`. Replace its child source with a live fetch. In `frontend/src/pages/Assessment.jsx`:
- Remove `import { mockChildren } from '../data/mockData';`
- Add `import api from '../api/client';` and `import { useEffect } from 'react';` (merge with existing React import).
- Add state + load near the other `useState` calls:
```javascript
const [children, setChildren] = useState([]);
useEffect(() => { api.get('/children/').then((r) => setChildren(r.data)); }, []);
```
- In Step 1's `<select>`, change `{mockChildren.map(c => (` to `{children.map(c => (` and the option to:
```javascript
<option key={c.id} value={c.id}>{c.fullname} ({c.case_type || 'n/a'})</option>
```
(The fake AI scoring in this wizard is replaced for real in Phase 3; this step only removes the mock dependency so the build is clean.)

- [ ] **Step 3: Verify the frontend builds with no unused mock imports**

Run (from `frontend/`): `npm run build`
Expected: build succeeds with no "mockChildren is not defined" errors.

- [ ] **Step 4: Create the README**

Create `README.md` at the repo root:
```markdown
# NACC-RACCO I — AI-Integrated Child Behavioral Assessment & Counseling Support System

Monorepo: `backend/` (Django REST API) + `frontend/` (React + Vite + Tailwind).
See `docs/superpowers/specs/` for the design and `docs/superpowers/plans/` for phase plans.

## Backend
```bash
cd backend
python -m venv venv
# activate: PowerShell ./venv/Scripts/Activate.ps1  |  Git Bash source venv/Scripts/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py seed_initial_data   # creates roles + admin@racco1.gov.ph / admin1234
python manage.py runserver
```

## Frontend
```bash
cd frontend
npm install
npm run dev   # http://localhost:5173
```

## Tests
```bash
cd backend && python manage.py test
```
```

- [ ] **Step 5: Full backend test run**

Run (from `backend/`, venv active): `python manage.py test`
Expected: all tests PASS (15 total: models, auth, users, roles, children, assessments).

- [ ] **Step 6: End-to-end smoke test (browser)**

With both servers running and `seed_initial_data` applied:
1. Log in as admin → Dashboard loads, sidebar shows all sections incl. User Management.
2. Create a Staff user → log in as them → can manage children, cannot see User Management.
3. Create a child as Staff → persists across refresh.
4. Create a Counselor → log in → Children page is read-only.
5. Logout works from every role.

- [ ] **Step 7: Final commit**

```bash
cd ..
git add frontend/src/data/mockData.js frontend/src/pages/Assessment.jsx README.md
git commit -m "chore: trim mock data, detach assessment from mock, add README"
git push
```

---

## Definition of Done (Phase 1)
- [ ] Backend runs; `python manage.py test` passes (15 tests).
- [ ] All 10 capstone tables exist as Django models and are migrated.
- [ ] Login works by email/password; archived users cannot log in.
- [ ] Admin can create/edit/archive users with roles.
- [ ] Admin/Staff can create/edit/archive children + guardians, persisted in the DB.
- [ ] Counselor has read-only access to children; only Admin sees User Management.
- [ ] Frontend no longer depends on `mockChildren`; build is clean.
- [ ] Everything committed and pushed to the GitHub repo.
```
