"""Synthetic smoke data for the two disposable development-configuration projects."""
import json
import os
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connection
from timesheets.models import Timesheet

assert settings.APP_ENV == 'development'
assert settings.INSTANCE_ID in ('task-tracker-instance-check-a', 'task-tracker-instance-check-b')
assert connection.settings_dict['NAME'] == connection.settings_dict['USER'] == 'task_tracker_instance'
User = get_user_model()
password = 'development-instance-synthetic-password'
replacement = 'development-instance-synthetic-replacement'
phase = os.environ['INSTANCE_CHECK_PHASE']
snapshot = Path(settings.MEDIA_ROOT) / '.development-check.json'
if phase == 'before':
    assert not User.objects.exists(), 'Refusing to overwrite an existing account.'
    with patch('accounts.management.commands.bootstrap_admin.getpass', return_value=password):
        call_command('bootstrap_admin', email='instance-check@example.test')
if phase == 'reset':
    assert settings.INSTANCE_ID.endswith('-a')
    with patch('accounts.management.commands.reset_password.getpass', return_value=replacement):
        call_command('reset_password', email='instance-check@example.test', reactivate=True, grant_admin=True)
else:
    user = User.objects.get(email='instance-check@example.test')
    with connection.cursor() as cursor:
        cursor.execute('SELECT system_identifier FROM pg_control_system()')
        database_identity = str(cursor.fetchone()[0])
    state = dict(user=str(user.pk), sheet=str(Timesheet.objects.get(user=user).pk), database=database_identity)
    if phase == 'before':
        snapshot.write_text(json.dumps(state, sort_keys=True))
    else:
        assert phase == 'after'
        assert snapshot.read_text() == json.dumps(state, sort_keys=True)
        assert user.check_password(replacement if settings.INSTANCE_ID.endswith('-a') else password)
    assert user.is_active and user.is_admin
    assert not user.read_others_timesheets and not user.write_others_timesheets
    print(f'{settings.INSTANCE_ID}: {phase} isolated bootstrap/recovery and database/upload persistence passed.')
