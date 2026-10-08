from django.db import migrations


def seed_lock(apps, schema_editor):
    MutationLock = apps.get_model("core", "MutationLock")
    MutationLock.objects.using(schema_editor.connection.alias).get_or_create(key="domain")


class Migration(migrations.Migration):
    dependencies = [("core", "0001_initial")]
    operations = [migrations.RunPython(seed_lock, migrations.RunPython.noop)]
