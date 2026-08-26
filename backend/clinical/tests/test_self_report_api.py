from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import Role
from children.models import Child
from clinical.models import AgencyFormTemplate, OpinionnaireInvite, SelfReportFlag

User = get_user_model()

FEELING = "How are you feeling this week?"
URL = "/api/self-report-flags/"


def _make_flag(child, template):
    invite = OpinionnaireInvite.objects.create(
        child=child, template=template,
        status=OpinionnaireInvite.SUBMITTED, submitted_at=timezone.now(),
        expires_at=timezone.now() + timedelta(days=7))
    return SelfReportFlag.objects.create(
        invite=invite, child=child, question=FEELING,
        answer="Lagi akong umiiyak sa gabi.",
        source=SelfReportFlag.LEXICON, matched="umiiyak")


class SelfReportApiTest(APITestCase):
    def setUp(self):
        psy_role = Role.objects.create(role_name=Role.PSYCHOLOGIST)
        admin_role = Role.objects.create(role_name=Role.ADMINISTRATOR)
        self.psy = User.objects.create_user(
            email="p@racco1.gov.ph", username="p", password="pass1234", role=psy_role)
        self.other = User.objects.create_user(
            email="q@racco1.gov.ph", username="q", password="pass1234", role=psy_role)
        self.admin = User.objects.create_user(
            email="a@racco1.gov.ph", username="a", password="pass1234", role=admin_role)
        self.mine = Child.objects.create(
            fullname="Maria Santos", assigned_psychologist=self.psy)
        self.theirs = Child.objects.create(
            fullname="Juan Dela Cruz", assigned_psychologist=self.other)
        template = AgencyFormTemplate.objects.create(
            title="Self-report", fields=[{"label": FEELING}])
        self.mine_flag = _make_flag(self.mine, template)
        self.theirs_flag = _make_flag(self.theirs, template)

    def test_a_psychologist_sees_only_their_own_childrens_flags(self):
        self.client.force_authenticate(self.psy)
        ids = [f["id"] for f in self.client.get(URL).data]
        self.assertIn(self.mine_flag.id, ids)
        self.assertNotIn(self.theirs_flag.id, ids)

    def test_an_administrator_sees_every_flag(self):
        self.client.force_authenticate(self.admin)
        ids = [f["id"] for f in self.client.get(URL).data]
        self.assertIn(self.theirs_flag.id, ids)

    def test_anonymous_is_refused(self):
        self.assertIn(self.client.get(URL).status_code, (401, 403))

    def test_the_payload_carries_the_words_and_the_reason(self):
        self.client.force_authenticate(self.psy)
        row = self.client.get(URL).data[0]
        self.assertEqual(FEELING, row["question"])
        self.assertEqual("Lagi akong umiiyak sa gabi.", row["answer"])
        self.assertEqual("umiiyak", row["matched"])
        self.assertFalse(row["is_reviewed"])

    def test_filtering_by_child(self):
        self.client.force_authenticate(self.admin)
        rows = self.client.get(f"{URL}?child={self.mine.id}").data
        self.assertEqual([self.mine_flag.id], [r["id"] for r in rows])

    def test_a_nonsense_child_filter_returns_nothing(self):
        self.client.force_authenticate(self.admin)
        self.assertEqual([], list(self.client.get(f"{URL}?child=abc").data))

    def test_acknowledging_records_who_and_when(self):
        self.client.force_authenticate(self.psy)
        res = self.client.post(f"{URL}{self.mine_flag.id}/acknowledge/",
                               {"note": "Called the house parent."}, format="json")
        self.assertEqual(200, res.status_code)
        self.mine_flag.refresh_from_db()
        self.assertEqual(self.psy, self.mine_flag.reviewed_by)
        self.assertIsNotNone(self.mine_flag.reviewed_at)
        self.assertEqual("Called the house parent.", self.mine_flag.review_note)

    def test_cannot_acknowledge_another_psychologists_flag(self):
        self.client.force_authenticate(self.psy)
        res = self.client.post(f"{URL}{self.theirs_flag.id}/acknowledge/",
                               {}, format="json")
        self.assertEqual(404, res.status_code)

    def test_acknowledging_twice_does_not_rewrite_the_first_reviewer(self):
        # The record of who actually read it first must survive whoever
        # clicked next.
        self.client.force_authenticate(self.psy)
        self.client.post(f"{URL}{self.mine_flag.id}/acknowledge/", {}, format="json")
        first = SelfReportFlag.objects.get(pk=self.mine_flag.pk).reviewed_at
        self.client.force_authenticate(self.admin)
        self.client.post(f"{URL}{self.mine_flag.id}/acknowledge/", {}, format="json")
        self.mine_flag.refresh_from_db()
        self.assertEqual(first, self.mine_flag.reviewed_at)
        self.assertEqual(self.psy, self.mine_flag.reviewed_by)


class CarryHistoryExemptionTest(APITestCase):
    """Self-reports are the child's own words, not carried history. They reach
    the psychologist responsible for her now, regardless of the control."""

    def test_a_flag_is_visible_with_history_switched_off(self):
        role = Role.objects.create(role_name=Role.PSYCHOLOGIST)
        psy = User.objects.create_user(
            email="p@racco1.gov.ph", username="p", password="pass1234", role=role)
        child = Child.objects.create(
            fullname="Maria Santos", assigned_psychologist=psy,
            assignee_sees_history=False)
        template = AgencyFormTemplate.objects.create(
            title="Self-report", fields=[{"label": FEELING}])
        _make_flag(child, template)

        self.client.force_authenticate(psy)
        self.assertEqual(1, len(self.client.get(URL).data))
