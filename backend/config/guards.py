"""Configuration mistakes that otherwise look like a healthy deployment.

Pure predicates, so they can be tested without standing up a settings module.
`settings.py` calls them at import time: the first raises, the second warns.

Both come from a real deployment on 27 Aug 2026 that reported healthy and was
broken in three separate ways, none visible from outside. The shape they share
is the dangerous part — the service says "ok" and the application does not
work — so each one is made to say so instead.
"""
import logging

logger = logging.getLogger(__name__)


def sqlite_fallback_is_a_mistake(*, debug, database_url, db_engine):
    """True when a deployment is about to get an ephemeral SQLite file.

    SQLite is the zero-config fallback so a fresh checkout and the test suite
    never block on a database server. That is right for development and wrong
    for anything deployed: the file lives on the container's disk, which most
    platforms destroy on every deploy and every wake from sleep. Records are
    written, reported saved, and then quietly disappear.

    `/healthz/` cannot catch this. SQLite *is* a working database, so the
    health check passes while the deployment is losing everything.
    """
    if debug:
        return False
    if str(database_url or "").strip():
        return False
    # The on-premises path predating V3 configures Postgres piecemeal rather
    # than through a URL.
    return str(db_engine or "sqlite").strip() != "postgres"


# The defaults in settings.py. A deployment still carrying these has not had
# its origins configured.
_LOCAL_ORIGINS = frozenset({
    "http://localhost:5173", "http://127.0.0.1:5173",
    "http://localhost:3000", "http://127.0.0.1:3000",
})


def cors_is_unconfigured(*, debug, origins):
    """True when a deployment has no origin a browser will actually come from.

    Not fatal — an API with no browser client is a legitimate configuration —
    but it is worth saying out loud, because the failure is silent and
    confusing: `curl` works perfectly while every request from the frontend is
    blocked before it is sent, and the browser console blames CORS in a message
    that does not name the setting.
    """
    if debug:
        return False
    real = [o for o in (origins or []) if o and o not in _LOCAL_ORIGINS]
    return not real
