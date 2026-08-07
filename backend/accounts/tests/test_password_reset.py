from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from accounts.models import Role

User = get_user_model()


class PasswordResetTest(APITestCase):
    """Admin-issued temporary passwords + server-enforced forced change."""

    def setUp(self):
        self.admin_role = Role.objects.create(role_name=Role.ADMINISTRATOR)
        self.staff_role = Role.objects.create(role_name=Role.STAFF)
        self.psy_role = Role.objects.create(role_name=Role.PSYCHOLOGIST)
        self.admin = User.objects.create_user(
            email="admin@racco1.gov.ph", username="admin", password="admin1234",
            role=self.admin_role)
        self.staff = User.objects.create_user(
            email="staff@racco1.gov.ph", username="staff", password="staff1234",
            role=self.staff_role)
        self.psy = User.objects.create_user(
            email="psy@racco1.gov.ph", username="psy", password="psy1234",
            role=self.psy_role)

    def _auth(self, email, password):
        token = self.client.post("/api/auth/login/", {
            "email": email, "password": password}).data["access"]
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + token)

    def _login(self, email, password):
        return self.client.post("/api/auth/login/", {"email": email, "password": password})

    # ---- admin reset-password action ----

    def test_admin_can_reset_another_users_password(self):
        self._auth("admin@racco1.gov.ph", "admin1234")
        resp = self.client.post(f"/api/users/{self.staff.id}/reset-password/")
        self.assertEqual(resp.status_code, 200)
        temp_password = resp.data["temp_password"]
        self.assertTrue(temp_password)

        self.staff.refresh_from_db()
        self.assertTrue(self.staff.must_change_password)

        login = self._login("staff@racco1.gov.ph", temp_password)
        self.assertEqual(login.status_code, 200)
        self.assertTrue(login.data["user"]["must_change_password"])

    def test_staff_forbidden_from_reset_password(self):
        self._auth("staff@racco1.gov.ph", "staff1234")
        resp = self.client.post(f"/api/users/{self.psy.id}/reset-password/")
        self.assertEqual(resp.status_code, 403)

    def test_psychologist_forbidden_from_reset_password(self):
        self._auth("psy@racco1.gov.ph", "psy1234")
        resp = self.client.post(f"/api/users/{self.staff.id}/reset-password/")
        self.assertEqual(resp.status_code, 403)

    def test_reset_password_on_archived_user_is_400(self):
        self._auth("admin@racco1.gov.ph", "admin1234")
        self.client.post(f"/api/users/{self.staff.id}/archive/")
        # Archived users are excluded from the default queryset, same as elsewhere
        # in this API — the admin UI needs include_archived=true to reach them.
        resp = self.client.post(f"/api/users/{self.staff.id}/reset-password/?include_archived=true")
        self.assertEqual(resp.status_code, 400)

    # ---- server-side enforcement while must_change_password is set ----

    def test_forced_password_change_blocks_other_endpoints(self):
        self._auth("admin@racco1.gov.ph", "admin1234")
        temp_password = self.client.post(f"/api/users/{self.staff.id}/reset-password/").data["temp_password"]

        login = self._login("staff@racco1.gov.ph", temp_password)
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + login.data["access"])

        blocked = self.client.get("/api/children/")
        self.assertEqual(blocked.status_code, 401)

        # allowlisted endpoints keep working
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 200)
        self.assertEqual(
            self.client.post("/api/auth/refresh/", {"refresh": login.data["refresh"]}).status_code, 200)
        change = self.client.post("/api/auth/change-password/", {
            "current_password": temp_password, "new_password": "brandNewPass9"})
        self.assertEqual(change.status_code, 200)

    # ---- change-password endpoint ----

    def test_change_password_wrong_current_is_400(self):
        self._auth("staff@racco1.gov.ph", "staff1234")
        resp = self.client.post("/api/auth/change-password/", {
            "current_password": "wrongpass", "new_password": "brandNewPass9"})
        self.assertEqual(resp.status_code, 400)

    def test_change_password_weak_new_password_is_400(self):
        self._auth("staff@racco1.gov.ph", "staff1234")
        resp = self.client.post("/api/auth/change-password/", {
            "current_password": "staff1234", "new_password": "12345678"})
        self.assertEqual(resp.status_code, 400)

    def test_change_password_same_as_current_is_400(self):
        self._auth("staff@racco1.gov.ph", "staff1234")
        resp = self.client.post("/api/auth/change-password/", {
            "current_password": "staff1234", "new_password": "staff1234"})
        self.assertEqual(resp.status_code, 400)

    def test_change_password_success_flow(self):
        # Forced change: admin resets, then staff changes password and regains full access.
        self._auth("admin@racco1.gov.ph", "admin1234")
        temp_password = self.client.post(f"/api/users/{self.staff.id}/reset-password/").data["temp_password"]

        login = self._login("staff@racco1.gov.ph", temp_password)
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + login.data["access"])

        resp = self.client.post("/api/auth/change-password/", {
            "current_password": temp_password, "new_password": "brandNewPass9"})
        self.assertEqual(resp.status_code, 200)

        self.staff.refresh_from_db()
        self.assertFalse(self.staff.must_change_password)

        # old (temp) password no longer works
        self.assertEqual(self._login("staff@racco1.gov.ph", temp_password).status_code, 401)
        # new password works
        relog = self._login("staff@racco1.gov.ph", "brandNewPass9")
        self.assertEqual(relog.status_code, 200)
        self.assertFalse(relog.data["user"]["must_change_password"])

        # normal API access is restored (no leftover must_change_password lock)
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + relog.data["access"])
        self.assertEqual(self.client.get("/api/children/").status_code, 200)

    def test_voluntary_password_change_without_forced_flag(self):
        self._auth("staff@racco1.gov.ph", "staff1234")
        resp = self.client.post("/api/auth/change-password/", {
            "current_password": "staff1234", "new_password": "brandNewPass9"})
        self.assertEqual(resp.status_code, 200)
        self.staff.refresh_from_db()
        self.assertFalse(self.staff.must_change_password)
        self.assertEqual(self._login("staff@racco1.gov.ph", "brandNewPass9").status_code, 200)
