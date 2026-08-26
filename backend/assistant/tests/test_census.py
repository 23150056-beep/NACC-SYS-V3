from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from accounts.models import Role
from assistant import services
from assistant.models import AssistantJob, AssistantSetting

User = get_user_model()
URL = "/api/assistant/census-narrative/"
FIGURES = {"active_children": 40, "completed_sessions": 112}


class CensusTest(APITestCase):
    def setUp(self):
        admin_role = Role.objects.create(role_name=Role.ADMINISTRATOR)
        staff_role = Role.objects.create(role_name=Role.STAFF)
        psy_role = Role.objects.create(role_name=Role.PSYCHOLOGIST)
        self.admin = User.objects.create_user(
            email="a@racco1.gov.ph", username="a", password="pass1234", role=admin_role)
        self.staff = User.objects.create_user(
            email="s@racco1.gov.ph", username="s", password="pass1234", role=staff_role)
        self.psy = User.objects.create_user(
            email="p@racco1.gov.ph", username="p", password="pass1234", role=psy_role)
        cfg = AssistantSetting.load()
        cfg.enabled = True
        cfg.save()

    def test_administrator_gets_a_narrative(self):
        self.client.force_authenticate(self.admin)
        with patch.object(services.OllamaClient, "generate", return_value="Narrative."):
            res = self.client.post(URL, {"figures": FIGURES}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["draft"], "Narrative.")
        self.assertEqual(AssistantJob.objects.get().job_type, "census_narrative")

    def test_staff_may_also_generate_one(self):
        self.client.force_authenticate(self.staff)
        with patch.object(services.OllamaClient, "generate", return_value="Narrative."):
            self.assertEqual(
                self.client.post(URL, {"figures": FIGURES}, format="json").status_code, 200)

    def test_psychologist_is_refused(self):
        self.client.force_authenticate(self.psy)
        self.assertEqual(
            self.client.post(URL, {"figures": FIGURES}, format="json").status_code, 403)

    def test_empty_figures_are_rejected(self):
        self.client.force_authenticate(self.admin)
        self.assertEqual(
            self.client.post(URL, {"figures": {}}, format="json").status_code, 400)

    def test_non_object_figures_are_rejected(self):
        self.client.force_authenticate(self.admin)
        self.assertEqual(
            self.client.post(URL, {"figures": "lots"}, format="json").status_code, 400)

    def test_503_when_the_assistant_is_off(self):
        cfg = AssistantSetting.load()
        cfg.enabled = False
        cfg.save()
        self.client.force_authenticate(self.admin)
        self.assertEqual(
            self.client.post(URL, {"figures": FIGURES}, format="json").status_code, 503)
