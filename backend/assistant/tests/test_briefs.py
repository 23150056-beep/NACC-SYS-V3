from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from accounts.models import Role
from assistant import services
from assistant.models import AssistantJob, AssistantSetting
from children.models import Child

User = get_user_model()


class BriefTestBase(APITestCase):
    """Shared fixtures only — no tests. Task 10 extends this too, and a
    subclass that inherited these tests would re-run POST cases against the
    read-only `latest` URL."""

    def setUp(self):
        psy_role = Role.objects.create(role_name=Role.PSYCHOLOGIST)
        admin_role = Role.objects.create(role_name=Role.ADMINISTRATOR)
        self.psy = User.objects.create_user(
            email="p@racco1.gov.ph", username="p", password="pass1234", role=psy_role)
        self.other = User.objects.create_user(
            email="q@racco1.gov.ph", username="q", password="pass1234", role=psy_role)
        self.admin = User.objects.create_user(
            email="a@racco1.gov.ph", username="a", password="pass1234", role=admin_role)
        self.mine = Child.objects.create(fullname="Maria Santos",
                                         assigned_psychologist=self.psy)
        self.theirs = Child.objects.create(fullname="Juan Dela Cruz",
                                           assigned_psychologist=self.other)
        cfg = AssistantSetting.load()
        cfg.enabled = True
        cfg.save()


class BriefTest(BriefTestBase):
    def _url(self, child):
        return f"/api/assistant/brief/child/{child.id}/"

    def test_psychologist_gets_a_brief_for_their_own_child(self):
        self.client.force_authenticate(self.psy)
        with patch.object(services.OllamaClient, "generate", return_value="Brief."):
            res = self.client.post(self._url(self.mine))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["draft"], "Brief.")
        job = AssistantJob.objects.get()
        self.assertEqual(job.input_ref, f"child:{self.mine.id}")
        self.assertEqual(job.job_type, "brief")

    def test_psychologist_gets_404_for_another_psychologists_child(self):
        self.client.force_authenticate(self.psy)
        with patch.object(services.OllamaClient, "generate", return_value="Brief."):
            res = self.client.post(self._url(self.theirs))
        self.assertEqual(res.status_code, 404)
        self.assertFalse(AssistantJob.objects.exists())

    def test_administrator_may_brief_any_child(self):
        self.client.force_authenticate(self.admin)
        with patch.object(services.OllamaClient, "generate", return_value="Brief."):
            res = self.client.post(self._url(self.theirs))
        self.assertEqual(res.status_code, 200)

    def test_missing_child_is_404(self):
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.post("/api/assistant/brief/child/99999/").status_code, 404)

    def test_503_when_feature_flag_off(self):
        cfg = AssistantSetting.load()
        cfg.feature_brief = False
        cfg.save()
        self.client.force_authenticate(self.psy)
        self.assertEqual(self.client.post(self._url(self.mine)).status_code, 503)
