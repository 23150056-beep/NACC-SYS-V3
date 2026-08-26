import http.client
import json
import urllib.error
from unittest.mock import MagicMock, patch

from django.test import TestCase

from assistant import services
from assistant.models import AssistantJob, AssistantSetting


class NormalizeOutputTest(TestCase):
    def test_replaces_unicode_punctuation_with_ascii(self):
        raw = "“The child’s mother” – arrived late—again. Noted."
        self.assertEqual(
            services._normalize_output(raw),
            '"The child\'s mother" - arrived late-again. Noted.')

    def test_leaves_plain_ascii_untouched(self):
        self.assertEqual(services._normalize_output("Plain note."), "Plain note.")


class GetClientTest(TestCase):
    def test_returns_null_client_when_disabled(self):
        cfg = AssistantSetting.load()
        cfg.enabled = False
        cfg.save()
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
        cfg = AssistantSetting.load()
        cfg.enabled = False
        cfg.save()
        with self.assertRaises(services.AIUnavailable):
            services.gate()

    def test_returns_config_when_enabled(self):
        cfg = AssistantSetting.load()
        cfg.enabled = True
        cfg.save()
        self.assertEqual(services.gate().pk, 1)


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


class OllamaClientGenerateTest(TestCase):
    """Exercises the real generate() body against a mocked transport —
    urllib.request.urlopen, not OllamaClient.generate itself — so the payload
    shape and the exception mapping are both actually covered."""

    def _client(self):
        return services.OllamaClient("http://localhost:11434", "qwen2.5:3b-instruct")

    def _response(self, body_bytes):
        resp = MagicMock()
        resp.__enter__.return_value = resp
        resp.read.return_value = body_bytes
        return resp

    def test_payload_has_no_extra_keys_without_system(self):
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = self._response(
                json.dumps({"response": "ok"}).encode())
            self._client().generate("prompt text")
        req = mock_urlopen.call_args[0][0]
        payload = json.loads(req.data.decode())
        self.assertEqual(set(payload.keys()), {"model", "prompt", "stream"})
        self.assertIs(payload["stream"], False)

    def test_payload_adds_system_key_only_when_given(self):
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = self._response(
                json.dumps({"response": "ok"}).encode())
            self._client().generate("prompt text", system="Be terse.")
        req = mock_urlopen.call_args[0][0]
        payload = json.loads(req.data.decode())
        self.assertEqual(
            set(payload.keys()), {"model", "prompt", "stream", "system"})

    def test_url_error_maps_to_ai_unavailable(self):
        with patch("urllib.request.urlopen",
                    side_effect=urllib.error.URLError("connection refused")):
            with self.assertRaises(services.AIUnavailable):
                self._client().generate("prompt")

    def test_timeout_maps_to_ai_unavailable(self):
        with patch("urllib.request.urlopen", side_effect=TimeoutError("timed out")):
            with self.assertRaises(services.AIUnavailable):
                self._client().generate("prompt")

    def test_malformed_json_body_maps_to_ai_unavailable(self):
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = self._response(b"not json")
            with self.assertRaises(services.AIUnavailable):
                self._client().generate("prompt")

    def test_incomplete_read_maps_to_ai_unavailable(self):
        # Raised by resp.read() when the runtime process dies mid-response
        # (observed on this hardware under OOM). IncompleteRead subclasses
        # http.client.HTTPException, not OSError, so it needs its own entry
        # in the except tuple.
        with patch("urllib.request.urlopen",
                    side_effect=http.client.IncompleteRead(b"partial")):
            with self.assertRaises(services.AIUnavailable):
                self._client().generate("prompt")

    def test_undecodable_body_maps_to_ai_unavailable(self):
        # .decode() on a truncated multi-byte sequence raises
        # UnicodeDecodeError, a ValueError subclass not covered by OSError.
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = self._response(b"\xff\xfe\x00\x01")
            with self.assertRaises(services.AIUnavailable):
                self._client().generate("prompt")
