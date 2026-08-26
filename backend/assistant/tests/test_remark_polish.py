from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from accounts.models import Role
from assistant import services
from assistant.models import AssistantJob, AssistantSetting

User = get_user_model()
URL = "/api/assistant/polish-remark/"


class RemarkPolishTest(APITestCase):
    def setUp(self):
        self.psy_role = Role.objects.create(role_name=Role.PSYCHOLOGIST)
        self.psy = User.objects.create_user(
            email="p@racco1.gov.ph", username="p", password="pass1234",
            role=self.psy_role)
        cfg = AssistantSetting.load()
        cfg.enabled = True
        cfg.save()
        self.client.force_authenticate(self.psy)

    def test_returns_draft_and_job_id(self):
        with patch.object(services.OllamaClient, "generate",
                          return_value="The child arrived late."):
            res = self.client.post(URL, {"text": "kid late again"}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["draft"], "The child arrived late.")
        self.assertEqual(res.data["disclaimer"], services.DISCLAIMER)
        self.assertTrue(AssistantJob.objects.filter(
            id=res.data["job_id"], job_type="remark_polish").exists())

    def test_blank_text_is_rejected(self):
        res = self.client.post(URL, {"text": "   "}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_missing_text_is_rejected(self):
        self.assertEqual(self.client.post(URL, {}, format="json").status_code, 400)

    def test_non_string_text_is_rejected(self):
        """A non-string JSON value (e.g. {"text": 5}) must 400, not 500."""
        res = self.client.post(URL, {"text": 5}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_503_when_master_switch_off(self):
        cfg = AssistantSetting.load()
        cfg.enabled = False
        cfg.save()
        res = self.client.post(URL, {"text": "note"}, format="json")
        self.assertEqual(res.status_code, 503)

    def test_503_when_feature_flag_off(self):
        cfg = AssistantSetting.load()
        cfg.feature_remark_polish = False
        cfg.save()
        res = self.client.post(URL, {"text": "note"}, format="json")
        self.assertEqual(res.status_code, 503)

    def test_503_when_runtime_unreachable(self):
        err = services.AIUnavailable("Local AI runtime unreachable: refused")
        with patch.object(services.OllamaClient, "generate", side_effect=err):
            res = self.client.post(URL, {"text": "note"}, format="json")
        self.assertEqual(res.status_code, 503)
        self.assertFalse(AssistantJob.objects.get().ok)

    def test_anonymous_is_refused(self):
        self.client.force_authenticate(None)
        self.assertIn(self.client.post(URL, {"text": "n"}, format="json").status_code,
                      (401, 403))


class RemarkPolishDriftGuardTest(APITestCase):
    """Remark polish is instructed to return clear professional English. Against
    Taglish case notes it has returned Tagalog instead — measured at 4/4, once
    garbled badly enough to lose the original meaning ("settling in well"
    vanished; "recreasyon" is a word in neither language).

    A draft that drifts is worse than no draft, so it is rejected rather than
    shown, and the audit records it as a failure so the usage table tells an
    administrator it is happening.
    """

    def setUp(self):
        self.psy_role = Role.objects.create(role_name=Role.PSYCHOLOGIST)
        self.psy = User.objects.create_user(
            email="p@racco1.gov.ph", username="p", password="pass1234",
            role=self.psy_role)
        cfg = AssistantSetting.load()
        cfg.enabled = True
        cfg.save()
        self.client.force_authenticate(self.psy)

    def test_a_drifted_draft_is_rejected_not_returned(self):
        drifted = "Nakikisalamuhan ng anak sa recreasyon."
        with patch.object(services.OllamaClient, "generate", return_value=drifted):
            res = self.client.post(URL, {"text": "Settling in well."}, format="json")
        self.assertEqual(res.status_code, 422)
        self.assertNotIn("draft", res.data)
        self.assertIn("English", res.data["detail"])

    def test_a_rejected_draft_is_audited_as_a_failure(self):
        drifted = "Nag-aalala pa rin tungkol sa school."
        with patch.object(services.OllamaClient, "generate", return_value=drifted):
            self.client.post(URL, {"text": "Still worried."}, format="json")
        job = AssistantJob.objects.get()
        self.assertFalse(job.ok)
        self.assertIn("drift", job.error)

    def test_clean_english_is_returned_unchanged(self):
        clean = "The child is settling in well and mixing with the others."
        with patch.object(services.OllamaClient, "generate", return_value=clean):
            res = self.client.post(URL, {"text": "settling ok"}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["draft"], clean)
        self.assertTrue(AssistantJob.objects.get().ok)
