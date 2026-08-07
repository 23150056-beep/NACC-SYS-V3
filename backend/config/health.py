"""Health endpoint for the cloud platform's load balancer.

Deliberately a plain Django view rather than a DRF one: platform health checks
are unauthenticated, and DRF's default permission class is IsAuthenticated.
It carries no data about the agency or its children — just enough to tell a
booting container from a healthy one.
"""

from django.db import connection
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt


@csrf_exempt
def healthz(request):
    """200 when the app can reach its database, 503 otherwise.

    The database check matters: a container whose app code booted fine but
    whose DATABASE_URL is wrong would otherwise pass a bare liveness probe and
    take live traffic, returning 500s to staff instead of failing the deploy.
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception as exc:  # noqa: BLE001 - any DB failure means "not ready"
        return JsonResponse(
            {"status": "unhealthy", "database": "unreachable", "detail": str(exc)[:200]},
            status=503,
        )
    return JsonResponse({"status": "ok", "database": "ok"})
