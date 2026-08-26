from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from accounts.models import Role
from children.models import Child
from clinical.models import AgencyFormTemplate, OpinionnaireInvite, SelfReportFlag

User = get_user_model()

FEELING = "How are you feeling this week?"


class SelfReportFlagModelTest(TestCase):
    def setUp(self):
        role = Role.objects.create(role_name=Role.PSYCHOLOGIST)
        self.psy = User.objects.create_user(
            email="p@racco1.gov.ph", username="p", password="pass1234", role=role)
        self.child = Child.objects.create(
            fullname="Maria Santos", assigned_psychologist=self.psy)
        self.template = AgencyFormTemplate.objects.create(
            title="Self-report", fields=[{"label": FEELING}])
        self.invite = OpinionnaireInvite.objects.create(
            child=self.child, template=self.template,
            expires_at=timezone.now() + timedelta(days=7))

    def _flag(self, **kw):
        return SelfReportFlag.objects.create(
            invite=self.invite, child=self.child, question=FEELING,
            answer="Lagi akong umiiyak sa gabi.",
            source=SelfReportFlag.LEXICON, matched="umiiyak", **kw)

    def test_stores_a_snapshot_of_the_question_and_answer(self):
        flag = self._flag()
        # Editing the template later must not rewrite what a child was asked.
        self.template.fields = [{"label": "Something else entirely"}]
        self.template.save()
        flag.refresh_from_db()
        self.assertEqual(FEELING, flag.question)
        self.assertEqual("Lagi akong umiiyak sa gabi.", flag.answer)

    def test_starts_unreviewed(self):
        self.assertFalse(self._flag().is_reviewed)

    def test_becomes_reviewed_when_acknowledged(self):
        flag = self._flag()
        flag.reviewed_by = self.psy
        flag.reviewed_at = timezone.now()
        flag.save()
        self.assertTrue(flag.is_reviewed)

    def test_records_which_detector_fired(self):
        self.assertEqual(SelfReportFlag.LEXICON, self._flag().source)

    def test_the_acknowledgement_survives_the_reviewer_being_deleted(self):
        flag = self._flag(reviewed_by=self.psy, reviewed_at=timezone.now())
        self.psy.delete()
        flag.refresh_from_db()
        self.assertIsNone(flag.reviewed_by)
        self.assertIsNotNone(flag.reviewed_at)

    def test_one_flag_per_question_and_source(self):
        # Re-scanning must be idempotent, so the same question cannot be
        # flagged twice by the same detector.
        from django.db import IntegrityError, transaction
        self._flag()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._flag()

    def test_both_detectors_may_flag_the_same_question(self):
        self._flag()
        other = SelfReportFlag.objects.create(
            invite=self.invite, child=self.child, question=FEELING,
            answer="Lagi akong umiiyak sa gabi.",
            source=SelfReportFlag.MODEL, matched="the child sounds distressed")
        self.assertEqual(2, SelfReportFlag.objects.count())
        self.assertEqual(SelfReportFlag.MODEL, other.source)
