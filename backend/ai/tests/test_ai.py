from unittest.mock import patch

from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from accounts.models import Role
from ai.models import AISetting, AIJob
from ai.services import AIUnavailable, NullClient, get_ai_client
from children.models import Child
from clinical.models import PsychologicalReport, RemarkNote

User = get_user_model()


class FakeClient:
    available = True

    def __init__(self, reply="Drafted text."):
        self.reply = reply
        self.prompts = []

    def generate(self, prompt, system=None):
        self.prompts.append(prompt)
        return self.reply


class AIBase(APITestCase):
    def setUp(self):
        self.admin_role = Role.objects.create(role_name=Role.ADMINISTRATOR)
        self.psy_role = Role.objects.create(role_name=Role.PSYCHOLOGIST)
        self.staff_role = Role.objects.create(role_name=Role.STAFF)
        self.admin = User.objects.create_user(
            email="a@racco1.gov.ph", username="a", password="pass1234", role=self.admin_role)
        self.psy = User.objects.create_user(
            email="p@racco1.gov.ph", username="p", password="pass1234", role=self.psy_role)
        self.child = Child.objects.create(
            fullname="Ana Reyes", case_type="Adoption", assigned_psychologist=self.psy)

    def _auth(self, email):
        token = self.client.post("/api/auth/login/", {
            "email": email, "password": "pass1234"}).data["access"]
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + token)

    def _enable(self):
        s = AISetting.load()
        s.enabled = True
        s.save()


