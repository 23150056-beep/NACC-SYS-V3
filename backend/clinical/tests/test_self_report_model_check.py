"""The model is a second detector. It can only add flags, never clear one."""
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from accounts.models import Role
from assistant.models import AssistantJob, AssistantSetting
from assistant.services import AIUnavailable
from children.models import Child
from clinical.models import AgencyFormTemplate, OpinionnaireInvite, SelfReportFlag
from clinical.self_report_model_check import _parse, run_model_check

User = get_user_model()

FEELING = "How are you feeling this week?"


class ParseReplyTest(TestCase):
    """Never flag on a reply we did not understand. A flag nobody can explain
    is worse than no flag."""

    def test_a_yes_yields_the_reason(self):
        self.assertEqual("the child sounds overwhelmed",
                         _parse("YES - the child sounds overwhelmed"))

    def test_a_no_yields_nothing(self):
        self.assertIsNone(_parse("NO - the child sounds settled"))

    def test_an_unparseable_reply_yields_nothing(self):
        self.assertIsNone(_parse("I think perhaps maybe"))

    def test_blank_yields_nothing(self):
        self.assertIsNone(_parse(""))
        self.assertIsNone(_parse(None))

    def test_a_yes_with_no_reason_still_yields_something_sayable(self):
        self.assertTrue(_parse("YES"))


class ModelCheckTest(TestCase):
    def setUp(self):
        role = Role.objects.create(role_name=Role.PSYCHOLOGIST)
        psy = User.objects.create_user(
            email="p@racco1.gov.ph", username="p", password="pass1234", role=role)
        self.child = Child.objects.create(
            fullname="Maria Santos", assigned_psychologist=psy)
        template = AgencyFormTemplate.objects.create(
            title="Self-report", fields=[{"label": FEELING}])
        self.invite = OpinionnaireInvite.objects.create(
            child=self.child, template=template,
            status=OpinionnaireInvite.SUBMITTED, submitted_at=timezone.now(),
            answers={FEELING: "Kasla nagbaliw ti riknak."},
            expires_at=timezone.now() + timedelta(days=7))
        cfg = AssistantSetting.load()
        cfg.enabled = True
        cfg.save()

    def _run(self, reply):
        with patch("assistant.services.OllamaClient.generate", return_value=reply):
            run_model_check(self.invite.pk)

    def test_a_yes_creates_a_model_flag(self):
        self._run("YES - the child sounds overwhelmed")
        flag = SelfReportFlag.objects.get()
        self.assertEqual(SelfReportFlag.MODEL, flag.source)
        self.assertIn("overwhelmed", flag.matched)
        self.assertEqual(self.child, flag.child)

    def test_a_no_creates_nothing(self):
        self._run("NO - the child sounds settled")
        self.assertEqual(0, SelfReportFlag.objects.count())

    def test_an_unparseable_reply_creates_nothing(self):
        self._run("I think perhaps maybe")
        self.assertEqual(0, SelfReportFlag.objects.count())

    def test_it_never_removes_a_lexicon_flag(self):
        SelfReportFlag.objects.create(
            invite=self.invite, child=self.child, question=FEELING,
            answer="Kasla nagbaliw ti riknak.",
            source=SelfReportFlag.LEXICON, matched="riknak")
        self._run("NO - the child sounds settled")
        self.assertEqual(1, SelfReportFlag.objects.count())
        self.assertEqual(SelfReportFlag.LEXICON, SelfReportFlag.objects.get().source)

    def test_the_runtime_being_down_is_not_an_error(self):
        with patch("assistant.services.OllamaClient.generate",
                   side_effect=AIUnavailable("refused")):
            run_model_check(self.invite.pk)          # must not raise
        self.assertEqual(0, SelfReportFlag.objects.count())

    def test_the_runtime_being_down_is_audited(self):
        with patch("assistant.services.OllamaClient.generate",
                   side_effect=AIUnavailable("refused")):
            run_model_check(self.invite.pk)
        job = AssistantJob.objects.get()
        self.assertEqual("self_report", job.job_type)
        self.assertFalse(job.ok)

    def test_it_does_nothing_when_the_assistant_is_off(self):
        cfg = AssistantSetting.load()
        cfg.enabled = False
        cfg.save()
        with patch("assistant.services.OllamaClient.generate") as gen:
            run_model_check(self.invite.pk)
        gen.assert_not_called()

    def test_running_twice_does_not_duplicate(self):
        self._run("YES - sounds distressed")
        self._run("YES - sounds distressed")
        self.assertEqual(1, SelfReportFlag.objects.count())

    def test_a_missing_invite_is_not_an_error(self):
        run_model_check(999999)                      # must not raise

    def test_a_blank_answer_is_skipped(self):
        self.invite.answers = {FEELING: "   "}
        self.invite.save()
        with patch("assistant.services.OllamaClient.generate") as gen:
            run_model_check(self.invite.pk)
        gen.assert_not_called()
