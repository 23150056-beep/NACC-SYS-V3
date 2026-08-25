from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from accounts.models import Role
from assistant import services
from assistant.models import AssistantSetting

User = get_user_model()
URL = "/api/assistant/check/"


class CheckApiTest(APITestCase):
    def setUp(self):
        admin_role = Role.objects.create(role_name=Role.ADMINISTRATOR)
        psy_role = Role.objects.create(role_name=Role.PSYCHOLOGIST)
        self.admin = User.objects.create_user(
            email="a@racco1.gov.ph", username="a", password="pass1234", role=admin_role)
        self.psy = User.objects.create_user(
            email="p@racco1.gov.ph", username="p", password="pass1234", role=psy_role)

    def test_psychologist_is_refused(self):
        self.client.force_authenticate(self.psy)
        self.assertEqual(self.client.post(URL).status_code, 403)

    def test_reports_not_ok_when_switched_off(self):
        self.client.force_authenticate(self.admin)
        res = self.client.post(URL)
        self.assertEqual(res.status_code, 200)  # a 200 describing a false, not a 503
        self.assertFalse(res.data["ok"])

    def test_reports_ok_with_latency_when_reachable(self):
        cfg = AssistantSetting.load()
        cfg.enabled = True
        cfg.save()
        self.client.force_authenticate(self.admin)
        with patch.object(services.OllamaClient, "generate", return_value="OK"):
            res = self.client.post(URL)
        self.assertTrue(res.data["ok"])
        self.assertIsNotNone(res.data["latency_ms"])

    def test_reports_the_error_when_unreachable(self):
        cfg = AssistantSetting.load()
        cfg.enabled = True
        cfg.save()
        self.client.force_authenticate(self.admin)
        err = services.AIUnavailable("Local AI runtime unreachable: refused")
        with patch.object(services.OllamaClient, "generate", side_effect=err):
            res = self.client.post(URL)
        self.assertFalse(res.data["ok"])
        self.assertIn("unreachable", res.data["detail"])
