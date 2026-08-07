from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ai", "0004_rename_case_study_job_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="aisetting",
            name="provider",
            field=models.CharField(
                choices=[("ollama", "On-premises Ollama"), ("hosted", "Hosted API (cloud)")],
                default="ollama",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="aisetting",
            name="hosted_model",
            field=models.CharField(default="claude-opus-5", max_length=100),
        ),
    ]
