from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from accounts.models import Role
from samd.checklist import ITEM_INDEX
from samd.models import SamdAssessment, SamdResponse

User = get_user_model()

ALL_KEYS = list(ITEM_INDEX.keys())


class SamdTestBase(APITestCase):
    def setUp(self):
        self.admin_role = Role.objects.create(role_name=Role.ADMINISTRATOR)
        self.psy_role = Role.objects.create(role_name=Role.PSYCHOLOGIST)
        self.staff_role = Role.objects.create(role_name=Role.STAFF)
        self.admin = User.objects.create_user(
            email="a@racco1.gov.ph", username="a", password="pass1234", role=self.admin_role)
        self.psy = User.objects.create_user(
            email="p@racco1.gov.ph", username="p", password="pass1234", role=self.psy_role)
        self.staff = User.objects.create_user(
            email="s@racco1.gov.ph", username="s", password="pass1234", role=self.staff_role)

    def _auth(self, email):
        token = self.client.post("/api/auth/login/", {
            "email": email, "password": "pass1234"}).data["access"]
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + token)


class PermissionsTest(SamdTestBase):
    def test_staff_forbidden_everywhere(self):
        self._auth("s@racco1.gov.ph")
        assessment = SamdAssessment.objects.create(label="R1")
        self.assertEqual(self.client.get("/api/samd/checklist/").status_code, 403)
        self.assertEqual(self.client.get("/api/samd/assessments/").status_code, 403)
        self.assertEqual(self.client.post("/api/samd/assessments/", {}, format="json").status_code, 403)
        self.assertEqual(self.client.get(f"/api/samd/assessments/{assessment.id}/").status_code, 403)
        self.assertEqual(self.client.post(
            f"/api/samd/assessments/{assessment.id}/respond/",
            {"item_key": "I.1", "compliance": "yes"}, format="json").status_code, 403)
        self.assertEqual(self.client.post(f"/api/samd/assessments/{assessment.id}/complete/").status_code, 403)

    def test_psychologist_forbidden_everywhere(self):
        self._auth("p@racco1.gov.ph")
        assessment = SamdAssessment.objects.create(label="R1")
        self.assertEqual(self.client.get("/api/samd/checklist/").status_code, 403)
        self.assertEqual(self.client.get("/api/samd/assessments/").status_code, 403)
        self.assertEqual(self.client.post(
            f"/api/samd/assessments/{assessment.id}/respond/",
            {"item_key": "I.1", "compliance": "yes"}, format="json").status_code, 403)

    def test_admin_allowed(self):
        self._auth("a@racco1.gov.ph")
        self.assertEqual(self.client.get("/api/samd/checklist/").status_code, 200)
        self.assertEqual(self.client.get("/api/samd/assessments/").status_code, 200)
        resp = self.client.post("/api/samd/assessments/", {"label": "Q3 2026"}, format="json")
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data["label"], "Q3 2026")


class RespondTest(SamdTestBase):
    def setUp(self):
        super().setUp()
        self._auth("a@racco1.gov.ph")
        self.assessment = SamdAssessment.objects.create(label="R1", created_by=self.admin)

    def _respond(self, item_key, compliance="yes", remarks=""):
        return self.client.post(
            f"/api/samd/assessments/{self.assessment.id}/respond/",
            {"item_key": item_key, "compliance": compliance, "remarks": remarks}, format="json")

    def test_upsert_creates_then_changes(self):
        resp1 = self._respond("I.1", "yes")
        self.assertEqual(resp1.status_code, 200)
        self.assertEqual(SamdResponse.objects.get(assessment=self.assessment, item_key="I.1").compliance, "yes")

        resp2 = self._respond("I.1", "not")
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(SamdResponse.objects.filter(assessment=self.assessment, item_key="I.1").count(), 1)
        self.assertEqual(SamdResponse.objects.get(assessment=self.assessment, item_key="I.1").compliance, "not")

    def test_unknown_item_key_400(self):
        resp = self._respond("ZZZ.99", "yes")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("item_key", resp.data)

    def test_bad_compliance_400(self):
        resp = self._respond("I.1", "maybe")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("compliance", resp.data)

    def test_clearing_compliance_keeps_row_if_remarks_present(self):
        self._respond("I.1", "yes")
        resp = self._respond("I.1", "", remarks="still checking")
        self.assertEqual(resp.status_code, 200)
        row = SamdResponse.objects.get(assessment=self.assessment, item_key="I.1")
        self.assertEqual(row.compliance, "")
        self.assertEqual(row.remarks, "still checking")

    def test_clearing_both_deletes_row(self):
        self._respond("I.1", "yes", remarks="note")
        resp = self._respond("I.1", "", remarks="")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(SamdResponse.objects.filter(assessment=self.assessment, item_key="I.1").exists())

    def test_respond_on_completed_assessment_400(self):
        self.client.post(f"/api/samd/assessments/{self.assessment.id}/complete/")
        resp = self._respond("I.1", "yes")
        self.assertEqual(resp.status_code, 400)