class AISettingsTest(AIBase):
    def test_defaults_off(self):
        self._auth("p@racco1.gov.ph")
        resp = self.client.get("/api/ai/settings/")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data["enabled"])

    def test_admin_can_toggle(self):
        self._auth("a@racco1.gov.ph")
        resp = self.client.patch("/api/ai/settings/", {"enabled": True}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(AISetting.load().enabled)

    def test_non_admin_cannot_toggle(self):
        self._auth("p@racco1.gov.ph")
        resp = self.client.patch("/api/ai/settings/", {"enabled": True}, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_client_seam(self):
        self.assertIsInstance(get_ai_client(), NullClient)
        with self.assertRaises(AIUnavailable):
            NullClient().generate("x")


class BriefTest(AIBase):
    def test_disabled_returns_503(self):
        self._auth("p@racco1.gov.ph")
        resp = self.client.post(f"/api/ai/brief/child/{self.child.id}/")
        self.assertEqual(resp.status_code, 503)

    @patch("ai.services.get_ai_client", return_value=FakeClient("Brief for Ana."))
    def test_brief_returns_draft_and_logs_job(self, _mock):
        self._enable()
        RemarkNote.objects.create(child=self.child, author=self.psy, text="Sleeping better.")
        self._auth("p@racco1.gov.ph")
        resp = self.client.post(f"/api/ai/brief/child/{self.child.id}/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["draft"], "Brief for Ana.")
        self.assertIn("disclaimer", resp.data)
        job = AIJob.objects.get()
        self.assertEqual(job.job_type, "brief")
        self.assertEqual(job.input_ref, f"child:{self.child.id}")
        self.assertTrue(job.ok)

    @patch("ai.services.get_ai_client", return_value=FakeClient())
    def test_brief_scoped_to_assigned(self, _mock):
        self._enable()
        other = User.objects.create_user(
            email="o@racco1.gov.ph", username="o", password="pass1234", role=self.psy_role)
        self._auth("o@racco1.gov.ph")
        resp = self.client.post(f"/api/ai/brief/child/{self.child.id}/")
        self.assertEqual(resp.status_code, 404)

    def test_unreachable_runtime_returns_503_and_logs_error(self):
        self._enable()  # enabled but no Ollama running on that port in CI
        s = AISetting.load()
        s.ollama_url = "http://127.0.0.1:1"  # guaranteed refused
        s.save()
        self._auth("p@racco1.gov.ph")
        resp = self.client.post(f"/api/ai/brief/child/{self.child.id}/")
        self.assertEqual(resp.status_code, 503)
        job = AIJob.objects.get()
        self.assertFalse(job.ok)


class DocIntelligenceTest(AIBase):
    def setUp(self):
        super().setUp()
        self.report = PsychologicalReport.objects.create(
            child=self.child, author=self.psy, file="reports/x.pdf",
            extracted_text="The child shows marked improvement in emotional regulation.")

    @patch("ai.services.get_ai_client", return_value=FakeClient("1. Findings…"))
    def test_draft_saved_unconfirmed(self, _mock):
        self._enable()
        self._auth("p@racco1.gov.ph")
        resp = self.client.post(f"/api/ai/summarize-report/{self.report.id}/")
        self.assertEqual(resp.status_code, 200)
        self.report.refresh_from_db()
        self.assertEqual(self.report.ai_summary, "1. Findings…")
        self.assertFalse(self.report.ai_summary_confirmed)

    @patch("ai.services.get_ai_client", return_value=FakeClient())
    def test_confirm_flow(self, _mock):
        self._enable()
        self._auth("p@racco1.gov.ph")
        self.client.post(f"/api/ai/summarize-report/{self.report.id}/")
        resp = self.client.post(f"/api/ai/confirm-summary/{self.report.id}/",
                                {"text": "Edited summary."}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.report.refresh_from_db()
        self.assertTrue(self.report.ai_summary_confirmed)
        self.assertEqual(self.report.ai_summary, "Edited summary.")
        self.assertTrue(AIJob.objects.filter(accepted=True).exists())

    def test_no_text_400(self):
        self._enable()
        self.report.extracted_text = ""
        self.report.save()
        with patch("ai.services.get_ai_client", return_value=FakeClient()):
            self._auth("p@racco1.gov.ph")
            resp = self.client.post(f"/api/ai/summarize-report/{self.report.id}/")
        self.assertEqual(resp.status_code, 400)


class PolishAndNarrativeTest(AIBase):
    @patch("ai.services.get_ai_client", return_value=FakeClient("Polished prose."))
    def test_polish(self, _mock):
        self._enable()
        self._auth("p@racco1.gov.ph")
        resp = self.client.post("/api/ai/polish-remark/", {"text": "slept ok, less anx"}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["draft"], "Polished prose.")

    @patch("ai.services.get_ai_client", return_value=FakeClient("Narrative."))
    def test_narrative_admin_only(self, _mock):
        self._enable()
        self._auth("p@racco1.gov.ph")
        self.assertEqual(self.client.post("/api/ai/census-narrative/",
                                          {"stats": {"total": 3}}, format="json").status_code, 403)
        self._auth("a@racco1.gov.ph")
        resp = self.client.post("/api/ai/census-narrative/", {"stats": {"total": 3}}, format="json")
        self.assertEqual(resp.status_code, 200)


class PromptHardeningTest(AIBase):
    @patch("ai.services.get_ai_client")
    def test_brief_prompt_includes_age_and_gender(self, mock_get):
        from datetime import date
        fake = FakeClient()
        mock_get.return_value = fake
        self._enable()
        self.child.birth_date = date(2018, 3, 1)
        self.child.gender = "Female"
        self.child.save()
        self._auth("p@racco1.gov.ph")
        resp = self.client.post(f"/api/ai/brief/child/{self.child.id}/")
        self.assertEqual(resp.status_code, 200)
        prompt = fake.prompts[0]
        self.assertIn("Sex/gender: Female", prompt)
        self.assertRegex(prompt, r"Age: \d+")
        self.assertIn("Do not state age, gender, or any other detail", prompt)

    @patch("ai.services.get_ai_client")
    def test_brief_prompt_unknown_when_missing(self, mock_get):
        fake = FakeClient()
        mock_get.return_value = fake
        self._enable()
        self._auth("p@racco1.gov.ph")
        self.client.post(f"/api/ai/brief/child/{self.child.id}/")
        prompt = fake.prompts[0]
        self.assertIn("Age: unknown", prompt)
        self.assertIn("Sex/gender: unspecified", prompt)

    def test_normalize_output(self):
        from ai.services import _normalize_output
        self.assertEqual(
            _normalize_output("Mika’s day — all “fine” now"),
            "Mika's day - all \"fine\" now")

    @patch("ai.services.get_ai_client")
    def test_run_job_normalizes(self, mock_get):
        mock_get.return_value = FakeClient(reply="Mika’s ok")
        self._enable()
        self._auth("p@racco1.gov.ph")
        resp = self.client.post("/api/ai/polish-remark/", {"text": "x"}, format="json")
        self.assertEqual(resp.data["draft"], "Mika's ok")


class ImmediateThread:
    """Stand-in for threading.Thread that runs the target synchronously."""
    def __init__(self, target=None, args=(), kwargs=None, daemon=None):
        self._target, self._args, self._kwargs = target, args, kwargs or {}

    def start(self):
        self._target(*self._args, **self._kwargs)


class PrefetchBriefTest(AIBase):
    def setUp(self):
        super().setUp()
        from django.utils import timezone
        from scheduling.models import Appointment
        self.appt = Appointment.objects.create(
            child=self.child, psychologist=self.psy,
            start=timezone.localtime().replace(hour=23, minute=0),
            status=Appointment.SCHEDULED)

    def test_latest_404_when_none(self):
        self._auth("p@racco1.gov.ph")
        resp = self.client.get(f"/api/ai/brief/child/{self.child.id}/latest/")
        self.assertEqual(resp.status_code, 404)

    def test_latest_returns_todays_brief(self):
        AIJob.objects.create(job_type="brief", input_ref=f"child:{self.child.id}",
                             output_text="Cached brief.", ok=True, created_by=self.psy)
        self._auth("p@racco1.gov.ph")
        resp = self.client.get(f"/api/ai/brief/child/{self.child.id}/latest/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["draft"], "Cached brief.")
        self.assertIn("generated_at", resp.data)

    def test_latest_scoped_to_assigned(self):
        other = User.objects.create_user(
            email="o@racco1.gov.ph", username="o", password="pass1234", role=self.psy_role)
        AIJob.objects.create(job_type="brief", input_ref=f"child:{self.child.id}",
                             output_text="Cached.", ok=True, created_by=self.psy)
        self._auth("o@racco1.gov.ph")
        resp = self.client.get(f"/api/ai/brief/child/{self.child.id}/latest/")
        self.assertEqual(resp.status_code, 404)

    def test_prefetch_disabled_503(self):
        self._auth("p@racco1.gov.ph")
        self.assertEqual(self.client.post("/api/ai/prefetch-briefs/").status_code, 503)

    @patch("ai.briefs.threading.Thread", ImmediateThread)
    @patch("ai.services.get_ai_client", return_value=FakeClient("Prefetched."))
    def test_prefetch_generates_for_todays_appointments(self, _mock):
        self._enable()
        self._auth("p@racco1.gov.ph")
        resp = self.client.post("/api/ai/prefetch-briefs/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["queued"], [self.child.id])
        job = AIJob.objects.get(job_type="brief")
        self.assertEqual(job.output_text, "Prefetched.")

    @patch("ai.briefs.threading.Thread", ImmediateThread)
    @patch("ai.services.get_ai_client", return_value=FakeClient())
    def test_prefetch_skips_when_today_brief_exists(self, _mock):
        self._enable()
        AIJob.objects.create(job_type="brief", input_ref=f"child:{self.child.id}",
                             output_text="Existing.", ok=True, created_by=self.psy)
        self._auth("p@racco1.gov.ph")
        resp = self.client.post("/api/ai/prefetch-briefs/")
        self.assertEqual(resp.data["queued"], [])
        self.assertEqual(resp.data["skipped"], [self.child.id])
        self.assertEqual(AIJob.objects.filter(job_type="brief").count(), 1)

    @patch("ai.briefs.threading.Thread", ImmediateThread)
    @patch("ai.services.get_ai_client", return_value=FakeClient())
    def test_prefetch_scoped_for_psychologist(self, _mock):
        from django.utils import timezone
        from scheduling.models import Appointment
        self._enable()
        other_psy = User.objects.create_user(
            email="o@racco1.gov.ph", username="o", password="pass1234", role=self.psy_role)
        other_child = Child.objects.create(fullname="Ben Cruz", assigned_psychologist=other_psy)
        Appointment.objects.create(
            child=other_child, psychologist=other_psy,
            start=timezone.localtime().replace(hour=23, minute=0),
            status=Appointment.SCHEDULED)
        self._auth("p@racco1.gov.ph")
        resp = self.client.post("/api/ai/prefetch-briefs/")
        self.assertEqual(resp.data["queued"], [self.child.id])


class CaseReferralSummaryTest(AIBase):
    def setUp(self):
        super().setUp()
        from clinical.models import CaseReferral
        self.staff = User.objects.create_user(
            email="s@racco1.gov.ph", username="s", password="pass1234", role=self.staff_role)
        self.cs = CaseReferral.objects.create(
            child=self.child, uploaded_by=self.staff, file="case_referrals/x.pdf",
            extracted_text="Family background: the child lives with a foster family.")

    @patch("ai.services.get_ai_client", return_value=FakeClient("1. Background…"))
    def test_draft_saved_unconfirmed(self, _mock):
        self._enable()
        self._auth("p@racco1.gov.ph")
        resp = self.client.post(f"/api/ai/summarize-case-referral/{self.cs.id}/")
        self.assertEqual(resp.status_code, 200)
        self.cs.refresh_from_db()
        self.assertEqual(self.cs.ai_summary, "1. Background…")
        self.assertFalse(self.cs.ai_summary_confirmed)
        job = AIJob.objects.get()
        self.assertEqual(job.job_type, "case_referral")
        self.assertEqual(job.input_ref, f"casereferral:{self.cs.id}")

    @patch("ai.services.get_ai_client", return_value=FakeClient())
    def test_scoped_to_assigned_psychologist(self, _mock):
        self._enable()
        other = User.objects.create_user(
            email="o@racco1.gov.ph", username="o", password="pass1234", role=self.psy_role)
        self._auth("o@racco1.gov.ph")
        resp = self.client.post(f"/api/ai/summarize-case-referral/{self.cs.id}/")
        self.assertEqual(resp.status_code, 404)

    def test_no_text_400(self):
        self._enable()
        self.cs.extracted_text = ""
        self.cs.save()
        with patch("ai.services.get_ai_client", return_value=FakeClient()):
            self._auth("p@racco1.gov.ph")
            resp = self.client.post(f"/api/ai/summarize-case-referral/{self.cs.id}/")
        self.assertEqual(resp.status_code, 400)

    @patch("ai.services.get_ai_client", return_value=FakeClient())
    def test_confirm_flow(self, _mock):
        self._enable()
        self._auth("p@racco1.gov.ph")
        self.client.post(f"/api/ai/summarize-case-referral/{self.cs.id}/")
        resp = self.client.post(f"/api/ai/confirm-case-referral-summary/{self.cs.id}/",
                                {"text": "Edited case summary."}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.cs.refresh_from_db()
        self.assertTrue(self.cs.ai_summary_confirmed)
        self.assertEqual(self.cs.ai_summary, "Edited case summary.")

    @patch("ai.services.get_ai_client", return_value=FakeClient())
    def test_staff_cannot_confirm(self, _mock):
        self._enable()
        self._auth("s@racco1.gov.ph")
        resp = self.client.post(f"/api/ai/confirm-case-referral-summary/{self.cs.id}/",
                                {"text": "x"}, format="json")
        self.assertEqual(resp.status_code, 403)


class FeedbackAndMetricsTest(AIBase):
    def _job(self, **kw):
        base = dict(job_type="brief", input_ref=f"child:{self.child.id}",
                    output_text="Draft.", ok=True, created_by=self.psy, latency_ms=100)
        base.update(kw)
        return AIJob.objects.create(**base)

    def test_feedback_sets_outcome(self):
        job = self._job()
        self._auth("p@racco1.gov.ph")
        resp = self.client.post(f"/api/ai/jobs/{job.id}/feedback/",
                                {"outcome": "accepted"}, format="json")
        self.assertEqual(resp.status_code, 200)
        job.refresh_from_db()
        self.assertEqual(job.outcome, "accepted")
        self.assertTrue(job.accepted)

    def test_feedback_discarded(self):
        job = self._job()
        self._auth("p@racco1.gov.ph")
        self.client.post(f"/api/ai/jobs/{job.id}/feedback/",
                         {"outcome": "discarded"}, format="json")
        job.refresh_from_db()
        self.assertEqual(job.outcome, "discarded")
        self.assertFalse(job.accepted)

    def test_feedback_invalid_outcome_400(self):
        job = self._job()
        self._auth("p@racco1.gov.ph")
        resp = self.client.post(f"/api/ai/jobs/{job.id}/feedback/",
                                {"outcome": "loved-it"}, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_feedback_creator_only(self):
        job = self._job()
        other = User.objects.create_user(
            email="o@racco1.gov.ph", username="o", password="pass1234", role=self.psy_role)
        self._auth("o@racco1.gov.ph")
        resp = self.client.post(f"/api/ai/jobs/{job.id}/feedback/",
                                {"outcome": "accepted"}, format="json")
        self.assertEqual(resp.status_code, 404)

    def test_metrics_admin_only(self):
        self._auth("p@racco1.gov.ph")
        self.assertEqual(self.client.get("/api/ai/metrics/").status_code, 403)

    def test_metrics_aggregates(self):
        self._job(outcome="accepted", latency_ms=100)
        self._job(outcome="edited", latency_ms=300)
        self._job(ok=False, error="boom", latency_ms=None)
        self._auth("a@racco1.gov.ph")
        resp = self.client.get("/api/ai/metrics/")
        self.assertEqual(resp.status_code, 200)
        brief = resp.data["brief"]["all_time"]
        self.assertEqual(brief["runs"], 3)
        self.assertEqual(brief["ok"], 2)
        self.assertEqual(brief["errors"], 1)
        self.assertEqual(brief["avg_latency_ms"], 200)
        self.assertEqual(brief["outcomes"]["accepted"], 1)
        self.assertEqual(brief["outcomes"]["edited"], 1)


class ConfirmOutcomeTest(AIBase):
    def setUp(self):
        super().setUp()
        self.report = PsychologicalReport.objects.create(
            child=self.child, author=self.psy, file="reports/x.pdf",
            extracted_text="The child shows improvement.")

    @patch("ai.services.get_ai_client", return_value=FakeClient("Draft summary."))
    def test_confirm_unchanged_marks_accepted(self, _mock):
        self._enable()
        self._auth("p@racco1.gov.ph")
        self.client.post(f"/api/ai/summarize-report/{self.report.id}/")
        self.client.post(f"/api/ai/confirm-summary/{self.report.id}/",
                         {"text": "Draft summary."}, format="json")
        job = AIJob.objects.get(job_type="doc_intelligence")
        self.assertEqual(job.outcome, "accepted")

    @patch("ai.services.get_ai_client", return_value=FakeClient("Draft summary."))
    def test_confirm_changed_marks_edited(self, _mock):
        self._enable()
        self._auth("p@racco1.gov.ph")
        self.client.post(f"/api/ai/summarize-report/{self.report.id}/")
        self.client.post(f"/api/ai/confirm-summary/{self.report.id}/",
                         {"text": "Heavily edited."}, format="json")
        job = AIJob.objects.get(job_type="doc_intelligence")
        self.assertEqual(job.outcome, "edited")
