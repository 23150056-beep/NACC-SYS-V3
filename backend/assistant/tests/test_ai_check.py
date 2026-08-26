from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from assistant import services
from assistant.models import AssistantSetting


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
