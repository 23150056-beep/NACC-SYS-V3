from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from accounts.models import Role
from children.models import Child

User = get_user_model()


class UserManagementTest(APITestCase):
    def setUp(self):
        self.admin_role = Role.objects.create(role_name=Role.ADMINISTRATOR)
        self.staff_role = Role.objects.create(role_name=Role.STAFF)
        self.admin = User.objects.create_user(
            email="admin@racco1.gov.ph", username="admin", password="admin1234",
            role=self.admin_role)
        self.staff = User.objects.create_user(
            email="staff@racco1.gov.ph", username="staff", password="staff1234",
            role=self.staff_role)

    def _auth(self, email, password):
        token = self.client.post("/api/auth/login/", {
            "email": email, "password": password}).data["access"]
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + token)

    def test_admin_can_create_user(self):
        self._auth("admin@racco1.gov.ph", "admin1234")
        resp = self.client.post("/api/users/", {
            "email": "new@racco1.gov.ph", "username": "newbie",
            "first_name": "New", "last_name": "Bie",
            "role": self.staff_role.id, "password": "pass1234"})
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(User.objects.filter(email="new@racco1.gov.ph").exists())

    def test_staff_cannot_create_user(self):
        self._auth("staff@racco1.gov.ph", "staff1234")
        resp = self.client.post("/api/users/", {
            "email": "x@racco1.gov.ph", "username": "x", "role": self.staff_role.id})
        self.assertEqual(resp.status_code, 403)

    def test_archive_sets_status_and_blocks_login(self):
        self._auth("admin@racco1.gov.ph", "admin1234")
        resp = self.client.post(f"/api/users/{self.staff.id}/archive/")
        self.assertEqual(resp.status_code, 200)
        self.staff.refresh_from_db()
        self.assertEqual(self.staff.status, User.ARCHIVED)
        self.assertFalse(self.staff.is_active)
        # archived user can no longer authenticate
        login = self.client.post("/api/auth/login/", {
            "email": "staff@racco1.gov.ph", "password": "staff1234"})
        self.assertEqual(login.status_code, 401)

    def test_list_excludes_archived_by_default(self):
        self._auth("admin@racco1.gov.ph", "admin1234")
        self.client.post(f"/api/users/{self.staff.id}/archive/")
        resp = self.client.get("/api/users/")
        emails = [u["email"] for u in resp.data]
        self.assertIn("admin@racco1.gov.ph", emails)
        self.assertNotIn("staff@racco1.gov.ph", emails)

    def test_admin_can_list_roles(self):
        self._auth("admin@racco1.gov.ph", "admin1234")
        resp = self.client.get("/api/roles/")
        self.assertEqual(resp.status_code, 200)
        names = [r["role_name"] for r in resp.data]
        self.assertIn("Administrator", names)
        self.assertIn("Staff", names)


class CreateUserTempPasswordTest(APITestCase):
    """User creation issues a server-generated temporary password, returned
    exactly once, and forces a change at first login — the admin never
    chooses another user's password (same rule as reset-password)."""

    def setUp(self):
        self.admin_role = Role.objects.create(role_name=Role.ADMINISTRATOR)
        self.staff_role = Role.objects.create(role_name=Role.STAFF)
        self.admin = User.objects.create_user(
            email="admin@racco1.gov.ph", username="admin", password="admin1234",
            role=self.admin_role)

    def _auth(self, email, password):
        token = self.client.post("/api/auth/login/", {
            "email": email, "password": password}).data["access"]
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + token)

    def _login(self, email, password):
        return self.client.post("/api/auth/login/", {"email": email, "password": password})

    def test_create_returns_temp_password_and_forces_change(self):
        self._auth("admin@racco1.gov.ph", "admin1234")
        resp = self.client.post("/api/users/", {
            "email": "new@racco1.gov.ph", "first_name": "New", "last_name": "Staff",
            "role": self.staff_role.id})
        self.assertEqual(resp.status_code, 201)
        temp_password = resp.data["temp_password"]
        self.assertTrue(temp_password)

        user = User.objects.get(email="new@racco1.gov.ph")
        self.assertTrue(user.must_change_password)

        login = self._login("new@racco1.gov.ph", temp_password)
        self.assertEqual(login.status_code, 200)
        self.assertTrue(login.data["user"]["must_change_password"])

    def test_client_supplied_password_on_create_is_ignored(self):
        self._auth("admin@racco1.gov.ph", "admin1234")
        resp = self.client.post("/api/users/", {
            "email": "new@racco1.gov.ph", "role": self.staff_role.id,
            "password": "AdminPicked9"})
        self.assertEqual(resp.status_code, 201)
        # The admin-typed password must NOT work — only the generated temp does.
        self.assertEqual(self._login("new@racco1.gov.ph", "AdminPicked9").status_code, 401)
        self.assertEqual(
            self._login("new@racco1.gov.ph", resp.data["temp_password"]).status_code, 200)

    def test_client_supplied_password_on_update_is_ignored(self):
        self._auth("admin@racco1.gov.ph", "admin1234")
        target = User.objects.create_user(
            email="s@racco1.gov.ph", username="s", password="staffPass1",
            role=self.staff_role)
        resp = self.client.put(f"/api/users/{target.id}/", {
            "email": "s@racco1.gov.ph", "password": "Hijacked99"})
        self.assertEqual(resp.status_code, 200)
        # The existing password still works; the admin-typed one does not.
        self.assertEqual(self._login("s@racco1.gov.ph", "staffPass1").status_code, 200)
        self.assertEqual(self._login("s@racco1.gov.ph", "Hijacked99").status_code, 401)


class PsychologistListTest(APITestCase):
    def setUp(self):
        self.admin_role = Role.objects.create(role_name=Role.ADMINISTRATOR)
        self.staff_role = Role.objects.create(role_name=Role.STAFF)
        self.psy_role = Role.objects.create(role_name=Role.PSYCHOLOGIST)
        self.admin = User.objects.create_user(email="a@racco1.gov.ph", username="a", password="pass1234", role=self.admin_role)
        self.staff = User.objects.create_user(email="s@racco1.gov.ph", username="s", password="pass1234", role=self.staff_role)
        self.psy = User.objects.create_user(email="p@racco1.gov.ph", username="p", password="pass1234",
                                            first_name="Levi", last_name="Makalaya", role=self.psy_role)
        Child.objects.create(fullname="A", assigned_psychologist=self.psy)
        Child.objects.create(fullname="B", assigned_psychologist=self.psy)
        Child.objects.create(fullname="C", assigned_psychologist=self.psy, status=Child.ARCHIVED)

    def _auth(self, email):
        token = self.client.post("/api/auth/login/", {"email": email, "password": "pass1234"}).data["access"]
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + token)

    def test_staff_can_list_psychologists_with_caseload(self):
        self._auth("s@racco1.gov.ph")
        resp = self.client.get("/api/psychologists/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]["name"], "Levi Makalaya")
        self.assertEqual(resp.data[0]["caseload"], 2)  # archived child not counted

    def test_admin_can_list_psychologists(self):
        self._auth("a@racco1.gov.ph")
        self.assertEqual(self.client.get("/api/psychologists/").status_code, 200)

    def test_psychologist_forbidden(self):
        self._auth("p@racco1.gov.ph")
        self.assertEqual(self.client.get("/api/psychologists/").status_code, 403)
