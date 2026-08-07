# Adds assigned_psychologist, structured location pickers, surrendered_by,
# and choices on case_type for the Child model (adviser revisions).
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("children", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="child",
            name="assigned_psychologist",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="assigned_children",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="child",
            name="province",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="child",
            name="municipality",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="child",
            name="barangay",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="child",
            name="surrendered_by",
            field=models.CharField(
                blank=True, max_length=50,
                choices=[
                    ("Social Worker", "Social Worker"),
                    ("Police", "Police"),
                    ("Relatives", "Relatives"),
                ],
            ),
        ),
        migrations.AlterField(
            model_name="child",
            name="case_type",
            field=models.CharField(
                blank=True, max_length=150,
                choices=[
                    ("Foster Care", "Foster Care"),
                    ("Kinship Care", "Kinship Care"),
                    ("Residential Care", "Residential Care"),
                    ("Family Tracing & Reunification", "Family Tracing & Reunification"),
                    ("Independent Living", "Independent Living"),
                ],
            ),
        ),
    ]
