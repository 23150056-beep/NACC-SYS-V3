from django.core.cache import cache
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model

from accounts import lockout
from accounts.models import Role
from activity.models import ActivityLog

User = get_user_model()

EMAIL = "staff@racco1.gov.ph"
PASSWORD = "staff1234"
IP = "127.0.0.1"  # Django test client's default REMOTE_ADDR


class LoginLockoutTest(APITestCase):
    """accounts.lockout wired into LoginView. Cache state is process-global
    (LocMemCache), so it's cleared before AND after every test — otherwise
    counters from one test would leak into the next."""

    def setUp(self):
        cache.clear()
        self.role = Role.objects.create(role_name=Role.STAFF)
        self.user = User.objects.create_user(
            email=EMAIL, username="staff", password=PASSWORD, role=self.role)

    def tearDown(self):
        cache.clear()

    def _login(self, email=EMAIL, password="wrongpass"):
        return self.client.post("/api/auth/login/", {"email": email, "password": password})

    # ---- core lockout behavior ----

    def test_normal_login_still_works(self):
        resp = self._login(password=PASSWORD)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("access", resp.data)

    def test_sixth_attempt_locked_even_with_correct_password(self):
        for _ in range(5):
            self.assertEqual(self._login().status_code, 401)
        resp = self._login(password=PASSWORD)
        self.assertEqual(resp.status_code, 429)
        self.assertIn("Try again in", resp.data["detail"])

    def test_successful_login_before_threshold_clears_counter(self):
        for _ in range(4):
            self.assertEqual(self._login().status_code, 401)
        self.assertEqual(self._login(password=PASSWORD).status_code, 200)
        for _ in range(4):
            self.assertEqual(self._login().status_code, 401)
        # Still not locked — the success reset the combo counter.
        locked, _retry_after = lockout.is_locked(EMAIL, IP)
        self.assertFalse(locked)
        self.assertEqual(self._login(password=PASSWORD).status_code, 200)

    def test_lock_expires(self):
        for _ in range(5):
            self._login()
        self.assertEqual(self._login(password=PASSWORD).status_code, 429)

        # Simulate the lock's TTL elapsing rather than sleeping 15 minutes.
        cache.delete(lockout._combo_lock_key(EMAIL, IP))

        resp = self._login(password=PASSWORD)
        self.assertEqual(resp.status_code, 200)

    def test_unknown_email_failures_count_and_lock(self):
        unknown = "nobody@racco1.gov.ph"
        for _ in range(5):
            resp = self._login(email=unknown)
            self.assertEqual(resp.status_code, 401)
        resp = self._login(email=unknown, password="whatever")
        self.assertEqual(resp.status_code, 429)

    def test_ip_wide_lockout_across_many_emails(self):
        for i in range(20):
            resp = self._login(email=f"nouser{i}@racco1.gov.ph")
            self.assertEqual(resp.status_code, 401)
        # A brand-new email from the same IP is still blocked by the IP-wide lock.
        resp = self._login(email="yet-another@racco1.gov.ph")
        self.assertEqual(resp.status_code, 429)
        # Even the legitimate user with the correct password is blocked.
        resp = self._login(password=PASSWORD)
        self.assertEqual(resp.status_code, 429)

    def test_lockout_logs_activity_exactly_once(self):
        for _ in range(5):
            self._login()
        # Further blocked attempts must not add more log entries.
        for _ in range(3):
            self._login()

        logs = ActivityLog.objects.filter(
            category=ActivityLog.SECURITY, entity_label__contains="Login locked")
        self.assertEqual(logs.count(), 1)
        self.assertIn(EMAIL, logs.first().entity_label)
