from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from assistant import services
from assistant.models import AssistantSetting
from assistant.services import OllamaClient, OpenAICompatibleClient


class AiCheckCommandTest(TestCase):
    def test_reports_switched_off_without_calling_the_runtime(self):
        cfg = AssistantSetting.load()
        cfg.enabled = False
        cfg.save()
        out = StringIO()
        with self.assertRaises(SystemExit) as ctx:
            call_command("ai_check", stdout=out)
        self.assertEqual(ctx.exception.code, 1)
        self.assertIn("switched off", out.getvalue())

    def test_reports_ok_and_latency_when_reachable(self):
        cfg = AssistantSetting.load()
        cfg.enabled = True
        cfg.save()
        out = StringIO()
        with patch.object(services.OllamaClient, "generate", return_value="OK"):
            call_command("ai_check", stdout=out)
        text = out.getvalue()
        self.assertIn("reachable", text)
        self.assertIn("qwen2.5:3b-instruct", text)

    def test_reports_unreachable_runtime_as_failure(self):
        cfg = AssistantSetting.load()
        cfg.enabled = True
        cfg.save()
        out = StringIO()
        err = services.AIUnavailable("Local AI runtime unreachable: refused")
        with patch.object(services.OllamaClient, "generate", side_effect=err):
            with self.assertRaises(SystemExit) as ctx:
                call_command("ai_check", stdout=out)
        self.assertEqual(ctx.exception.code, 1)
        self.assertIn("unreachable", out.getvalue())


class ReportsTheClientActuallyUsedTest(TestCase):
    """It printed the settings row, not the client. With a hosted model
    configured that meant reporting "qwen2.5:3b-instruct / localhost:11434"
    while timing a Cloudflare call — the wrong answer from the one command
    whose job is saying what the assistant is talking to."""

    def setUp(self):
        cfg = AssistantSetting.load()
        cfg.enabled = True
        cfg.ollama_url = "http://localhost:11434"
        cfg.model_name = "qwen2.5:3b-instruct"
        cfg.save()

    def _run(self, client):
        out = StringIO()
        with patch("assistant.management.commands.ai_check.get_ai_client",
                   return_value=client):
            call_command("ai_check", stdout=out)
        return out.getvalue()

    def test_a_hosted_client_is_named_as_hosted(self):
        hosted = OpenAICompatibleClient(
            "https://api.cloudflare.com/client/v4/accounts/x/ai/v1",
            "@cf/meta/llama-4-scout-17b-16e-instruct", "token")
        with patch.object(OpenAICompatibleClient, "generate", return_value="OK"):
            output = self._run(hosted)
        self.assertIn("HOSTED", output)
        self.assertIn("llama-4-scout", output)
        self.assertIn("api.cloudflare.com", output)
        # The settings row must not be what gets reported.
        self.assertNotIn("qwen2.5:3b-instruct", output)
        self.assertNotIn("localhost:11434", output)

    def test_a_local_client_is_named_as_local(self):
        local = OllamaClient("http://localhost:11434", "qwen2.5:3b-instruct")
        with patch.object(OllamaClient, "generate", return_value="OK"):
            output = self._run(local)
        self.assertIn("local runtime", output)
        self.assertNotIn("HOSTED", output)
