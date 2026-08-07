from django.db import migrations


def copy_titles(apps, schema_editor):
    """Historical one-off: carried v1 questionnaire titles into the V2 catalog
    at the assessments->clinical cutover. The legacy assessments app has since
    been deleted (v1 data is archived to CSV, not migrated), so on fresh
    installs there is nothing to copy and this is a no-op."""
    try:
        Questionnaire = apps.get_model("assessments", "Questionnaire")
    except LookupError:
        return
    InstrumentCatalog = apps.get_model("clinical", "InstrumentCatalog")
    for qn in Questionnaire.objects.all():
        InstrumentCatalog.objects.get_or_create(
            title=qn.title,
            owner_id=qn.owner_id,
            defaults={
                "age_range": qn.age_group or "",
                "notes": qn.description or "",
                "category": "behavioral",
                "active": qn.status == "active",
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ("clinical", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(copy_titles, migrations.RunPython.noop),
    ]
