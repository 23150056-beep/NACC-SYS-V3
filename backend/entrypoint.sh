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

# Reference data, not user data: the PSGC provinces, cities/municipalities and
# barangays the intake form picks from. Idempotent — it matches on the PSGC code
# and updates in place, so running it every deploy is how a newer dataset gets
# adopted. Without it the address dropdowns are empty.
echo "==> Loading PSGC addresses"
python manage.py seed_psgc

# Attaches PSGC codes to addresses that were typed before the picker existed.
# Only touches records with no codes yet, so an address a person chose in the
# form is never recomputed from its text. Safe on every deploy; a no-op once
# there is nothing left to match.
echo "==> Backfilling PSGC codes on existing addresses"
python manage.py backfill_psgc --apply

# --timeout is generous on purpose: uploading a large report and writing it to
# object storage happens inside the request cycle.
echo "==> Starting Gunicorn on port ${PORT:-8000}"
exec gunicorn config.wsgi:application \
    --bind "0.0.0.0:${PORT:-8000}" \
    --workers "${WEB_CONCURRENCY:-3}" \
    --timeout "${GUNICORN_TIMEOUT:-180}" \
    --graceful-timeout 30 \
    --access-logfile - \
    --error-logfile - \
    --log-level "${GUNICORN_LOG_LEVEL:-info}"
