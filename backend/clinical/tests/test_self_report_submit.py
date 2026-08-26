"""The public survey endpoint creates flags as a side effect.

This endpoint is unauthenticated and token-gated — it is reached from a child's
own device. It must stay fast, and it must never fail because of flagging.
"""
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import Role
from children.models import Child
from clinical.models import AgencyFormTemplate, OpinionnaireInvite, SelfReportFlag

User = get_user_model()

FEELING = "How are you feeling this week?"
ISOLATION = "Who do you talk to when you are sad?"


class SubmitFlaggingTest(APITestCase):
    def setUp(self):
        role = Role.objects.create(role_name=Role.PSYCHOLOGIST)
        psy = User.objects.create_user(
            email="p@racco1.gov.ph", username="p", password="pass1234", role=role)
        self.child = Child.objects.create(
            fullname="Maria Santos", assigned_psychologist=psy)
        self.template = AgencyFormTemplate.objects.create(
            title="Self-report",
            fields=[{"label": FEELING}, {"label": ISOLATION}])
        self.invite = OpinionnaireInvite.objects.create(
            child=self.child, template=self.template,
            expires_at=timezone.now() + timedelta(days=7))
        self.url = f"/api/opinionnaire/{self.invite.token}/submit/"

    def _submit(self, answers):
        # The model detector is patched out throughout: it runs in a thread and
        # this task is only about the synchronous path.
        with patch("clinical.views.start_model_check"):
            return self.client.post(self.url, {"answers": answers}, format="json")

    def test_a_distress_answer_creates_a_flag(self):
        res = self._submit({FEELING: "Lagi akong umiiyak sa gabi."})
        self.assertEqual(200, res.status_code)
        flag = SelfReportFlag.objects.get()
        self.assertEqual(self.child, flag.child)
        self.assertEqual(SelfReportFlag.LEXICON, flag.source)
        self.assertEqual("umiiyak", flag.matched)

    def test_the_flag_snapshots_the_question_and_answer(self):
        self._submit({FEELING: "Lagi akong umiiyak sa gabi."})
        flag = SelfReportFlag.objects.get()
        self.assertEqual(FEELING, flag.question)
        self.assertEqual("Lagi akong umiiyak sa gabi.", flag.answer)

    def test_a_calm_answer_creates_no_flag(self):
        self._submit({FEELING: "I feel safe. Ang bait ng nag-aalaga sa akin."})
        self.assertEqual(0, SelfReportFlag.objects.count())

    def test_nobody_flags_only_against_the_isolation_question(self):
        self._submit({FEELING: "Nobody", ISOLATION: "Nobody"})
        flags = SelfReportFlag.objects.all()
        self.assertEqual(1, flags.count())
        self.assertEqual(ISOLATION, flags[0].question)

    def test_the_submission_still_succeeds_when_flagging_raises(self):
        # Flagging must never cost a child her submission.
        with patch("clinical.views.detect_concerns", side_effect=RuntimeError("boom")):
            with patch("clinical.views.start_model_check"):
                res = self.client.post(
                    self.url, {"answers": {FEELING: "Lagi akong umiiyak"}},
                    format="json")
        self.assertEqual(200, res.status_code)
        self.invite.refresh_from_db()
        self.assertEqual(OpinionnaireInvite.SUBMITTED, self.invite.status)

    def test_the_submission_still_succeeds_when_the_model_thread_cannot_start(self):
        with patch("clinical.views.start_model_check", side_effect=RuntimeError("boom")):
            res = self.client.post(
                self.url, {"answers": {FEELING: "Okay lang."}}, format="json")
        self.assertEqual(200, res.status_code)

    def test_the_answers_are_still_saved(self):
        self._submit({FEELING: "Lagi akong umiiyak sa gabi."})
        self.invite.refresh_from_db()
        self.assertEqual("Lagi akong umiiyak sa gabi.", self.invite.answers[FEELING])

    def test_the_model_pass_is_started(self):
        with patch("clinical.views.start_model_check") as start:
            self.client.post(self.url, {"answers": {FEELING: "Okay lang."}},
                             format="json")
        start.assert_called_once_with(self.invite.pk)
