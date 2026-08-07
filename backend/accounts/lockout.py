"""Login brute-force protection (cache-based, no DB models).

Failed-login counters and locks live in Django's default cache
(LocMemCache — see CACHES in settings, which is unset so Django falls
back to it). That means counters reset on process restart and are NOT
shared across processes/workers. Acceptable for this system's
single-process office deployment; if this is ever run behind multiple
app-server workers, point CACHES at Redis or Memcached instead so every
worker sees the same counters.
"""

import time

from django.conf import settings
from django.core.cache import cache

_PREFIX = "login-lock:"


def _norm_email(email):
    return (email or "").strip().lower()


def client_ip(request):
    """Client IP used for lockout keying.

    The office deployment has no reverse proxy in front of Django, so
    REMOTE_ADDR is the real client address. X-Forwarded-For is
    deliberately NOT trusted — a client can set that header to whatever
    it likes, which would let an attacker pick their own lockout bucket.
    """
    return request.META.get("REMOTE_ADDR", "")


def _combo_counter_key(email, ip):
    return f"{_PREFIX}count:{_norm_email(email)}:{ip}"


def _combo_lock_key(email, ip):
    return f"{_PREFIX}lock:{_norm_email(email)}:{ip}"


def _ip_counter_key(ip):
    return f"{_PREFIX}ipcount:{ip}"


def _ip_lock_key(ip):
    return f"{_PREFIX}iplock:{ip}"


def _window_seconds():
    return settings.LOGIN_LOCKOUT_MINUTES * 60


def _remaining(lock_key):
    """Seconds left on a lock key, or 0 if it's unset/already expired."""
    unlock_at = cache.get(lock_key)
    if not unlock_at:
        return 0
    remaining = int(round(unlock_at - time.time()))
    return remaining if remaining > 0 else 0


def is_locked(email, ip):
    """Whether a login attempt for this email+IP should be blocked right now.

    Checks the email+IP lock (this specific combo failed too often) and
    the IP-wide lock (this IP failed too often across many different
    emails — a spray attack). Returns (locked, retry_after_seconds); when
    both locks are active, retry_after is the longer of the two.
    """
    retry_after = max(_remaining(_combo_lock_key(email, ip)), _remaining(_ip_lock_key(ip)))
    return retry_after > 0, retry_after


def _bump(counter_key):
    """Increment a rolling-window counter, creating it on first use.

    LocMemCache's incr() raises ValueError on a missing key, and two
    near-simultaneous first failures could both race to create it. This
    is a single-process deployment, so a plain get-then-set is enough —
    worst case on a genuine race is losing one increment, which doesn't
    meaningfully weaken the lockout.
    """
    count = (cache.get(counter_key) or 0) + 1
    cache.set(counter_key, count, timeout=_window_seconds())
    return count


def register_failure(email, ip):
    """Record a failed login attempt against both the combo and IP counters.

    Returns (locked, retry_after_seconds, new_lockout). `new_lockout` is
    True only on the attempt that just crossed a threshold, so the caller
    can log the lockout exactly once — once a lock exists, is_locked()
    blocks the request before this function is called again for the same
    combo/IP, so it never fires twice for the same lockout.
    """
    combo_count = _bump(_combo_counter_key(email, ip))
    ip_count = _bump(_ip_counter_key(ip))

    new_lockout = False
    retry_after = 0
    unlock_at = time.time() + _window_seconds()

    if combo_count >= settings.LOGIN_MAX_ATTEMPTS:
        if cache.add(_combo_lock_key(email, ip), unlock_at, timeout=_window_seconds()):
            new_lockout = True
        retry_after = max(retry_after, _window_seconds())

    if ip_count >= settings.LOGIN_IP_MAX_ATTEMPTS:
        if cache.add(_ip_lock_key(ip), unlock_at, timeout=_window_seconds()):
            new_lockout = True
        retry_after = max(retry_after, _window_seconds())

    return retry_after > 0, retry_after, new_lockout


def clear_failures(email, ip):
    """Reset the email+IP counter on a successful login.

    The IP-wide counter is deliberately left alone — one successful login
    from an IP shouldn't reset the count for a spray attack still running
    against other accounts from that same IP.
    """
    cache.delete(_combo_counter_key(email, ip))
