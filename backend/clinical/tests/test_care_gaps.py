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
