"""Health endpoint for the cloud platform's load balancer.

Deliberately a plain Django view rather than a DRF one: platform health checks
are unauthenticated, and DRF's default permission class is IsAuthenticated.
It carries no data about the agency or its children — just enough to tell a
booting container from a healthy one.
"""

from django.conf import settings
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt


def _database_identity():
    """Which database this container actually reached — engine and host.

    `{"database": "ok"}` on its own was not enough. A demo deployment came up
    with DATABASE_URL unset, fell through to the zero-config SQLite path, and
    reported healthy for hours while writing to a file the platform destroys on
    every deploy. Naming what was reached makes that visible at a glance.

    The host is deployment detail and safe to expose here. The credential is
    not, and is never read.
    """
    cfg = settings.DATABASES.get("default", {})
    engine = str(cfg.get("ENGINE", "")).rsplit(".", 1)[-1] or "unknown"
    host = str(cfg.get("HOST", "") or "")
    if not host:
        # SQLite has no host; the file path is the identifying thing, and its
        # basename is enough to tell "on disk" from "a real server".
        name = str(cfg.get("NAME", "") or "")
        host = f"file:{name.rsplit('/', 1)[-1].rsplit(chr(92), 1)[-1]}" if name else "local"
    return engine, host


@csrf_exempt
def healthz(request):
    """200 when the app can reach its database, 503 otherwise.

    The database check matters: a container whose app code booted fine but
    whose DATABASE_URL is wrong would otherwise pass a bare liveness probe and
    take live traffic, returning 500s to staff instead of failing the deploy.
    """
    engine, host = _database_identity()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception as exc:  # noqa: BLE001 - any DB failure means "not ready"
        return JsonResponse(
            {"status": "unhealthy", "database": "unreachable",
             "engine": engine, "host": host, "detail": str(exc)[:200]},
            status=503,
        )
    return JsonResponse({"status": "ok", "database": "ok",
                         "engine": engine, "host": host})