class ScoringTest(SamdTestBase):
    def setUp(self):
        super().setUp()
        self._auth("a@racco1.gov.ph")
        self.assessment = SamdAssessment.objects.create(label="R1", created_by=self.admin)

    def _detail(self):
        return self.client.get(f"/api/samd/assessments/{self.assessment.id}/").data

    def test_per_kra_and_overall_math(self):
        # KRA I: answer all 11 -> 8 yes, 2 not, 1 na, 0 unanswered.
        kra_i_keys = [f"I.{n}" for n in range(1, 12)]
        for key in kra_i_keys[:8]:
            SamdResponse.objects.create(assessment=self.assessment, item_key=key, compliance="yes")
        for key in kra_i_keys[8:10]:
            SamdResponse.objects.create(assessment=self.assessment, item_key=key, compliance="not")
        SamdResponse.objects.create(assessment=self.assessment, item_key=kra_i_keys[10], compliance="na")

        # KRA II: answer only 5 of 51 (rest unanswered) -> 3 yes, 1 not, 1 na.
        kra_ii_keys = [f"II.{n}" for n in range(1, 6)]
        SamdResponse.objects.create(assessment=self.assessment, item_key=kra_ii_keys[0], compliance="yes")
        SamdResponse.objects.create(assessment=self.assessment, item_key=kra_ii_keys[1], compliance="yes")
        SamdResponse.objects.create(assessment=self.assessment, item_key=kra_ii_keys[2], compliance="yes")
        SamdResponse.objects.create(assessment=self.assessment, item_key=kra_ii_keys[3], compliance="not")
        SamdResponse.objects.create(assessment=self.assessment, item_key=kra_ii_keys[4], compliance="na")

        data = self._detail()
        scores = data["scores"]
        kra_i = next(k for k in scores["kras"] if k["key"] == "I")
        kra_ii = next(k for k in scores["kras"] if k["key"] == "II")
        kra_iii = next(k for k in scores["kras"] if k["key"] == "III")

        self.assertEqual(kra_i["total"], 11)
        self.assertEqual(kra_i["yes"], 8)
        self.assertEqual(kra_i["not"], 2)
        self.assertEqual(kra_i["na"], 1)
        self.assertEqual(kra_i["unanswered"], 0)
        self.assertEqual(kra_i["actual_score"], 9)  # 8 yes + 1 na
        self.assertAlmostEqual(kra_i["pct"], round(9 / 11 * 100, 1))

        self.assertEqual(kra_ii["total"], 51)
        self.assertEqual(kra_ii["yes"], 3)
        self.assertEqual(kra_ii["not"], 1)
        self.assertEqual(kra_ii["na"], 1)
        self.assertEqual(kra_ii["unanswered"], 46)
        self.assertEqual(kra_ii["actual_score"], 4)  # 3 yes + 1 na
        self.assertAlmostEqual(kra_ii["pct"], round(4 / 51 * 100, 1))

        self.assertEqual(kra_iii["total"], 21)
        self.assertEqual(kra_iii["unanswered"], 21)
        self.assertEqual(kra_iii["actual_score"], 0)

        overall = scores["overall"]
        self.assertEqual(overall["total"], 83)
        self.assertEqual(overall["yes"], 11)
        self.assertEqual(overall["not"], 3)
        self.assertEqual(overall["na"], 2)
        self.assertEqual(overall["unanswered"], 67)
        self.assertEqual(overall["actual_score"], 13)  # 11 yes + 2 na
        self.assertAlmostEqual(overall["pct"], round(13 / 83 * 100, 1))

        # List view exposes the same overall figures as a "summary".
        list_resp = self.client.get("/api/samd/assessments/").data
        row = next(r for r in list_resp if r["id"] == self.assessment.id)
        self.assertEqual(row["summary"]["actual_score"], 13)
        self.assertEqual(row["summary"]["band"], overall["band"])

    def _set_yes_count(self, count):
        for key in ALL_KEYS[:count]:
            SamdResponse.objects.create(assessment=self.assessment, item_key=key, compliance="yes")

    def test_band_full_certification(self):
        self._set_yes_count(70)  # 70/83 = 84.3% >= 75
        overall = self._detail()["scores"]["overall"]
        self.assertGreaterEqual(overall["pct"], 75)
        self.assertEqual(overall["band"], "Full Certification")

    def test_band_conditional_approval(self):
        self._set_yes_count(55)  # 55/83 = 66.3%
        overall = self._detail()["scores"]["overall"]
        self.assertTrue(60 <= overall["pct"] <= 74)
        self.assertEqual(overall["band"], "Conditional Approval")

    def test_band_non_certification(self):
        self._set_yes_count(30)  # 30/83 = 36.1%
        overall = self._detail()["scores"]["overall"]
        self.assertLessEqual(overall["pct"], 59)
        self.assertEqual(overall["band"], "Non-Certification")


class CompleteTest(SamdTestBase):
    def setUp(self):
        super().setUp()
        self._auth("a@racco1.gov.ph")
        self.assessment = SamdAssessment.objects.create(label="R1", created_by=self.admin)

    def test_complete_sets_completed_at_and_locks(self):
        self.assertIsNone(self.assessment.completed_at)
        resp = self.client.post(f"/api/samd/assessments/{self.assessment.id}/complete/")
        self.assertEqual(resp.status_code, 200)
        self.assessment.refresh_from_db()
        self.assertEqual(self.assessment.status, SamdAssessment.COMPLETED)
        self.assertIsNotNone(self.assessment.completed_at)

        # Locked: no reopening, no further responses.
        again = self.client.post(f"/api/samd/assessments/{self.assessment.id}/complete/")
        self.assertEqual(again.status_code, 400)
        respond = self.client.post(
            f"/api/samd/assessments/{self.assessment.id}/respond/",
            {"item_key": "I.1", "compliance": "yes"}, format="json")
        self.assertEqual(respond.status_code, 400)
