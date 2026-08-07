from rest_framework import status
from rest_framework.test import APITestCase
from accounts.models import Role
from children.models import Child, TerminationRecord
from children.tests.test_child_collab import make_user


class ReopenTests(APITestCase):
    def setUp(self):
        self.admin = make_user("ra@t.ph", Role.ADMINISTRATOR)
        self.psych = make_user("rp@t.ph", Role.PSYCHOLOGIST)
        self.child = Child.objects.create(
            fullname="Back Again", status=Child.INACTIVE,
            case_status=Child.STAGE_TERMINATED, assigned_psychologist=self.psych)
        TerminationRecord.objects.create(
            child=self.child, terminated_by=self.psych,
            reason_category="Services completed", note="Done for now.")

    def test_admin_reopen_restores_active_and_keeps_history(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post(f"/api/children/{self.child.id}/reopen/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.child.refresh_from_db()
        self.assertEqual(self.child.status, Child.ACTIVE)
        self.assertEqual(self.child.case_status, Child.STAGE_PRE_ASSESSMENT)
        self.assertEqual(self.child.terminations.count(), 1)  # history kept

    def test_reopen_resets_assigned_psychologist_but_keeps_details(self):
        # A reopened case returns to the pool unassigned — staff/admin pick
        # the (possibly different) psychologist fresh. Everything else stays.
        self.child.case_type = "Foster Care"
        self.child.save(update_fields=["case_type"])
        self.client.force_authenticate(self.admin)
        r = self.client.post(f"/api/children/{self.child.id}/reopen/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.child.refresh_from_db()
        self.assertIsNone(self.child.assigned_psychologist)
        self.assertEqual(self.child.fullname, "Back Again")
        self.assertEqual(self.child.case_type, "Foster Care")
        self.assertEqual(self.child.terminations.count(), 1)

    def test_non_admin_cannot_reopen(self):
        self.client.force_authenticate(self.psych)
        r = self.client.post(f"/api/children/{self.child.id}/reopen/")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_reopen_active_child_400(self):
        self.client.force_authenticate(self.admin)
        active = Child.objects.create(fullname="Still Active")
        r = self.client.post(f"/api/children/{active.id}/reopen/")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_serializer_exposes_termination_history(self):
        self.client.force_authenticate(self.admin)
        r = self.client.get(f"/api/children/{self.child.id}/")
        self.assertEqual(len(r.data["terminations"]), 1)
        self.assertEqual(r.data["terminations"][0]["reason_category"], "Services completed")
