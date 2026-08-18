from django.db import migrations


class Migration(migrations.Migration):
    """Drop the tables the removed `ai` app left behind.

    The AI layer was taken out entirely (product decision 2026-08-18): the
    on-premises runtime could not run on cloud instances, and the hosted one
    would have meant sending clinical free text to a processor outside the
    agency's data-processing agreements. Deleting the app stops Django from
    managing `tbl_ai_setting` and `tbl_ai_job`, but does not drop them — the
    rows would sit in the database holding prompts and drafts about real
    children with nothing left to read or delete them.

    This migration lives in `activity` rather than `ai` because `ai` no longer
    exists to hold a migration. Its own rows in `django_migrations` are left
    alone: they are inert, and rewriting another app's migration history to
    tidy them up would risk more than it cleans.
    """

    dependencies = [("activity", "0002_activitylog_recipient")]

    operations = [
        migrations.RunSQL(
            sql=[
                "DROP TABLE IF EXISTS tbl_ai_job;",
                "DROP TABLE IF EXISTS tbl_ai_setting;",
            ],
            # Irreversible on purpose: recreating empty tables would imply the
            # data could come back, and it cannot.
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
