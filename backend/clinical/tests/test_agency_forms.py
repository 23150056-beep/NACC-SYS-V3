from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from django.core.management import call_command
from accounts.models import Role
from children.models import Child
from clinical.models import AgencyFormTemplate

User = get_user_model()


class AgencyFormsBase(APITestCase):
    def setUp(self):
        self.admin_role = Role.objects.create(role_name=Role.ADMINISTRATOR)
        self.psy_role = Role.objects.create(role_name=Role.PSYCHOLOGIST)
        self.admin = User.objects.create_user(
            email="a@racco1.gov.ph", username="a", password="pass1234", role=self.admin_role)
        self.psy = User.objects.create_user(
            email="p@racco1.gov.ph", username="p", password="pass1234", role=self.psy_role)
        self.other = User.objects.create_user(
            email="o@racco1.gov.ph", username="o", password="pass1234", role=self.psy_role)
        self.child = Child.objects.create(
            fullname="Ana", case_type="Foster Care", assigned_psychologist=self.psy)

    def _auth(self, email):
        token = self.client.post("/api/auth/login/", {
            "email": email, "password": "pass1234"}).data["access"]
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + token)


class TemplateBodyTest(AgencyFormsBase):
    def test_body_roundtrips_through_api(self):
        self._auth("a@racco1.gov.ph")
        resp = self.client.post("/api/form-templates/", {
            "form_type": "consent", "title": "Consent X",
            "body": "Intro paragraph.\n\n## I. PURPOSE\nBody text.",
            "fields": [], "attestation": True}, format="json")
        self.assertEqual(resp.status_code, 201)
        self.assertIn("## I. PURPOSE", resp.data["body"])
        self.assertEqual(AgencyFormTemplate.objects.get(pk=resp.data["id"]).body,
                         "Intro paragraph.\n\n## I. PURPOSE\nBody text.")

    def test_body_edit_bumps_version(self):
        self._auth("a@racco1.gov.ph")
        created = self.client.post("/api/form-templates/", {
            "form_type": "consent", "title": "Consent X", "body": "v1 text",
            "fields": [], "attestation": True}, format="json")
        resp = self.client.patch(f"/api/form-templates/{created.data['id']}/", {
            "body": "v2 text", "attestation": True}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["version"], 2)


class InterviewRespondentTest(AgencyFormsBase):
    def test_respondent_roundtrips_through_api(self):
        self._auth("p@racco1.gov.ph")
        resp = self.client.post("/api/interviews/", {
            "child": self.child.id, "answers": {"Q": "A"},
            "respondent": "Custodian/PAP"}, format="json")
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data["respondent"], "Custodian/PAP")
        listed = self.client.get(f"/api/interviews/?child={self.child.id}")
        self.assertEqual(listed.data[0]["respondent"], "Custodian/PAP")


class SharedTemplateAccessTest(AgencyFormsBase):
    def setUp(self):
        super().setUp()
        self.shared = AgencyFormTemplate.objects.create(
            form_type="consent", title="Official Consent", owner=None,
            attestation=True, active=True)
        self.own = AgencyFormTemplate.objects.create(
            form_type="consent", title="My Consent", owner=self.psy,
            attestation=True, active=True)
        self.others = AgencyFormTemplate.objects.create(
            form_type="consent", title="Other Consent", owner=self.other,
            attestation=True, active=True)

    def test_psychologist_sees_own_and_shared_only(self):
        self._auth("p@racco1.gov.ph")
        resp = self.client.get("/api/form-templates/")
        self.assertEqual({t["title"] for t in resp.data},
                         {"Official Consent", "My Consent"})

    def test_psychologist_cannot_edit_shared_template(self):
        self._auth("p@racco1.gov.ph")
        resp = self.client.patch(f"/api/form-templates/{self.shared.id}/", {
            "title": "Renamed", "attestation": True}, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_psychologist_cannot_deactivate_shared_template(self):
        self._auth("p@racco1.gov.ph")
        resp = self.client.post(f"/api/form-templates/{self.shared.id}/deactivate/")
        self.assertEqual(resp.status_code, 403)

    def test_admin_can_edit_shared_template(self):
        self._auth("a@racco1.gov.ph")
        resp = self.client.patch(f"/api/form-templates/{self.shared.id}/", {
            "title": "Official Consent (2025)", "attestation": True}, format="json")
        self.assertEqual(resp.status_code, 200)

    def test_psychologist_cannot_touch_other_owned_template(self):
        self._auth("p@racco1.gov.ph")
        resp = self.client.patch(f"/api/form-templates/{self.others.id}/", {
            "title": "Renamed", "attestation": True}, format="json")
        self.assertEqual(resp.status_code, 404)

    def test_psychologist_cannot_reassign_owner(self):
        self._auth("p@racco1.gov.ph")
        resp = self.client.patch(f"/api/form-templates/{self.own.id}/", {
            "owner": None, "attestation": True}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.own.refresh_from_db()
        self.assertEqual(self.own.owner_id, self.psy.id)


class SeedAgencyFormsTest(APITestCase):
    def test_seed_creates_three_templates_idempotently(self):
        call_command("seed_agency_forms")
        self.assertEqual(AgencyFormTemplate.objects.count(), 3)

        consent = AgencyFormTemplate.objects.get(form_type="consent")
        self.assertEqual(consent.title,
                         "Informed Consent for Psychological Evaluation (Adoption)")
        self.assertEqual(consent.fields, [])
        for heading in ["## I. PURPOSE", "## II. NATURE", "## III. VOLUNTARY",
                        "## IV. CONFIDENTIALITY", "## V. RISKS", "## VI. BENEFITS",
                        "## VII. FEES", "## VIII. ACCURACY", "## IX. QUESTIONS",
                        "## X. CONSENT"]:
            self.assertIn(heading, consent.body)

        pap = AgencyFormTemplate.objects.get(
            title="Adoption Pre-Assessment Questionnaire — Custodian/PAP")
        self.assertEqual(
            len([f for f in pap.fields if f["field_type"] == "section"]), 9)
        self.assertEqual(
            len([f for f in pap.fields if f["field_type"] == "long_text"]), 42)

        kid = AgencyFormTemplate.objects.get(
            title="Adoption Pre-Assessment Questionnaire — Child")
        self.assertEqual(
            len([f for f in kid.fields if f["field_type"] == "section"]), 8)
        self.assertEqual(
            len([f for f in kid.fields if f["field_type"] == "long_text"]), 38)
        self.assertIn("age", kid.body)

        for t in AgencyFormTemplate.objects.all():
            self.assertIsNone(t.owner)
            self.assertTrue(t.attestation)
            self.assertIsNotNone(t.attested_at)

        # Re-run: no duplicates, and in-app edits are preserved.
        consent.body = "EDITED"
        consent.save()
        call_command("seed_agency_forms")
        self.assertEqual(AgencyFormTemplate.objects.count(), 3)
        consent.refresh_from_db()
        self.assertEqual(consent.body, "EDITED")
