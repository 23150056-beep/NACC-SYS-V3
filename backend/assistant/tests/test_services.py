from unittest.mock import patch

from django.test import TestCase

from assistant import services
from assistant.models import AssistantJob, AssistantSetting


class NormalizeOutputTest(TestCase):
    def test_replaces_unicode_punctuation_with_ascii(self):
        raw = "“The child’s mother” – arrived late—again. Noted."
        self.assertEqual(
            services._normalize_output(raw),
            '"The child\'s mother" - arrived late-again. Noted.')

    def test_leaves_plain_ascii_untouched(self):
        self.assertEqual(services._normalize_output("Plain note."), "Plain note.")


class GetClientTest(TestCase):
    def test_returns_null_client_when_disabled(self):
        AssistantSetting.load()  # enabled defaults to False
        self.assertIsInstance(services.get_ai_client(), services.NullClient)

    def test_returns_ollama_client_when_enabled(self):
        cfg = AssistantSetting.load()
        cfg.enabled = True
        cfg.save()
        client = services.get_ai_client()
        self.assertIsInstance(client, services.OllamaClient)
        self.assertEqual(client.model, "qwen2.5:3b-instruct")

    def test_null_client_raises(self):
        with self.assertRaises(services.AIUnavailable):
            services.NullClient().generate("anything")


class GateTest(TestCase):
    def test_raises_when_master_switch_off(self):
        AssistantSetting.load()
        with self.assertRaises(services.AIUnavailable):
            services.gate("feature_remark_polish")

    def test_raises_when_feature_flag_off(self):
        cfg = AssistantSetting.load()
        cfg.enabled = True
        cfg.feature_remark_polish = False
        cfg.save()
        with self.assertRaises(services.AIUnavailable):
            services.gate("feature_remark_polish")

    def test_returns_config_when_enabled(self):
        cfg = AssistantSetting.load()
        cfg.enabled = True
        cfg.save()
        self.assertEqual(services.gate("feature_remark_polish").pk, 1)


class RunJobTest(TestCase):
    def setUp(self):
        cfg = AssistantSetting.load()
        cfg.enabled = True
        cfg.save()

    def test_writes_audit_row_and_normalizes_on_success(self):
        with patch.object(services.OllamaClient, "generate", return_value="A ‘draft’."):
            text, job = services.run_job(
                "remark_polish", "prompt", input_ref="child:1")
        self.assertEqual(text, "A 'draft'.")
        self.assertTrue(job.ok)
        self.assertEqual(job.output_text, "A 'draft'.")
        self.assertEqual(job.input_ref, "child:1")
        self.assertEqual(job.model_used, "qwen2.5:3b-instruct")
        self.assertIsNotNone(job.latency_ms)

    def test_writes_audit_row_on_failure_and_reraises(self):
        boom = services.AIUnavailable("runtime unreachable")
        with patch.object(services.OllamaClient, "generate", side_effect=boom):
            with self.assertRaises(services.AIUnavailable):
                services.run_job("remark_polish", "prompt", input_ref="child:1")
        job = AssistantJob.objects.get()
        self.assertFalse(job.ok)
        self.assertIn("unreachable", job.error)
        self.assertEqual(job.output_text, "")

    def test_unauthenticated_user_is_stored_as_null(self):
        with patch.object(services.OllamaClient, "generate", return_value="ok"):
            _, job = services.run_job("remark_polish", "p", user=None)
        self.assertIsNone(job.created_by)
