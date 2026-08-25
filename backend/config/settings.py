"""
Django settings for config project (NACC-RACCO I system).

V3 is cloud-hosted. Everything that differs between a laptop, a staging
deploy and production comes from environment variables — the container image
is identical in all three. Defaults are the *development* values so that a
bare `python manage.py runserver` still works with no .env at all; production
overrides them explicitly (see docs/CLOUD-DEPLOYMENT.md).
"""

import os
from pathlib import Path
from datetime import timedelta

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def env_list(name, default=""):
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


DEBUG = env_bool("DJANGO_DEBUG", True)

# The dev key is a known constant, so a production deploy that forgets to set
# DJANGO_SECRET_KEY must fail loudly at boot rather than silently signing
# session cookies and JWTs with a public value.
DEV_SECRET_KEY = "dev-insecure-secret-key-change-me-in-production"
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", DEV_SECRET_KEY)
if not DEBUG and SECRET_KEY == DEV_SECRET_KEY:
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY must be set to a unique random value when "
        "DJANGO_DEBUG=False. Generate one with: "
        "python -c \"from django.core.management.utils import get_random_secret_key as k; print(k())\""
    )

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")

# Render injects the service's public hostname at runtime; the same trick works
# for any platform that exposes its hostname through an env var.
for _host_var in ("RENDER_EXTERNAL_HOSTNAME", "PLATFORM_EXTERNAL_HOSTNAME"):
    _host = os.getenv(_host_var)
    if _host and _host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(_host)

# Container platforms health-check the app over its internal IP, which never
# matches ALLOWED_HOSTS. /healthz/ is exempted in config.health instead of
# opening up the host allowlist.


# Application definition

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
    "locations",
    "clinical",
    "scheduling",
    "activity",
    "samd",
    "assistant",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    # WhiteNoise serves collected static files (the Django admin, mainly)
    # directly from the app container — no separate web server or CDN needed.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# Database
# Cloud platforms hand out a single DATABASE_URL, so that wins when present.
# The DB_ENGINE=postgres path is kept for on-premises installs that predate V3,
# and SQLite remains the zero-config fallback so tests and a fresh checkout
# never block on a database server.
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=int(os.getenv("DB_CONN_MAX_AGE", "600")),
            conn_health_checks=True,
            ssl_require=env_bool("DB_SSL_REQUIRE", False),
        )
    }
elif os.getenv("DB_ENGINE", "sqlite") == "postgres":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("DB_NAME", "nacc_v3"),
            "USER": os.getenv("DB_USER", "postgres"),
            "PASSWORD": os.getenv("DB_PASSWORD", ""),
            "HOST": os.getenv("DB_HOST", "localhost"),
            "PORT": os.getenv("DB_PORT", "5432"),
            "CONN_MAX_AGE": int(os.getenv("DB_CONN_MAX_AGE", "600")),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_USER_MODEL = "accounts.User"


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Manila"
USE_I18N = True
USE_TZ = True


# Static files (Django admin + DRF browsable API assets).
STATIC_URL = "static/"
STATIC_ROOT = Path(os.getenv("STATIC_ROOT", BASE_DIR / "staticfiles"))

# Uploaded files (psychological reports, signed consent scans, child photos).
# Served only through authenticated API endpoints — MEDIA_URL is not exposed
# via urlpatterns, and the S3 bucket below stays private for the same reason.
MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", BASE_DIR / "media"))
MEDIA_URL = "media/"
FILE_UPLOAD_MAX_MEMORY_SIZE = int(
    os.getenv("FILE_UPLOAD_MAX_MB", "15")
) * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = FILE_UPLOAD_MAX_MEMORY_SIZE

# Cloud containers have ephemeral disks: anything written to MEDIA_ROOT is lost
# on the next deploy. USE_S3=true switches uploads to S3-compatible object
# storage (AWS S3, Cloudflare R2, Backblaze B2, Supabase Storage...). All file
# access in the app goes through Django's storage API, so nothing else changes.
USE_S3 = env_bool("USE_S3", False)
if USE_S3:
    # boto3 >= 1.36 defaults request_checksum_calculation to "when_supported",
    # which attaches CRC32 checksum headers to every upload. AWS S3 accepts
    # them; Cloudflare R2 and Backblaze B2 reject them, so an otherwise correct
    # configuration fails on the very first file with an opaque error and looks
    # like bad credentials. Restoring the older behaviour costs nothing on AWS,
    # which is why it is unconditional rather than an R2 special case.
    # setdefault, so an operator can still override it from the environment.
    os.environ.setdefault("AWS_REQUEST_CHECKSUM_CALCULATION", "when_required")
    os.environ.setdefault("AWS_RESPONSE_CHECKSUM_VALIDATION", "when_supported")

    from config.storages import s3_storage_options

    _default_storage = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": s3_storage_options(),
    }
