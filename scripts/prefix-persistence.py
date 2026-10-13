"""Executed only inside a guarded synthetic prefix-test backend."""
import hashlib
import json
import os
from pathlib import Path
from unittest.mock import patch

from django.apps import apps
from django.conf import settings
from django.core.management import call_command
from django.db import connection

assert settings.APP_ENV == 'test'
assert settings.INSTANCE_ID in ('prefix-a', 'prefix-b')
assert connection.settings_dict['NAME'] == connection.settings_dict['USER'] == 'task_tracker_test'
phase = os.environ['PREFIX_CHECK_PHASE']
snapshot = Path(settings.MEDIA_ROOT) / '.prefix-snapshot.json'
if phase == 'reset':
    assert settings.INSTANCE_ID == 'prefix-a'
    user = apps.get_model('accounts', 'User').objects.get(email__startswith='prefix-same-')
    with patch('accounts.management.commands.reset_password.getpass', return_value='prefix-server-recovery-long-password'):
        call_command('reset_password', email=user.email)
    print('Targeted server reset completed for prefix-a only.')
else:
    data = {}
    for label in ('accounts.User', 'projects.Organization', 'projects.Project', 'access.OrganizationGrant',
                  'access.ProjectGrant', 'tasks.Task', 'remarks.Remark', 'timesheets.Timesheet',
                  'timesheets.WorkSession', 'timesheets.TimeEntry', 'content.Reference', 'content.ContentImage',
                  'core.MutationLock'):
        model = apps.get_model(label)
        fields = [field.attname for field in model._meta.concrete_fields if field.name not in ('password', 'last_login')]
        data[label] = list(model.objects.order_by(model._meta.pk.name).values(*fields))
    images = apps.get_model('content', 'ContentImage').objects.all()
    assert images.exists(), 'Image persistence requires actual synthetic uploads.'
    data['image_bytes'] = {str(image.pk): hashlib.sha256((Path(settings.MEDIA_ROOT) / image.file_name).read_bytes()).hexdigest()
                           for image in images}
    with connection.cursor() as cursor:
        cursor.execute('SELECT system_identifier FROM pg_control_system()')
        data['database_identity'] = str(cursor.fetchone()[0])
    serialized = json.dumps(data, default=str, sort_keys=True)
    if phase == 'before':
        snapshot.write_text(serialized)
        print(f'{settings.INSTANCE_ID}: captured database identity, all domain records and private image bytes.')
    else:
        assert phase == 'after'
        assert snapshot.read_text() == serialized, 'Instance data or upload bytes changed during replacement.'
        print(f'{settings.INSTANCE_ID}: database identity, all domain records and image bytes preserved.')
