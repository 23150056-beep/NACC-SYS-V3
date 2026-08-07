from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from accounts.models import Role

User = get_user_model()


class AuthTest(APITestCase):
    def setUp(self):
        self.role = Role.objects.create(role_name=Role.ADMINISTRATOR)
        self.user = User.objects.create_user(
            email="admin@racco1.gov.ph", username="admin",
            password="admin1234", first_name="Sys", last_name="Admin",
            role=self.role,
        )

    def test_login_returns_tokens_and_user(self):
        resp = self.client.post("/api/auth/login/", {
            "email": "admin@racco1.gov.ph", "password": "admin1234"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("access", resp.data)
        self.assertEqual(resp.data["user"]["role_name"], "Administrator")

    def test_me_requires_auth(self):
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 401)

    def test_me_returns_current_user(self):
        login = self.client.post("/api/auth/login/", {
            "email": "admin@racco1.gov.ph", "password": "admin1234"})
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + login.data["access"])
        resp = self.client.get("/api/auth/me/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["email"], "admin@racco1.gov.ph")
