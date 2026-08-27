"""Diagnosing "the chatbot is broken" without reading deployment logs.

/healthz/ proves the database credential and nothing else. Without this,
working out whether the model host is down, the token is wrong, or the model
was retired means reading logs on the platform — and a hosted model can be
deprecated underneath a running deployment, which a spike hit when
@cf/meta/llama-3.1-8b-instruct started returning HTTP 410.
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APITestCase

from accounts.models import Role
from assistant import services
from assistant.models import AssistantSetting

User = get_user_model()
URL = "/api/assistant/model-health/"

HOSTED = {
    "ASSISTANT_ALLOW_HOSTED_MODEL": True,
    "ASSISTANT_MODEL_URL": "https://api.example.invalid/v1",
    "ASSISTANT_MODEL_TOKEN": "a-token",
    "ASSISTANT_MODEL_NAME": "@cf/meta/llama-4-scout-17b-16e-instruct",
}


class ModelHealthTest(APITestCase):
    def setUp(self):
        admin_role = Role.objects.create(role_name=Role.ADMINISTRATOR)
        psy_role = Role.objects.create(role_name=Role.PSYCHOLOGIST)
        self.admin = User.objects.create_user(
            email="a@racco1.gov.ph", username="a", password="pass1234",
            role=admin_role)
        self.psy = User.objects.create_user(
            email="p@racco1.gov.ph", username="p", password="pass1234",
            role=psy_role)
        cfg = AssistantSetting.load()
        cfg.enabled = True
        cfg.save()

    def test_reports_reachable_when_the_model_answers(self):
        self.client.force_authenticate(self.admin)
        with patch.object(services.OllamaClient, "generate", return_value="ok"):
            res = self.client.get(URL)
        self.assertEqual(200, res.status_code)
        self.assertTrue(res.data["reachable"])
        self.assertEqual("local", res.data["provider"])

    def test_reports_unreachable_rather_than_raising(self):
        # A 200 saying "no" — the question was answered, and the answer is no.
        self.client.force_authenticate(self.admin)
        with patch.object(services.OllamaClient, "generate",
                          side_effect=services.AIUnavailable("refused")):
            res = self.client.get(URL)
        self.assertEqual(200, res.status_code)
        self.assertFalse(res.data["reachable"])
        self.assertIn("refused", res.data["detail"])

    def test_reports_off_when_the_switch_is_off(self):
        cfg = AssistantSetting.load()
        cfg.enabled = False
        cfg.save()
        self.client.force_authenticate(self.admin)
        res = self.client.get(URL)
        self.assertEqual("off", res.data["provider"])
        self.assertFalse(res.data["reachable"])

    @override_settings(**HOSTED)
    def test_names_the_hosted_model_so_deprecation_is_visible(self):
        self.client.force_authenticate(self.admin)
        with patch.object(services.OpenAICompatibleClient, "generate",
                          return_value="ok"):
            res = self.client.get(URL)
        self.assertEqual("hosted", res.data["provider"])
        self.assertEqual("@cf/meta/llama-4-scout-17b-16e-instruct",
                         res.data["model"])

    @override_settings(**HOSTED)
    def test_never_returns_the_token(self):
        self.client.force_authenticate(self.admin)
        with patch.object(services.OpenAICompatibleClient, "generate",
                          return_value="ok"):
            raw = self.client.get(URL).content.decode()
        self.assertNotIn("a-token", raw)

    def test_a_psychologist_may_not_read_it(self):
        # It names the model host, which is deployment detail.
        self.client.force_authenticate(self.psy)
        self.assertEqual(403, self.client.get(URL).status_code)

    def test_anonymous_is_refused(self):
        self.assertIn(self.client.get(URL).status_code, (401, 403))
