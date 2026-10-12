"""Run inside the isolated test web service before/after container replacement."""
import base64
from io import BytesIO
import os
from uuid import uuid4

from django.conf import settings
from PIL import Image
from rest_framework.test import APIClient

from access.services import replace_grant
from accounts.models import User
from accounts.services import create_account
from content.models import ContentImage
from projects.services import save_organization, save_project
from tasks.models import Task, TaskStatus
from tasks.services import change_task, preview_task

assert settings.APP_ENV == 'test'
assert str(settings.MEDIA_ROOT) == '/var/lib/task-tracker/uploads'
admin = User.objects.get(email='admin@example.test')
output = BytesIO()
Image.new('RGB', (8, 6), color='green').save(output, format='PNG')
raw = output.getvalue()
if os.environ['IMAGE_CHECK_PHASE'] == 'before':
    key = uuid4().hex
    actor = create_account(admin, {'email': f'persist-{key}@example.test', 'display_name': 'Persistence reader',
                                   'password': 'synthetic-persistence-only-password'})
    org = save_organization(admin, {'name': f'Persistence {key}'})
    project = save_project(admin, {'name': 'Image persistence', 'organization': str(org.pk)})
    replace_grant(admin, actor.pk, 'projects', project.pk, {'task_read': True, 'task_write': True})
    image_id = str(uuid4())
    payload = {'title': 'Stage 8 persistence proof', 'project': str(project.pk),
               'status': str(TaskStatus.objects.get(name='In Progress').pk),
               'description': f'[image:{image_id}]',
               'images': [{'id': image_id, 'data': base64.b64encode(raw).decode()}]}
    preview = preview_task(actor, 'create', payload)
    change_task(actor, 'create', {**payload, 'confirm': True, 'expected_domain_revision': preview['domain_revision']})
task = Task.objects.get(title='Stage 8 persistence proof')
image = ContentImage.objects.get(source_task=task)
client = APIClient()
client.force_authenticate(task.owner)
response = client.get(f'/api/v1/images/{image.pk}/', HTTP_HOST='localhost')
assert response.status_code == 200, response.status_code
assert b''.join(response.streaming_content) == raw
response.close()
client.force_authenticate(admin)
assert client.get(f'/api/v1/images/{image.pk}/', HTTP_HOST='localhost').status_code == 404
print('Image metadata, original bytes and private access verified:', os.environ['IMAGE_CHECK_PHASE'])
