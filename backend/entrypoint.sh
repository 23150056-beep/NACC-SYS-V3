#!/usr/bin/env sh
#
# Container entrypoint: bring the schema up to date, then serve.
#
# `set -e` matters here — if migrate fails, the container must die so the
# platform's deploy fails visibly, rather than starting Gunicorn against a
# half-migrated database and serving 500s to staff.
set -e

echo "==> Applying database migrations"
python manage.py migrate --noinput

# First boot only: creates the roles and the default administrator. The command
# is idempotent, so leaving RUN_SEED=true set is harmless — it just prints
# "already present" on subsequent deploys.
if [ "${RUN_SEED:-false}" = "true" ]; then
    echo "==> Seeding roles and initial admin"
    python manage.py seed_initial_data
fi

# --timeout is generous on purpose: an AI draft is generated inside the request
# cycle and a slow model can take a minute or more. It must exceed
# AI_HOSTED_TIMEOUT (default 120s) or Gunicorn kills the worker mid-draft.
echo "==> Starting Gunicorn on port ${PORT:-8000}"
exec gunicorn config.wsgi:application \
    --bind "0.0.0.0:${PORT:-8000}" \
    --workers "${WEB_CONCURRENCY:-3}" \
    --timeout "${GUNICORN_TIMEOUT:-180}" \
    --graceful-timeout 30 \
    --access-logfile - \
    --error-logfile - \
    --log-level "${GUNICORN_LOG_LEVEL:-info}"
