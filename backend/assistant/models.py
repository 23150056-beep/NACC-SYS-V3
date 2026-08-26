from django.conf import settings
from django.db import models


class AssistantSetting(models.Model):
    """Singleton (pk=1): the assistant switch plus local runtime config.

    The system stays fully functional with the assistant off — every feature
    degrades to a 503 the screens absorb — but it is on by default, so it
    works as soon as the local runtime is running.
    """

    # On by default: once the runtime is installed the assistant is simply
    # available, rather than waiting for someone to discover a toggle. The
    # switch remains so an administrator can stop a misbehaving feature
    # without a code deploy — which is the only remedy otherwise.
    enabled = models.BooleanField(default=True)

    # On-premises runtime only. There is no hosted provider: sending clinical
    # free text to an outside processor is what removed the V2 layer.
    ollama_url = models.URLField(default="http://localhost:11434")
    model_name = models.CharField(max_length=100, default="qwen2.5:3b-instruct")

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tbl_assistant_setting"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class AssistantJob(models.Model):
    """Audit row for every model call: what ran, on what, what came back, how
    long it took, and what the human did with it."""

    TYPE_CHOICES = [
        ("brief", "Pre-Session Brief"),
        ("doc_intelligence", "Document Summary"),
        ("remark_polish", "Remark Polishing"),
        ("census_narrative", "Census Narrative"),
    ]

    PENDING, ACCEPTED, EDITED, DISCARDED = "pending", "accepted", "edited", "discarded"
    OUTCOME_CHOICES = [
        (PENDING, "Pending"),
        (ACCEPTED, "Accepted as-is"),
        (EDITED, "Edited then used"),
        (DISCARDED, "Discarded"),
    ]

    job_type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    input_ref = models.CharField(max_length=150, blank=True)  # "child:12", "report:3"
    output_text = models.TextField(blank=True)
    model_used = models.CharField(max_length=100, blank=True)
    latency_ms = models.PositiveIntegerField(null=True, blank=True)
    ok = models.BooleanField(default=True)
    error = models.CharField(max_length=255, blank=True)
    outcome = models.CharField(max_length=10, choices=OUTCOME_CHOICES, default=PENDING)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="assistant_jobs")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "tbl_assistant_job"
        ordering = ["-created_at"]
