import re
from uuid import UUID

from django.db import migrations


def backfill(apps, schema_editor):
    pattern = re.compile(r'\[(task|remark):([0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12})\]')
    Reference = apps.get_model('content', 'Reference')
    alias = schema_editor.connection.alias
    for app, model, field, source in [('tasks', 'Task', 'description', 'source_task_id'),
                                      ('remarks', 'Remark', 'body', 'source_remark_id')]:
        for pk, text in apps.get_model(app, model).objects.using(alias).values_list('pk', field).iterator():
            targets = {(kind, UUID(target)) for kind, target in pattern.findall(text)}
            Reference.objects.using(alias).bulk_create([
                Reference(**{source: pk}, target_kind=kind, target_id=target) for kind, target in targets])


class Migration(migrations.Migration):
    dependencies = [('content', '0001_initial')]
    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
