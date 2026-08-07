"""Hosted AI provider (cloud deployments) and the provider-aware settings guard."""

from types import SimpleNamespace
from unittest import mock

from django.test import TestCase, override_settings
from rest_framework.test import APITestCase

from accounts.models import Role
from ai.models import AISetting
from ai.services import AIUnavailable, HostedClient, NullClient, OllamaClient, get_ai_client
from children.tests.test_child_collab import make_user


def _hosted_setting(**kwargs):
    setting = AISetting.load()
    setting.enabled = True
    setting.provider = AISetting.HOSTED
    for key, value in kwargs.items():
        setattr(setting, key, value)
    setting.save()
    return setting


class ClientSelectionTests(TestCase):
    def test_hosted_provider_returns_hosted_client(self):
        _hosted_setting()
        self.assertIsInstance(get_ai_client(), HostedClient)

    def test_ollama_provider_still_returns_ollama_client(self):
        setting = AISetting.load()
        setting.enabled = True
        setting.provider = AISetting.OLLAMA
        setting.save()
        self.assertIsInstance(get_ai_client(), OllamaClient)

    def test_master_switch_off_beats_provider_choice(self):
        # The kill switch has to win regardless of which runtime is configured.
        setting = _hosted_setting()
        setting.enabled = False
        setting.save()
        self.assertIsInstance(get_ai_client(), NullClient)

    def test_active_model_follows_provider(self):
        setting = _hosted_setting(hosted_model="claude-opus-5",
                                  model_name="qwen2.5:7b-instruct")
        self.assertEqual(setting.active_model, "claude-opus-5")
        setting.provider = AISetting.OLLAMA
        self.assertEqual(setting.active_model, "qwen2.5:7b-instruct")


class HostedClientTests(TestCase):
    @override_settings(AI_HOSTED_API_KEY="")
    def test_missing_api_key_is_unavailable_not_a_crash(self):
        # An unconfigured credential must degrade like an unreachable Ollama:
        # the feature reports 503 and the rest of the system keeps working.
        _hosted_setting()
        with self.assertRaises(AIUnavailable) as ctx:
            get_ai_client().generate("draft a summary")
        self.assertIn("AI_HOSTED_API_KEY", str(ctx.exception))

    @override_settings(AI_HOSTED_API_KEY="test-key")
    def test_text_blocks_are_joined_and_stripped(self):
        client = HostedClient(model="claude-opus-5", api_key="test-key")
        response = SimpleNamespace(
            stop_reason="end_turn",
            stop_details=None,
            content=[
                SimpleNamespace(type="text", text="  Clinical summary. "),
                SimpleNamespace(type="text", text="Second paragraph.  "),
            ],
        )
        with mock.patch("anthropic.Anthropic") as sdk:
            sdk.return_value.beta.messages.create.return_value = response
            out = client.generate("summarize", system="You are a clinician.")
        self.assertEqual(out, "Clinical summary. Second paragraph.")

    @override_settings(AI_HOSTED_API_KEY="test-key")
    def test_system_prompt_is_forwarded(self):
        client = HostedClient(model="claude-opus-5", api_key="test-key")
        response = SimpleNamespace(stop_reason="end_turn", stop_details=None,
                                   content=[SimpleNamespace(type="text", text="ok")])
        with mock.patch("anthropic.Anthropic") as sdk:
            sdk.return_value.beta.messages.create.return_value = response
            client.generate("the prompt", system="the system prompt")
            kwargs = sdk.return_value.beta.messages.create.call_args.kwargs
        self.assertEqual(kwargs["system"], "the system prompt")
        self.assertEqual(kwargs["messages"], [{"role": "user", "content": "the prompt"}])
        self.assertEqual(kwargs["model"], "claude-opus-5")

    @override_settings(AI_HOSTED_API_KEY="test-key")
    def test_refusal_is_reported_as_unavailable(self):
        # A declined request comes back as a normal HTTP 200 with an empty
        # content list — reading content[0] blindly would raise IndexError and
        # surface to the psychologist as a 500 instead of "write it manually".
        client = HostedClient(model="claude-opus-5", api_key="test-key")
        response = SimpleNamespace(
            stop_reason="refusal",
            stop_details=SimpleNamespace(category="bio", explanation="declined"),
            content=[],
        )
        with mock.patch("anthropic.Anthropic") as sdk:
            sdk.return_value.beta.messages.create.return_value = response
            with self.assertRaises(AIUnavailable) as ctx:
                client.generate("summarize")
        self.assertIn("declined", str(ctx.exception).lower())

    @override_settings(AI_HOSTED_API_KEY="test-key")
    def test_connection_error_is_reported_as_unavailable(self):
        import anthropic

        client = HostedClient(model="claude-opus-5", api_key="test-key")
        with mock.patch("anthropic.Anthropic") as sdk:
            sdk.return_value.beta.messages.create.side_effect = (
                anthropic.APIConnectionError(request=mock.Mock())
            )
            with self.assertRaises(AIUnavailable):
                client.generate("summarize")


class ProviderAwareSettingsGuardTests(APITestCase):
    def setUp(self):
        self.admin = make_user("hosted@t.ph", Role.ADMINISTRATOR)
        self.client.force_authenticate(self.admin)

    def test_switching_to_hosted_provider_is_accepted(self):
        r = self.client.patch("/api/ai/settings/", {"provider": "hosted"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(AISetting.load().provider, AISetting.HOSTED)

    def test_remote_ollama_url_is_ignored_while_hosted_is_selected(self):
        # The frontend resends the whole object on save, so a stale remote
        # ollama_url must not block a cloud deployment from saving settings.
        r = self.client.patch("/api/ai/settings/", {
            "provider": "hosted",
            "ollama_url": "http://203.0.113.5:11434",
            "hosted_model": "claude-opus-5",
        }, format="json")
        self.assertEqual(r.status_code, 200, r.data)

    def test_loopback_guard_still_applies_when_ollama_is_selected(self):
        r = self.client.patch("/api/ai/settings/", {
            "provider": "ollama", "ollama_url": "http://203.0.113.5:11434",
        }, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("ollama_url", r.data)

    def test_switching_back_to_ollama_revalidates_the_url(self):
        setting = AISetting.load()
        setting.provider = AISetting.HOSTED
        setting.ollama_url = "http://203.0.113.9:11434"
        setting.save()
        r = self.client.patch("/api/ai/settings/", {
            "provider": "ollama", "ollama_url": "http://203.0.113.5:11434",
        }, format="json")
        self.assertEqual(r.status_code, 400)

    @override_settings(AI_HOSTED_API_KEY="")
    def test_hosted_key_configured_is_false_without_a_server_key(self):
        r = self.client.get("/api/ai/settings/")
        self.assertFalse(r.data["hosted_key_configured"])

    @override_settings(AI_HOSTED_API_KEY="test-key")
    def test_hosted_key_configured_is_true_with_a_server_key(self):
        r = self.client.get("/api/ai/settings/")
        self.assertTrue(r.data["hosted_key_configured"])

    @override_settings(AI_HOSTED_API_KEY="super-secret-key")
    def test_api_key_is_never_exposed_through_the_api(self):
        r = self.client.get("/api/ai/settings/")
        self.assertNotIn("super-secret-key", str(r.data))
