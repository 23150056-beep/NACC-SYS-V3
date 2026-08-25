from django.test import TestCase

from assistant.models import AssistantSetting, AssistantJob


class AssistantSettingTest(TestCase):
    def test_load_creates_singleton_with_safe_defaults(self):
        cfg = AssistantSetting.load()
        self.assertEqual(cfg.pk, 1)
        # Off by default: installing the app must change nothing.
        self.assertFalse(cfg.enabled)
        self.assertEqual(cfg.model_name, "qwen2.5:3b-instruct")
        self.assertEqual(cfg.ollama_url, "http://localhost:11434")

    def test_load_is_idempotent(self):
        AssistantSetting.load()
        AssistantSetting.load()
        self.assertEqual(AssistantSetting.objects.count(), 1)

    def test_save_always_pins_pk_to_one(self):
        cfg = AssistantSetting(pk=99, enabled=True)
        cfg.save()
        self.assertEqual(cfg.pk, 1)
        self.assertEqual(AssistantSetting.objects.count(), 1)


class AssistantJobTest(TestCase):
    def test_job_defaults_to_pending_outcome(self):
        job = AssistantJob.objects.create(job_type="remark_polish", input_ref="child:1")
        self.assertEqual(job.outcome, AssistantJob.PENDING)
        self.assertTrue(job.ok)
