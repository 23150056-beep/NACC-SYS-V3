from django.core.management import call_command
from io import StringIO

from rest_framework.test import APITestCase

from accounts.models import Role, User
from children.models import Child
from locations.models import Barangay, Municipality, Province


class SeedTest(APITestCase):
    def test_seed_loads_region_one(self):
        call_command("seed_psgc", stdout=StringIO())
        self.assertEqual(Province.objects.count(), 4)
        self.assertEqual(Municipality.objects.count(), 125)
        self.assertEqual(Barangay.objects.count(), 3265)

    def test_seeding_twice_does_not_duplicate(self):
        """Re-running against a newer PSGC release has to update in place —
        duplicating would orphan every child record pointing at a code."""
        call_command("seed_psgc", stdout=StringIO())
        call_command("seed_psgc", stdout=StringIO())
        self.assertEqual(Province.objects.count(), 4)
        self.assertEqual(Barangay.objects.count(), 3265)

    def test_la_union_has_all_twenty_lgus(self):
        call_command("seed_psgc", stdout=StringIO())
        la_union = Province.objects.get(name="La Union")
        self.assertEqual(la_union.municipalities.count(), 20)


class LocationApiTest(APITestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_psgc", stdout=StringIO())

    def setUp(self):
        role = Role.objects.create(role_name=Role.STAFF)
        User.objects.create_user(email="s@racco1.gov.ph", username="s",
                                 password="pass1234", role=role)
        token = self.client.post("/api/auth/login/", {
            "email": "s@racco1.gov.ph", "password": "pass1234"}).data["access"]
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + token)

    def test_provinces_listed(self):
        resp = self.client.get("/api/locations/provinces/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual({p["name"] for p in resp.data},
                         {"Ilocos Norte", "Ilocos Sur", "La Union", "Pangasinan"})

    def test_municipalities_filter_by_province(self):
        la_union = Province.objects.get(name="La Union")
        resp = self.client.get("/api/locations/municipalities/",
                               {"province": la_union.psgc_code})
        self.assertEqual(len(resp.data), 20)
        # PSGC's own name, not the informal one. The hand-kept list this
        # replaces said "San Fernando City"; the standard says this. Keeping
        # the official spelling is the point of using the standard at all.
        self.assertIn("City Of San Fernando (Capital)", [m["name"] for m in resp.data])

    def test_barangays_require_a_municipality(self):
        """3,265 rows is not a list anyone picks from, and not what the form
        asks for — an unfiltered request returns nothing rather than all."""
        resp = self.client.get("/api/locations/barangays/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 0)

    def test_barangays_of_a_municipality(self):
        agoo = Municipality.objects.get(name="Agoo")
        resp = self.client.get("/api/locations/barangays/",
                               {"municipality": agoo.psgc_code})
        self.assertGreater(len(resp.data), 0)
        self.assertTrue(all("psgc_code" in b and "name" in b for b in resp.data))

    def test_anonymous_is_refused(self):
        self.client.credentials()
        self.assertEqual(self.client.get("/api/locations/provinces/").status_code, 401)

    def test_the_api_is_read_only(self):
        resp = self.client.post("/api/locations/provinces/", {"name": "Nowhere"})
        self.assertIn(resp.status_code, (403, 405))


class BackfillTest(APITestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_psgc", stdout=StringIO())

    def test_matching_text_gets_codes(self):
        child = Child.objects.create(fullname="Ana", province="La Union",
                                     municipality="Agoo", barangay="Ambitacay")
        call_command("backfill_psgc", "--apply", stdout=StringIO())
        child.refresh_from_db()
        self.assertTrue(child.psgc_province)
        self.assertTrue(child.psgc_municipality)
        self.assertTrue(child.psgc_barangay)

    def test_case_and_spacing_do_not_block_a_match(self):
        child = Child.objects.create(fullname="Ben", province="  la union ",
                                     municipality="AGOO")
        call_command("backfill_psgc", "--apply", stdout=StringIO())
        child.refresh_from_db()
        self.assertTrue(child.psgc_municipality)

    def test_unmatched_text_is_kept_not_wiped(self):
        child = Child.objects.create(fullname="Cid", province="Atlantis",
                                     municipality="Nowhere")
        call_command("backfill_psgc", "--apply", stdout=StringIO())
        child.refresh_from_db()
        self.assertEqual(child.province, "Atlantis")
        self.assertEqual(child.municipality, "Nowhere")
        self.assertEqual(child.psgc_province, "")

    def test_dry_run_writes_nothing(self):
        child = Child.objects.create(fullname="Dee", province="La Union", municipality="Agoo")
        call_command("backfill_psgc", stdout=StringIO())
        child.refresh_from_db()
        self.assertEqual(child.psgc_province, "")

    def test_report_names_the_records_needing_a_human(self):
        Child.objects.create(fullname="Eve", province="Atlantis")
        out = StringIO()
        call_command("backfill_psgc", stdout=out)
        self.assertIn("Eve", out.getvalue())
