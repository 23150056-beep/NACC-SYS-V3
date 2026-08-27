# NACC SYS V3 — backend image (Django + Gunicorn)
#
# Build from the repository root:
#   docker build -f backend/Dockerfile -t nacc-backend ./backend
FROM python:3.12-slim

# Python in containers: no .pyc clutter, unbuffered stdout so the platform's
# log viewer shows output as it happens rather than when a buffer fills.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# curl is here for the container HEALTHCHECK below; everything else installs
# from wheels (psycopg[binary], Pillow, PyMuPDF), so no compiler is needed.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Dependencies first: this layer is cached until requirements.txt changes, so
# ordinary code edits rebuild in seconds instead of reinstalling everything.
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Bake static assets into the image so a booting container never has to write
# to disk before serving.
#
# Both values here are throwaways. collectstatic only renders the asset
# manifest — it never signs anything and never opens a database connection —
# and the real values arrive from the environment at runtime.
#
# DATABASE_URL has to be present because settings.py refuses to start with
# DJANGO_DEBUG=False and no database configured, rather than falling back to a
# SQLite file the platform destroys on every deploy. That guard is right, and
# it fires here too: importing settings runs it whether or not the command
# needs a database. A build-time placeholder satisfies it without weakening it.
# CORS_ALLOWED_ORIGINS is here only to keep the build log clean: settings.py
# warns when a non-debug configuration has no deployed origin, which is true
# and useful at runtime and meaningless during a build. Without it every
# successful build prints "every browser request from the frontend will be
# blocked", which is exactly the kind of alarming-but-irrelevant line that
# sends someone chasing a problem that is not there.
RUN DJANGO_DEBUG=False \
    DJANGO_SECRET_KEY=build-time-only-never-used-at-runtime \
    DATABASE_URL=postgresql://build:build@127.0.0.1:5432/build-time-only \
    CORS_ALLOWED_ORIGINS=https://build-time-only.invalid \
    python manage.py collectstatic --noinput

# Run as a non-root user: a container compromise should not also mean root
# inside the image. Ownership covers the media fallback directory for deploys
# that mount a volume instead of using S3.
RUN useradd --create-home --uid 10001 nacc \
    && mkdir -p /app/media \
    && chown -R nacc:nacc /app
USER nacc

EXPOSE 8000

# The platform's own health check is the authority; this one makes `docker ps`
# useful for local compose runs.
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PORT:-8000}/healthz/" || exit 1

ENTRYPOINT ["./entrypoint.sh"]
