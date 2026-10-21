from django.conf import settings
from django.db import migrations


def backfill(apps, schema_editor):
    User = apps.get_model(settings.AUTH_USER_MODEL)
    Timesheet = apps.get_model('timesheets', 'Timesheet')
    database = schema_editor.connection.alias
    for user_id in User.objects.using(database).values_list('pk', flat=True).iterator():
        Timesheet.objects.using(database).get_or_create(user_id=user_id)


class Migration(migrations.Migration):
    dependencies = [('timesheets', '0001_initial')]
    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
