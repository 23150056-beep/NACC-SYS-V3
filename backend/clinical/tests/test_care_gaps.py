from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from accounts.models import Role
from children.models import Child
from clinical.models import PreAssessment, ConsentRecord, PsychologicalReport
from clinical.care_gaps import compute_alerts
from scheduling.models import Appointment

User = get_user_model()


class CareGapTest(APITestCase):
    def setUp(self):
        self.psy_role = Role.objects.create(role_name=Role.PSYCHOLOGIST)
        self.admin_role = Role.objects.create(role_name=Role.ADMINISTRATOR)
        self.psy = User.objects.create_user(
            email="p@racco1.gov.ph", username="p", password="pass1234", role=self.psy_role)
        self.admin = User.objects.create_user(
            email="a@racco1.gov.ph", username="a", password="pass1234", role=self.admin_role)

    def _types_for(self, child):
        return {a["type"] for a in compute_alerts(Child.objects.filter(id=child.id))}

    def test_consent_missing_on_open_pre_assessment(self):
        c = Child.objects.create(fullname="Ana", assigned_psychologist=self.psy)
        PreAssessment.objects.create(child=c, psychologist=self.psy, status="in_progress")
        self.assertIn("consent_missing", self._types_for(c))

    def test_no_consent_alert_when_signed(self):
        c = Child.objects.create(fullname="Ana", assigned_psychologist=self.psy)
        ConsentRecord.objects.create(child=c, status="signed")
        PreAssessment.objects.create(child=c, psychologist=self.psy, status="in_progress")
        self.assertNotIn("consent_missing", self._types_for(c))

    def test_pre_assessment_overdue_after_intake(self):
        c = Child.objects.create(fullname="Ben", assigned_psychologist=self.psy)
        Child.objects.filter(id=c.id).update(
            created_at=timezone.now() - timedelta(days=30))
        self.assertIn("pre_assessment_overdue", self._types_for(c))

    def test_report_missing_after_completed_pre_assessment(self):
        c = Child.objects.create(fullname="Cara", assigned_psychologist=self.psy)
        PreAssessment.objects.create(
            child=c, psychologist=self.psy, status="completed",
            completed_at=timezone.now() - timedelta(days=20))
        self.assertIn("report_missing", self._types_for(c))

    def test_no_report_alert_when_uploaded(self):
        c = Child.objects.create(fullname="Cara", assigned_psychologist=self.psy)
        PreAssessment.objects.create(
            child=c, psychologist=self.psy, status="completed",
            completed_at=timezone.now() - timedelta(days=20))
        PsychologicalReport.objects.create(child=c, author=self.psy, file="reports/x.pdf")
        self.assertNotIn("report_missing", self._types_for(c))

    def test_no_upcoming_appointment_flag(self):
        c = Child.objects.create(fullname="Dan", assigned_psychologist=self.psy)
        self.assertIn("no_upcoming_appointment", self._types_for(c))
        Appointment.objects.create(child=c, psychologist=self.psy,
                                   start=timezone.now() + timedelta(days=3))
        self.assertNotIn("no_upcoming_appointment", self._types_for(c))

    def test_inactive_children_ignored(self):
        c = Child.objects.create(fullname="Zed", assigned_psychologist=self.psy,
                                 status=Child.INACTIVE)
        self.assertEqual(compute_alerts(Child.objects.filter(id=c.id)), [])

    def test_dashboard_returns_census_and_gaps(self):
        Child.objects.create(fullname="Ana", case_type="Adoption",
                             assigned_psychologist=self.psy)
        token = self.client.post("/api/auth/login/", {
            "email": "a@racco1.gov.ph", "password": "pass1234"}).data["access"]
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + token)
        resp = self.client.get("/api/reports/dashboard/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["census"]["active"], 1)
        self.assertEqual(resp.data["census"]["by_case_type"], {"Adoption": 1})
        self.assertIn("today_schedule", resp.data)
        self.assertIn("intake_vs_termination", resp.data)
        self.assertTrue(any(g["type"] == "no_upcoming_appointment"
                            for g in resp.data["care_gaps"]))


class SelfReportConcernAlertTest(APITestCase):
    """The alert reads persisted flags. No text analysis runs inside
    compute_alerts — it is called on every page load."""

    def setUp(self):
        from clinical.models import (AgencyFormTemplate, OpinionnaireInvite,
                                     SelfReportFlag)
        role = Role.objects.create(role_name=Role.PSYCHOLOGIST)
        self.psy = User.objects.create_user(
            email="sp@racco1.gov.ph", username="sp", password="pass1234", role=role)
        self.other = User.objects.create_user(
            email="sq@racco1.gov.ph", username="sq", password="pass1234", role=role)
        self.mine = Child.objects.create(
            fullname="Maria Santos", assigned_psychologist=self.psy)
        self.theirs = Child.objects.create(
            fullname="Juan Dela Cruz", assigned_psychologist=self.other)
        template = AgencyFormTemplate.objects.create(
            title="Self-report",
            fields=[{"label": "How are you feeling this week?"}])
        invite = OpinionnaireInvite.objects.create(
            child=self.mine, template=template,
            status=OpinionnaireInvite.SUBMITTED, submitted_at=timezone.now(),
            expires_at=timezone.now() + timedelta(days=7))
        self.flag = SelfReportFlag.objects.create(
            invite=invite, child=self.mine,
            question="How are you feeling this week?",
            answer="Lagi akong umiiyak sa gabi.",
            source=SelfReportFlag.LEXICON, matched="umiiyak")

    def _alerts(self, child):
        return compute_alerts(Child.objects.filter(pk=child.pk))

    def _types(self, child):
        return [a["type"] for a in self._alerts(child)]

    def test_an_unreviewed_flag_raises_an_alert(self):
        self.assertIn("self_report_concern", self._types(self.mine))

    def test_the_alert_does_not_quote_the_child(self):
        # The message says a self-report is waiting. The words themselves
        # belong on her page beside the notes, not in a skimmed caseload list.
        alert = [a for a in self._alerts(self.mine)
                 if a["type"] == "self_report_concern"][0]
        self.assertNotIn("umiiyak", alert["message"])
        self.assertEqual("danger", alert["severity"])
        self.assertEqual("Maria Santos", alert["child_name"])

    def test_an_acknowledged_flag_raises_nothing(self):
        self.flag.reviewed_by = self.psy
        self.flag.reviewed_at = timezone.now()
        self.flag.save()
        self.assertNotIn("self_report_concern", self._types(self.mine))

    def test_it_is_scoped_to_the_children_passed_in(self):
        self.assertNotIn("self_report_concern", self._types(self.theirs))
