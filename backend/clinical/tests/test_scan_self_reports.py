from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from accounts.models import Role
from children.models import Child
from clinical.models import AgencyFormTemplate, OpinionnaireInvite, SelfReportFlag

User = get_user_model()

FEELING = "How are you feeling this week?"


class ScanSelfReportsTest(TestCase):
    def setUp(self):
        role = Role.objects.create(role_name=Role.PSYCHOLOGIST)
        psy = User.objects.create_user(
            email="p@racco1.gov.ph", username="p", password="pass1234", role=role)
        child = Child.objects.create(
            fullname="Maria Santos", assigned_psychologist=psy)
        template = AgencyFormTemplate.objects.create(
            title="Self-report", fields=[{"label": FEELING}])
        self.invite = OpinionnaireInvite.objects.create(
            child=child, template=template,
            status=OpinionnaireInvite.SUBMITTED, submitted_at=timezone.now(),
            answers={FEELING: "Lagi akong umiiyak sa gabi."},
            expires_at=timezone.now() + timedelta(days=7))

    def _run(self, *args):
        out = StringIO()
        call_command("scan_self_reports", *args, stdout=out)
        return out.getvalue()

    def test_creates_flags_for_existing_submissions(self):
        self._run()
        self.assertEqual(1, SelfReportFlag.objects.count())

    def test_is_idempotent(self):
        self._run()
        self._run()
        self.assertEqual(1, SelfReportFlag.objects.count())

    def test_reports_what_it_did(self):
        self.assertIn("1 submissions", self._run())

    def test_skips_unsubmitted_invites(self):
        self.invite.status = OpinionnaireInvite.PENDING
        self.invite.save()
        self._run()
        self.assertEqual(0, SelfReportFlag.objects.count())

    def test_does_not_call_the_model_by_default(self):
        # Opt-in: 122 records at roughly two seconds each is four minutes.
        with patch("clinical.self_report_model_check.run_model_check") as run:
            self._run()
        run.assert_not_called()

    def test_calls_the_model_when_asked(self):
        with patch("clinical.self_report_model_check.run_model_check") as run:
            self._run("--with-model")
        run.assert_called_once_with(self.invite.pk)

    def test_a_calm_submission_creates_nothing(self):
        self.invite.answers = {FEELING: "I feel safe. Ang bait ng nag-aalaga sa akin."}
        self.invite.save()
        self._run()
        self.assertEqual(0, SelfReportFlag.objects.count())
