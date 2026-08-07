from django.db import migrations


def archived_to_inactive(apps, schema_editor):
    Child = apps.get_model("children", "Child")
    Child.objects.filter(status="archived").update(status="inactive")


def inactive_to_archived(apps, schema_editor):
    Child = apps.get_model("children", "Child")
    Child.objects.filter(status="inactive").update(status="archived")


class Migration(migrations.Migration):

    dependencies = [
        ("children", "0006_child_current_placement_child_education_level_and_more"),
    ]

    operations = [
        migrations.RunPython(archived_to_inactive, inactive_to_archived),
    ]
