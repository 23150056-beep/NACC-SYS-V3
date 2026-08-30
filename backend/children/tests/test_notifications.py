import urllib.error
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APITestCase

from accounts.models import Role, User
from children.models import Child
from children.notifications import (
    _post, build_payload, build_temporary_password_payload,
    send_assignment_notification, send_temporary_password_notification,
)


@override_settings(BREVO_API_KEY="test-key", BREVO_SENDER_EMAIL="from@racco1.gov.ph",
                   BREVO_SENDER_NAME="NACC RACCO1")
class AssignmentEmailContentTest(TestCase):
    """What leaves the building. Brevo is a processor outside the agency's
    data-processing agreements, so this asserts the absence of case data as
    strictly as it asserts the presence of the case number."""

    def setUp(self):
        self.psych_role = Role.objects.create(role_name=Role.PSYCHOLOGIST)
        self.psych = User.objects.create_user(
            email="p@racco1.gov.ph", username="p", password="x",
            role=self.psych_role, first_name="Maria", last_name="Dela Cruz")

    def test_case_number_is_included(self):
        body = build_payload(self.psych, 4021)["htmlContent"]
        self.assertIn("4021", body)

    def test_the_child_is_never_named(self):
        child = Child.objects.create(fullname="Ana Reyes", case_type="Adoption",
                                     assigned_psychologist=self.psych)
        body = build_payload(self.psych, child.id)["htmlContent"]
        self.assertNotIn("Ana", body)
        self.assertNotIn("Reyes", body)
        self.assertNotIn("Adoption", body)

    def test_it_goes_to_the_psychologist(self):
        payload = build_payload(self.psych, 1)
        self.assertEqual(payload["to"][0]["email"], "p@racco1.gov.ph")

    def test_no_api_key_means_no_send(self):
        child = Child.objects.create(fullname="Ana Reyes", assigned_psychologist=self.psych)
        with override_settings(BREVO_API_KEY=""):
            self.assertFalse(send_assignment_notification(child))

    def test_an_unassigned_child_sends_nothing(self):
        child = Child.objects.create(fullname="Ana Reyes")
        self.assertFalse(send_assignment_notification(child))

    def test_a_psychologist_without_an_address_sends_nothing(self):
        self.psych.email = ""
        self.psych.save(update_fields=["email"])
        child = Child.objects.create(fullname="Ana Reyes", assigned_psychologist=self.psych)
        self.assertFalse(send_assignment_notification(child))

    def test_temporary_password_is_sent_to_the_user(self):
        payload = build_temporary_password_payload(self.psych, "TempPass9")
        self.assertEqual(payload["to"][0]["email"], "p@racco1.gov.ph")
        self.assertIn("TempPass9", payload["htmlContent"])

    def test_temporary_password_without_an_address_sends_nothing(self):
        self.psych.email = ""
        self.psych.save(update_fields=["email"])
        self.assertFalse(send_temporary_password_notification(self.psych, "TempPass9"))


@override_settings(BREVO_API_KEY="test-key")
class BrevoFailureLoggingTest(SimpleTestCase):
    """More than one kind of message goes through _post. A failure that does
    not name which one sends whoever is reading the logs to the wrong
    feature — this pins the name to the message."""

    def _failing_post(self, description):
        with patch("children.notifications.urllib.request.urlopen",
                   side_effect=urllib.error.URLError("no route")):
            with self.assertLogs("children.notifications", level="ERROR") as captured:
                self.assertFalse(_post({}, description))
        return "\n".join(captured.output)

    def test_a_failed_temporary_password_email_says_so(self):
        logged = self._failing_post("temporary password email")
        self.assertIn("temporary password email", logged)
        self.assertNotIn("assignment email", logged)

    def test_a_failed_assignment_email_still_says_so(self):
        self.assertIn("assignment email", self._failing_post("assignment email"))


@override_settings(BREVO_API_KEY="test-key")
class AssignmentEmailTriggerTest(APITestCase):
    """When it fires: on assignment, and on a *change* of assignee — not on
    every edit to an already-assigned case."""

    def setUp(self):
        self.admin_role = Role.objects.create(role_name=Role.ADMINISTRATOR)
        self.psych_role = Role.objects.create(role_name=Role.PSYCHOLOGIST)
        self.admin = User.objects.create_user(
            email="admin@racco1.gov.ph", username="admin", password="admin1234",
            role=self.admin_role)
        self.psych = User.objects.create_user(
            email="p@racco1.gov.ph", username="p", password="x", role=self.psych_role)
        self.other = User.objects.create_user(
            email="p2@racco1.gov.ph", username="p2", password="x", role=self.psych_role)
        token = self.client.post("/api/auth/login/", {
            "email": "admin@racco1.gov.ph", "password": "admin1234"}).data["access"]
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + token)

    @patch("children.views.send_assignment_notification")
    def test_creating_with_an_assignee_notifies(self, mock_send):
        resp = self.client.post("/api/children/", {
            "fullname": "Nico Reyes", "gender": "Male",
            "case_type": "Foster Care", "psychologist": self.psych.id,
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        mock_send.assert_called_once()

    @patch("children.views.send_assignment_notification")
    def test_creating_without_an_assignee_does_not(self, mock_send):
        resp = self.client.post("/api/children/", {
            "fullname": "Nico Reyes", "gender": "Male", "case_type": "Foster Care",
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        mock_send.assert_not_called()

    @patch("children.views.send_assignment_notification")
    def test_reassigning_notifies_the_new_psychologist(self, mock_send):
        child = Child.objects.create(fullname="Nico Reyes", assigned_psychologist=self.psych)
        resp = self.client.patch(f"/api/children/{child.id}/",
                                 {"psychologist": self.other.id}, format="json")
        self.assertEqual(resp.status_code, 200, resp.data)
        mock_send.assert_called_once()

    @patch("children.views.send_assignment_notification")
    def test_editing_an_assigned_case_does_not_re_notify(self, mock_send):
        child = Child.objects.create(fullname="Nico Reyes", assigned_psychologist=self.psych)
        resp = self.client.patch(f"/api/children/{child.id}/",
                                 {"medical_notes": "Updated."}, format="json")
        self.assertEqual(resp.status_code, 200, resp.data)
        mock_send.assert_not_called()
