from django.test import override_settings
from rest_framework.test import APITestCase

from accounts.models import Role
from children.tests.test_child_collab import make_user


class OllamaUrlGuardTests(APITestCase):
    def setUp(self):
        self.admin = make_user("ou@t.ph", Role.ADMINISTRATOR)
        self.client.force_authenticate(self.admin)

    def test_remote_url_rejected(self):
        r = self.client.patch("/api/ai/settings/", {"ollama_url": "http://203.0.113.5:11434"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_localhost_accepted(self):
        r = self.client.patch("/api/ai/settings/", {"ollama_url": "http://localhost:11434"}, format="json")
        self.assertEqual(r.status_code, 200)

    def test_loopback_ip_accepted(self):
        r = self.client.patch("/api/ai/settings/", {"ollama_url": "http://127.0.0.1:11434"}, format="json")
        self.assertEqual(r.status_code, 200)

    def test_ipv6_loopback_accepted(self):
        r = self.client.patch("/api/ai/settings/", {"ollama_url": "http://[::1]:11434"}, format="json")
        self.assertEqual(r.status_code, 200)

    @override_settings(ALLOW_REMOTE_OLLAMA=True)
    def test_remote_url_allowed_when_escape_hatch_set(self):
        r = self.client.patch("/api/ai/settings/", {"ollama_url": "http://203.0.113.5:11434"}, format="json")
        self.assertEqual(r.status_code, 200)

    def test_unchanged_remote_url_does_not_block_unrelated_save(self):
        # Simulate a pre-existing remote config (legitimate at the time it was
        # set, before this guard existed) - an unrelated field change must not
        # be blocked by re-validating a URL nobody is touching. The frontend
        # always resends the full object on save, so ollama_url MUST be in
        # the payload here (unchanged) to actually exercise the skip-when-
        # unchanged branch - omitting it would let DRF's partial-update
        # field-skipping pass the test regardless of whether the fix exists.
        from ai.models import AISetting
        setting = AISetting.load()
        setting.ollama_url = "http://203.0.113.5:11434"
        setting.save()
        r = self.client.patch("/api/ai/settings/", {
            "ollama_url": "http://203.0.113.5:11434", "enabled": True,
        }, format="json")
        self.assertEqual(r.status_code, 200)

    def test_changing_away_from_a_stale_remote_url_still_requires_loopback(self):
        from ai.models import AISetting
        setting = AISetting.load()
        setting.ollama_url = "http://203.0.113.5:11434"
        setting.save()
        r = self.client.patch("/api/ai/settings/", {"ollama_url": "http://203.0.113.9:11434"}, format="json")
        self.assertEqual(r.status_code, 400)
