from django.conf import settings
from django.db import models


class AISetting(models.Model):
    """Singleton (pk=1): AI feature flags + local Ollama endpoint config.
    The system is fully functional with everything switched off."""
    enabled = models.BooleanField(default=False)  # master switch
    feature_brief = models.BooleanField(default=True)          # A1 pre-session brief
    feature_doc_intelligence = models.BooleanField(default=True)  # A2 report summarization
    feature_remark_polish = models.BooleanField(default=True)   # A3 remark polishing
    feature_census_narrative = models.BooleanField(default=True)  # A5 monthly narrative
    ollama_url = models.URLField(default="http://localhost:11434")
    model_name = models.CharField(max_length=100, default="qwen2.5:7b-instruct")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tbl_ai_setting"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class AIJob(models.Model):
    """Audit row for every AI call: what ran, on what, what came back,
    and whether the human accepted it."""
    TYPE_CHOICES = [
        ("brief", "Pre-Session Brief"),
        ("doc_intelligence", "Report Document Intelligence"),
        ("remark_polish", "Remark Polishing"),
        ("census_narrative", "Census Narrative"),
        ("case_referral", "Case Referral Summary"),
    ]

    PENDING, ACCEPTED, EDITED, DISCARDED = "pending", "accepted", "edited", "discarded"
    OUTCOME_CHOICES = [(PENDING, "Pending"), (ACCEPTED, "Accepted as-is"),
                       (EDITED, "Edited then used"), (DISCARDED, "Discarded")]

    job_type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    input_ref = models.CharField(max_length=150, blank=True)  # e.g. "child:12", "report:3"
    output_text = models.TextField(blank=True)
    model_used = models.CharField(max_length=100, blank=True)
    latency_ms = models.PositiveIntegerField(null=True, blank=True)
    ok = models.BooleanField(default=True)
    error = models.CharField(max_length=255, blank=True)
    accepted = models.BooleanField(null=True, blank=True)  # human-in-the-loop verdict
    outcome = models.CharField(max_length=10, choices=OUTCOME_CHOICES, default=PENDING)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="ai_jobs")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "tbl_ai_job"
        ordering = ["-created_at"]