else:
    _default_storage = {"BACKEND": "django.core.files.storage.FileSystemStorage"}

STORAGES = {
    "default": _default_storage,
    "staticfiles": {
        "BACKEND": (
            "config.storages.WhiteNoiseStaticFilesStorage"
            if not DEBUG
            else "django.contrib.staticfiles.storage.StaticFilesStorage"
        )
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# Django REST Framework
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "accounts.authentication.ForcePasswordChangeJWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
}

# --- Google Sign-In (staff and psychologists) -----------------------------
#
# Unset = the feature is off and the login page shows only the password form.
# The client ID is public (it ships inside any page that renders the Google
# button); it lives in the environment so the feature can be switched on or
# off without a rebuild.
#
# Accounts are never created by signing in — an Administrator creates the user
# with the correct role first, and Google only replaces the password for that
# already-authorised account. See accounts/google_auth.py.
GOOGLE_OAUTH_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip()

# Optional allowlist of email domains, e.g. "racco1.gov.ph". Empty means any
# Google address may be used, provided an account already exists for it.
GOOGLE_ALLOWED_DOMAINS = [
    d.strip().lower() for d in env_list("GOOGLE_ALLOWED_DOMAINS")
]


# Login brute-force protection (accounts.lockout) — cache-based, no DB models.
LOGIN_MAX_ATTEMPTS = 5       # failed attempts for one email+IP before that combo locks
LOGIN_IP_MAX_ATTEMPTS = 20   # failed attempts from one IP (any/many emails) before the IP locks
LOGIN_LOCKOUT_MINUTES = 15   # both the rolling counting window and the lock duration

# Google sign-up abuse control (accounts.signup_limit). Sign-up is open to any
# Google address, so these keep the approval queue reviewable by a human — an
# administrator scrolling past a hundred fakes is how a real one gets approved
# by mistake. Deliberately generous: blocking a genuine new psychologist on
# their first day is worse than some junk in a queue an admin can see and
# decline.
SIGNUP_MAX_PER_IP = 5        # new access requests from one IP per window
SIGNUP_WINDOW_MINUTES = 60
SIGNUP_MAX_PENDING = 50      # global ceiling on outstanding requests (DB-counted)

CORS_ALLOWED_ORIGINS = env_list(
    "CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
)
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")
for _host_var in ("RENDER_EXTERNAL_HOSTNAME", "PLATFORM_EXTERNAL_HOSTNAME"):
    _host = os.getenv(_host_var)
    if _host and f"https://{_host}" not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(f"https://{_host}")


# HTTPS / transport hardening. Only applied outside DEBUG so local development
# over plain http:// keeps working.
if not DEBUG:
    # The app sits behind the platform's TLS terminator, so Django learns the
    # original scheme from the proxy header rather than the socket.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
    SECURE_REDIRECT_EXEMPT = [r"^healthz/?$"]
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"
    X_FRAME_OPTIONS = "DENY"


# Logging: containers have no log files, only stdout/stderr, which the platform
# collects. Keep it plain so the platform's log viewer stays readable.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "standard"},
    },
    "root": {"handlers": ["console"], "level": os.getenv("DJANGO_LOG_LEVEL", "INFO")},
    "loggers": {
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False},
    },
}

# --- Transactional mail (Brevo) -------------------------------------------
#
# One message only: "a case has been assigned to you", carrying the case
# number and nothing else. Brevo is a processor outside the agency's DPAs, so
# no child name or case detail is put in an email body — see the
# data-residency section of docs/CLOUD-DEPLOYMENT.md. Leave BREVO_API_KEY
# unset and the notification is skipped; nothing else changes.
BREVO_API_KEY = os.getenv("BREVO_API_KEY", "")
BREVO_SENDER_EMAIL = os.getenv("BREVO_SENDER_EMAIL", "racco1nacc@gmail.com")
BREVO_SENDER_NAME = os.getenv("BREVO_SENDER_NAME", "NACC RACCO1")
