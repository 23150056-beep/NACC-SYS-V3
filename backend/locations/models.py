from django.db import models


class _Place(models.Model):
    """Common shape for the three PSGC levels.

    `psgc_code` is the identity, not the name. Municipalities are renamed and
    promoted to cities, barangays are split and merged — but the code assigned
    to a place outlives its label, which is why a recorded address stores the
    code and not just the text.
    """

    psgc_code = models.CharField(max_length=12, unique=True, db_index=True)
    name = models.CharField(max_length=120, db_index=True)

    class Meta:
        abstract = True
        ordering = ["name"]

    def __str__(self):
        return self.name


class Province(_Place):
    class Meta(_Place.Meta):
        abstract = False
        ordering = ["name"]
        db_table = "tbl_province"


class Municipality(_Place):
    """Cities and municipalities both. PSGC treats them as one level, and the
    intake form asks for "City/Municipality" as one field, so splitting them
    here would invent a distinction neither the standard nor the form makes."""

    province = models.ForeignKey(
        Province, on_delete=models.CASCADE, related_name="municipalities")

    class Meta(_Place.Meta):
        abstract = False
        ordering = ["name"]
        db_table = "tbl_municipality"


class Barangay(_Place):
    municipality = models.ForeignKey(
        Municipality, on_delete=models.CASCADE, related_name="barangays")

    class Meta(_Place.Meta):
        abstract = False
        ordering = ["name"]
        db_table = "tbl_barangay"
