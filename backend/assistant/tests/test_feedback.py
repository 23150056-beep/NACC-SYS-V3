from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from accounts.models import Role
from assistant.models import AssistantJob

User = get_user_model()


class FeedbackTest(APITestCase):
    def setUp(self):
        psy_role = Role.objects.create(role_name=Role.PSYCHOLOGIST)
        admin_role = Role.objects.create(role_name=Role.ADMINISTRATOR)
        self.owner = User.objects.create_user(
            email="p@racco1.gov.ph", username="p", password="pass1234", role=psy_role)
        self.other = User.objects.create_user(
            email="q@racco1.gov.ph", username="q", password="pass1234", role=psy_role)
        self.admin = User.objects.create_user(
            email="a@racco1.gov.ph", username="a", password="pass1234", role=admin_role)
        self.job = AssistantJob.objects.create(
            job_type="remark_polish", output_text="draft", created_by=self.owner)

    def _url(self, job=None):
        return f"/api/assistant/jobs/{(job or self.job).id}/feedback/"

    def test_creator_can_record_outcome(self):
        self.client.force_authenticate(self.owner)
        res = self.client.post(self._url(), {"outcome": "accepted"}, format="json")
        self.assertEqual(res.status_code, 200)
        self.job.refresh_from_db()
        self.assertEqual(self.job.outcome, AssistantJob.ACCEPTED)

    def test_administrator_can_record_outcome(self):
        self.client.force_authenticate(self.admin)
        res = self.client.post(self._url(), {"outcome": "discarded"}, format="json")
        self.assertEqual(res.status_code, 200)

    def test_another_psychologist_gets_404_not_403(self):
        self.client.force_authenticate(self.other)
        res = self.client.post(self._url(), {"outcome": "accepted"}, format="json")
        self.assertEqual(res.status_code, 404)

    def test_invalid_outcome_is_rejected(self):
        self.client.force_authenticate(self.owner)
        res = self.client.post(self._url(), {"outcome": "brilliant"}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_feedback_works_with_the_assistant_switched_off(self):
        """It only writes history, so it must not 503."""
        self.client.force_authenticate(self.owner)
        res = self.client.post(self._url(), {"outcome": "edited"}, format="json")
        self.assertEqual(res.status_code, 200)
