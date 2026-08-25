from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import Role
from assistant import services, views
from assistant.models import AssistantJob, AssistantSetting
from children.models import Child
from scheduling.models import Appointment

User = get_user_model()
URL = "/api/assistant/prefetch-briefs/"


class PrefetchTest(APITestCase):
    def setUp(self):
        psy_role = Role.objects.create(role_name=Role.PSYCHOLOGIST)
        self.psy = User.objects.create_user(
            email="p@racco1.gov.ph", username="p", password="pass1234", role=psy_role)
        self.other = User.objects.create_user(
            email="q@racco1.gov.ph", username="q", password="pass1234", role=psy_role)
        self.mine = Child.objects.create(fullname="Maria", assigned_psychologist=self.psy)
        self.theirs = Child.objects.create(fullname="Juan", assigned_psychologist=self.other)
        cfg = AssistantSetting.load()
        cfg.enabled = True
        cfg.save()
        self.client.force_authenticate(self.psy)

    def _appointment(self, child, psychologist, *, days=0):
        # Appointment has no `end` field -- only `start` and `duration_minutes`
        # (default 60, i.e. one hour), so the default stands in for the brief's
        # `end=start + timedelta(hours=1)`.
        start = timezone.now() + timedelta(days=days, hours=1)
        return Appointment.objects.create(
            child=child, psychologist=psychologist, start=start,
            status=Appointment.SCHEDULED)

    def test_queues_todays_own_appointments(self):
        self._appointment(self.mine, self.psy)
        with patch.object(views, "_start_prefetch_thread") as spawn:
            res = self.client.post(URL)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["queued"], [self.mine.id])
        spawn.assert_called_once()

    def test_ignores_another_psychologists_appointments(self):
        self._appointment(self.theirs, self.other)
        with patch.object(views, "_start_prefetch_thread"):
            res = self.client.post(URL)
        self.assertEqual(res.data["queued"], [])

    def test_ignores_appointments_on_other_days(self):
        self._appointment(self.mine, self.psy, days=3)
        with patch.object(views, "_start_prefetch_thread"):
            res = self.client.post(URL)
        self.assertEqual(res.data["queued"], [])

    def test_skips_children_that_already_have_a_brief_today(self):
        self._appointment(self.mine, self.psy)
        AssistantJob.objects.create(
            job_type="brief", input_ref=f"child:{self.mine.id}", ok=True,
            output_text="already done")
        with patch.object(views, "_start_prefetch_thread"):
            res = self.client.post(URL)
        self.assertEqual(res.data["queued"], [])
        self.assertEqual(res.data["skipped"], [self.mine.id])

    def test_worker_generates_sequentially_and_audits(self):
        with patch.object(services.OllamaClient, "generate", return_value="Brief."):
            views._generate_briefs_now([self.mine.id], self.psy)
        job = AssistantJob.objects.get()
        self.assertEqual(job.input_ref, f"child:{self.mine.id}")
        self.assertEqual(job.created_by, self.psy)

    def test_worker_survives_a_failing_generation(self):
        """One unreachable call must not abandon the rest of the queue."""
        err = services.AIUnavailable("unreachable")
        with patch.object(services.OllamaClient, "generate", side_effect=err):
            views._generate_briefs_now([self.mine.id], self.psy)  # must not raise
        self.assertFalse(AssistantJob.objects.get().ok)

    def test_503_when_feature_flag_off(self):
        cfg = AssistantSetting.load()
        cfg.feature_brief = False
        cfg.save()
        self.assertEqual(self.client.post(URL).status_code, 503)
