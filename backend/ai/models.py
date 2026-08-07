from django.conf import settings
from django.db import models


class AISetting(models.Model):
    """Singleton (pk=1): AI feature flags + runtime provider config.
    The system is fully functional with everything switched off."""

    OLLAMA, HOSTED = "ollama", "hosted"
    PROVIDER_CHOICES = [
        (OLLAMA, "On-premises Ollama"),
        (HOSTED, "Hosted API (cloud)"),
    ]

    enabled = models.BooleanField(default=False)  # master switch
    feature_brief = models.BooleanField(default=True)          # A1 pre-session brief
    feature_doc_intelligence = models.BooleanField(default=True)  # A2 report summarization
    feature_remark_polish = models.BooleanField(default=True)   # A3 remark polishing
    feature_census_narrative = models.BooleanField(default=True)  # A5 monthly narrative

    # Which runtime serves the drafts. Defaults to ollama so an existing
    # on-premises install keeps behaving exactly as it did in V2 after upgrade.
    provider = models.CharField(max_length=10, choices=PROVIDER_CHOICES, default=OLLAMA)

    # Ollama (on-premises) settings.
    ollama_url = models.URLField(default="http://localhost:11434")
    model_name = models.CharField(max_length=100, default="qwen2.5:7b-instruct")

    # Hosted provider settings. The API key is NOT here on purpose — it lives
    # in the server environment (AI_HOSTED_API_KEY) so it can never be read
    # back through the API, dumped in a DB backup, or edited by a signed-in
    # administrator.
    hosted_model = models.CharField(max_length=100, default="claude-opus-5")

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tbl_ai_setting"

    @property
    def active_model(self):
        """The model name that will actually serve the next job."""
        return self.hosted_model if self.provider == self.HOSTED else self.model_name

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
