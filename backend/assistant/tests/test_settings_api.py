from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from accounts.models import Role
from assistant.models import AssistantSetting

User = get_user_model()


class AssistantSettingsApiTest(APITestCase):
    def setUp(self):
        self.admin_role = Role.objects.create(role_name=Role.ADMINISTRATOR)
        self.psy_role = Role.objects.create(role_name=Role.PSYCHOLOGIST)
        self.admin = User.objects.create_user(
            email="a@racco1.gov.ph", username="a", password="pass1234",
            role=self.admin_role)
        self.psy = User.objects.create_user(
            email="p@racco1.gov.ph", username="p", password="pass1234",
            role=self.psy_role)

    def test_administrator_can_read_settings(self):
        self.client.force_authenticate(self.admin)
        res = self.client.get("/api/assistant/settings/")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data["enabled"])
        self.assertEqual(res.data["model_name"], "qwen2.5:3b-instruct")

    def test_psychologist_cannot_read_settings(self):
        self.client.force_authenticate(self.psy)
        self.assertEqual(self.client.get("/api/assistant/settings/").status_code, 403)

    def test_anonymous_cannot_read_settings(self):
        self.assertIn(self.client.get("/api/assistant/settings/").status_code, (401, 403))

    def test_administrator_can_switch_the_assistant_on(self):
        self.client.force_authenticate(self.admin)
        res = self.client.put("/api/assistant/settings/", {
            "enabled": True,
            "ollama_url": "http://localhost:11434",
            "model_name": "qwen2.5:3b-instruct",
        }, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(AssistantSetting.load().enabled)

    def test_settings_stay_a_singleton(self):
        self.client.force_authenticate(self.admin)
        self.client.put("/api/assistant/settings/", {"enabled": True},
                        format="json")
        self.client.put("/api/assistant/settings/", {"enabled": False},
                        format="json")
        self.assertEqual(AssistantSetting.objects.count(), 1)
