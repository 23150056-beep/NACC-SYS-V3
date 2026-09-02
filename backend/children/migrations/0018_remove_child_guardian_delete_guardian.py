from django.db import migrations


def refuse_if_any_data(apps, schema_editor):
    """Stop the deploy rather than drop records.

    The two operations after this are irreversible: the guardian column goes,
    then the table. The decision to run them rests on a row count somebody read
    off a screen — and the demo branch and the production branch are one
    dropdown apart in the Neon console, so a zero read from the wrong branch
    looks exactly like a zero read from the right one.

    So the count is taken again here, at the only moment it can be taken
    against the database actually being migrated. If anything is there, this
    raises: the migration aborts, entrypoint.sh fails, the deploy stops, and
    the container already serving keeps serving. Nothing is lost and somebody
    reads this message.

    Verified empty on the production branch on 2 Sep 2026 (0 guardians, 0
    children linked), which is why this is expected to be a no-op everywhere.
    """
    Guardian = apps.get_model("children", "Guardian")
    Child = apps.get_model("children", "Child")

    guardians = Guardian.objects.count()
    linked = Child.objects.exclude(guardian=None).count()
    if guardians or linked:
        raise RuntimeError(
            f"Refusing to drop the Guardian table: it holds {guardians} row(s) "
            f"and {linked} child record(s) still point at it. The count this "
            f"migration was written against was zero, so it was taken against "
            f"a different database — most likely the demo branch rather than "
            f"production. Nothing has been changed. Read the rows first "
            f"(SELECT * FROM tbl_guardian), decide whether they matter, and "
            f"either migrate them onto assigned_psychologist or delete this "
            f"migration and keep the column."
        )


def noop(apps, schema_editor):
    """Nothing to undo — the check only ever reads."""


class Migration(migrations.Migration):

    dependencies = [
        ('children', '0017_child_psgc_barangay_child_psgc_municipality_and_more'),
    ]

    operations = [
        migrations.RunPython(refuse_if_any_data, noop),
        migrations.RemoveField(
            model_name='child',
            name='guardian',
        ),
        migrations.DeleteModel(
            name='Guardian',
        ),
    ]
