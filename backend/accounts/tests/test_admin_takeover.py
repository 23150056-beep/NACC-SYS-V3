from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from accounts.models import Role

User = get_user_model()


class AdminTakeoverTest(APITestCase):
    """Single-admin handover (product decision 2026-07-18): creating a new
    Administrator marks a pending takeover; both admins stay active until the
    successor's FIRST login, which deactivates every other admin account. A
    deactivated admin can only return via a brand-new account."""

    def setUp(self):
        self.admin_role = Role.objects.create(role_name=Role.ADMINISTRATOR)
        self.staff_role = Role.objects.create(role_name=Role.STAFF)
        self.old_admin = User.objects.create_user(
            email="old@racco1.gov.ph", username="old", password="admin1234",
            role=self.admin_role)

    def _auth(self, email, password):
        token = self.client.post("/api/auth/login/", {
            "email": email, "password": password}).data["access"]
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + token)

    def _login(self, email, password):
        return self.client.post("/api/auth/login/", {"email": email, "password": password})

    def _create_successor(self):
        self._auth("old@racco1.gov.ph", "admin1234")
        resp = self.client.post("/api/users/", {
            "email": "new@racco1.gov.ph", "first_name": "New", "last_name": "Admin",
            "role": self.admin_role.id})
        self.assertEqual(resp.status_code, 201)
        return resp.data

    def test_creating_new_admin_marks_takeover_but_keeps_old_admin_active(self):
        data = self._create_successor()
        new_admin = User.objects.get(email="new@racco1.gov.ph")
        self.assertTrue(new_admin.admin_takeover_pending)
        self.assertTrue(data["admin_takeover_pending"])
        self.old_admin.refresh_from_db()
        self.assertEqual(self.old_admin.status, User.ACTIVE)
        self.assertTrue(self.old_admin.is_active)

    def test_creating_non_admin_does_not_mark_takeover(self):
        self._auth("old@racco1.gov.ph", "admin1234")
        resp = self.client.post("/api/users/", {
            "email": "s@racco1.gov.ph", "role": self.staff_role.id})
        self.assertEqual(resp.status_code, 201)
        self.assertFalse(User.objects.get(email="s@racco1.gov.ph").admin_takeover_pending)

    def test_successor_first_login_deactivates_other_admins(self):
        temp_password = self._create_successor()["temp_password"]
        login = self._login("new@racco1.gov.ph", temp_password)
        self.assertEqual(login.status_code, 200)

        self.old_admin.refresh_from_db()
        self.assertEqual(self.old_admin.status, User.ARCHIVED)
        self.assertFalse(self.old_admin.is_active)
        # Old admin credentials no longer work at all.
        self.assertEqual(self._login("old@racco1.gov.ph", "admin1234").status_code, 401)
        # Takeover completed — flag cleared, not re-triggered on later logins.
        new_admin = User.objects.get(email="new@racco1.gov.ph")
        self.assertFalse(new_admin.admin_takeover_pending)

    def test_takeover_spares_non_admin_accounts(self):
        staff = User.objects.create_user(
            email="s@racco1.gov.ph", username="s", password="staff1234",
            role=self.staff_role)
        temp_password = self._create_successor()["temp_password"]
        self._login("new@racco1.gov.ph", temp_password)
        staff.refresh_from_db()
        self.assertEqual(staff.status, User.ACTIVE)
        self.assertTrue(staff.is_active)
