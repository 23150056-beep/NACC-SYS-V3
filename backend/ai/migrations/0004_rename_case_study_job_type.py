# Rename the "case_study" job type to "case_referral", including existing audit rows.

from django.db import migrations, models


def forwards(apps, schema_editor):
    AIJob = apps.get_model("ai", "AIJob")
    for job in AIJob.objects.filter(job_type="case_study"):
        job.job_type = "case_referral"
        job.input_ref = job.input_ref.replace("casestudy:", "casereferral:")
        job.save(update_fields=["job_type", "input_ref"])


def backwards(apps, schema_editor):
    AIJob = apps.get_model("ai", "AIJob")
    for job in AIJob.objects.filter(job_type="case_referral"):
        job.job_type = "case_study"
        job.input_ref = job.input_ref.replace("casereferral:", "casestudy:")
        job.save(update_fields=["job_type", "input_ref"])


class Migration(migrations.Migration):

    dependencies = [
        ('ai', '0003_aijob_outcome'),
    ]

    operations = [
        migrations.AlterField(
            model_name='aijob',
            name='job_type',
            field=models.CharField(choices=[('brief', 'Pre-Session Brief'), ('doc_intelligence', 'Report Document Intelligence'), ('remark_polish', 'Remark Polishing'), ('census_narrative', 'Census Narrative'), ('case_referral', 'Case Referral Summary')], max_length=30),
        ),
        migrations.RunPython(forwards, backwards),
    ]
