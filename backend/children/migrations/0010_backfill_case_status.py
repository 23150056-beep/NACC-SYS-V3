from django.db import migrations


def backfill(apps, schema_editor):
    Child = apps.get_model("children", "Child")
    Child.objects.filter(status="inactive").update(case_status="terminated")


class Migration(migrations.Migration):

    dependencies = [
        ("children", "0009_child_case_status"),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
