from django.db import models


class SamdAssessment(models.Model):
    """One run of the NACC-SAMD-GF-000 self-assessment checklist (83 indicators
    across 3 KRAs). Completed rounds are locked (see SamdResponse and the
    `respond`/`complete` actions in samd/views.py)."""
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    STATUS_CHOICES = [(IN_PROGRESS, "In progress"), (COMPLETED, "Completed")]

    label = models.CharField(max_length=150)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=IN_PROGRESS)
    created_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="samd_assessments")
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "tbl_samd_assessment"
        ordering = ["-created_at"]

    def __str__(self):
        return self.label


class SamdResponse(models.Model):
    """A single checklist item's answer within one assessment round.

    `item_key` references samd.checklist.ITEM_INDEX (e.g. "II.5") rather than a
    FK, since the checklist itself is static data, not a DB table.
    """
    YES = "yes"
    NOT = "not"
    NA = "na"
    COMPLIANCE_CHOICES = [(YES, "Yes"), (NOT, "Not"), (NA, "N/A")]

    assessment = models.ForeignKey(
        SamdAssessment, on_delete=models.CASCADE, related_name="responses")
    item_key = models.CharField(max_length=10)
    # Blank is allowed at the DB level (not a real choice) so "remarks only, not
    # yet answered yet-or-cleared" rows can be stored; samd/views.py validates
    # the incoming value against yes/not/na/"" before saving.
    compliance = models.CharField(max_length=10, choices=COMPLIANCE_CHOICES, blank=True)
    remarks = models.TextField(blank=True)

    class Meta:
        db_table = "tbl_samd_response"
        constraints = [
            models.UniqueConstraint(fields=["assessment", "item_key"], name="unique_samd_response_per_item"),
        ]

    def __str__(self):
        return f"{self.assessment_id}:{self.item_key}={self.compliance}"
