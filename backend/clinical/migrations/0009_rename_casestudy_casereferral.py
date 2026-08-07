# Hand-written rename: CaseStudy -> CaseReferral, keeping all existing rows.

import clinical.models
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('children', '0010_backfill_case_status'),
        ('clinical', '0008_instrumentcatalog_audience'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RenameModel(old_name='CaseStudy', new_name='CaseReferral'),
        migrations.AlterModelTable(name='casereferral', table='tbl_case_referral'),
        migrations.AlterField(
            model_name='casereferral',
            name='file',
            field=models.FileField(upload_to=clinical.models.case_referral_upload_path),
        ),
        migrations.AlterField(
            model_name='casereferral',
            name='child',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='case_referrals', to='children.child'),
        ),
        migrations.AlterField(
            model_name='casereferral',
            name='uploaded_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='case_referrals_uploaded', to=settings.AUTH_USER_MODEL),
        ),
    ]
