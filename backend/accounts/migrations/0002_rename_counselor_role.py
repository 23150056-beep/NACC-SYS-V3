# Rename the existing "Counselor" role row to "Psychologist" on databases
# that were seeded before the rename.

from django.db import migrations


def counselor_to_psychologist(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    Role.objects.filter(role_name='Counselor').update(role_name='Psychologist')


def psychologist_to_counselor(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    Role.objects.filter(role_name='Psychologist').update(role_name='Counselor')


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(counselor_to_psychologist, psychologist_to_counselor),
    ]
