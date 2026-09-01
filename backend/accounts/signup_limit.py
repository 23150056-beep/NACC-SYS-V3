"""Abuse control for the two open sign-up paths.

POST /api/auth/google/ and POST /api/auth/signup/ are the only endpoints in
this system that both accept anonymous traffic and write a row. Neither has a
domain allowlist doing any work — RACCO I staff use personal Google accounts —
which means anyone on the internet can create approval requests.

Both paths share these limits, and they must: two doors with one budget
between them, or the cheaper door is simply the one an abuser uses.

The harm is not storage. It is that an administrator wading through a hundred
plausible-looking fake requests eventually approves one by mistake, and that
approval is the only access control standing between a stranger and child case
records. So the limits below exist to keep the queue reviewable by a human, not
to save disk.

Two limits, deliberately different in kind:

* Per-IP, in the cache. Cheap and self-resetting, and it catches a naive flood.
  It inherits LocMemCache's weaknesses (see lockout.py): counters are
  per-worker and wiped on restart, and this deployment runs two Gunicorn
  workers, so the effective allowance is roughly double the number below. A
  speed bump, not a wall.
* A global ceiling on outstanding requests, counted in the database. Durable,
  shared across workers, and survives restarts — because it asks the source of
  truth rather than a cache. This is the one that actually holds, and it is
  why the weaker limit above is acceptable.

Both are deliberately generous. A limit that blocks a genuine new psychologist
on their first day is a worse failure than a queue with some junk in it: the
junk is visible and reversible, the lockout is neither.
"""

from django.conf import settings
from django.core.cache import cache

_PREFIX = "signup:"


def _key(ip):
    return f"{_PREFIX}count:{ip or 'unknown'}"


def _window_seconds():
    return settings.SIGNUP_WINDOW_MINUTES * 60


def attempts_from(ip):
    return cache.get(_key(ip)) or 0


def ip_is_throttled(ip):
    """Whether this address has already opened its allowance of requests."""
    return attempts_from(ip) >= settings.SIGNUP_MAX_PER_IP


def register_attempt(ip):
    """Count one newly created request against this address.

    Only successful creations are counted, not every call to the endpoint: a
    returning applicant checking whether they have been approved yet must not
    burn through the allowance and lock themselves out of their own status.
    """
    count = attempts_from(ip) + 1
    cache.set(_key(ip), count, timeout=_window_seconds())
    return count


def queue_is_full():
    """Whether outstanding requests have reached the global ceiling.

    Imported here rather than at module scope to keep this module importable
    from settings-adjacent code without dragging in the model layer.
    """
    from accounts.models import User

    return (User.objects.filter(status=User.PENDING).count()
            >= settings.SIGNUP_MAX_PENDING)
