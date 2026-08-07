from django.core.management import call_command
from rest_framework.test import APITestCase
from accounts.models import Role
from children.tests.test_child_collab import make_user
from clinical.models import InstrumentCatalog


class InstrumentSharingTests(APITestCase):
    def setUp(self):
        self.admin = make_user("ia@t.ph", Role.ADMINISTRATOR)
        self.psych = make_user("ip@t.ph", Role.PSYCHOLOGIST)
        self.shared = InstrumentCatalog.objects.create(
            title="Raven's Progressive Matrices", owner=None, audience="both")
        self.own = InstrumentCatalog.objects.create(
            title="My Checklist", owner=self.psych, audience="child")

    def test_psychologist_sees_shared_plus_own(self):
        self.client.force_authenticate(self.psych)
        titles = [i["title"] for i in self.client.get("/api/instruments/").data]
        self.assertIn("Raven's Progressive Matrices", titles)
        self.assertIn("My Checklist", titles)

    def test_psychologist_cannot_edit_shared(self):
        self.client.force_authenticate(self.psych)
        r = self.client.patch(f"/api/instruments/{self.shared.id}/", {"title": "X"}, format="json")
        self.assertIn(r.status_code, (403, 404))

    def test_admin_create_without_owner_is_shared(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post("/api/instruments/", {"title": "Shared One"}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertIsNone(InstrumentCatalog.objects.get(title="Shared One").owner)

    def test_psychologist_cannot_delete_shared(self):
        self.client.force_authenticate(self.psych)
        r = self.client.delete(f"/api/instruments/{self.shared.id}/")
        self.assertIn(r.status_code, (403, 404))
        self.assertTrue(InstrumentCatalog.objects.filter(id=self.shared.id).exists())

    def test_psychologist_cannot_reassign_owner_via_patch(self):
        self.client.force_authenticate(self.psych)
        self.client.patch(f"/api/instruments/{self.own.id}/", {"owner": None}, format="json")
        self.own.refresh_from_db()
        self.assertEqual(self.own.owner_id, self.psych.id)

    def test_seed_command_idempotent(self):
        call_command("seed_instrument_titles")
        first = InstrumentCatalog.objects.filter(owner__isnull=True).count()
        call_command("seed_instrument_titles")
        self.assertEqual(InstrumentCatalog.objects.filter(owner__isnull=True).count(), first)
        self.assertTrue(InstrumentCatalog.objects.filter(
            title="Children's Apperception Test", audience="child").exists())
        self.assertTrue(InstrumentCatalog.objects.filter(
            title="Marital Satisfaction Inventory", audience="adoptive_parent").exists())
