import re
from uuid import UUID

from rest_framework import serializers

from access.policies import can_remark, can_task
from core.api import StrictSerializer
from core.domain import current_user
from content.models import Reference
from content.images import IMAGE_TOKEN
from projects.services import validated
from remarks.models import Remark
from tasks.models import Task

TOKEN = re.compile(r'\[(task|remark):([0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12})\]')


def sync_references(source):
    # Called inside the containing object's mutation transaction. Targets are
    # identifiers, not foreign keys: deletion must leave an unavailable link.
    field, body = ('source_task', source.description) if isinstance(source, Task) else ('source_remark', source.body)
    desired = {(kind, UUID(pk)) for kind, pk in TOKEN.findall(body)}
    rows = Reference.objects.filter(**{field: source})
    existing = {(row.target_kind, row.target_id): row for row in rows}
    remove = [row.pk for key, row in existing.items() if key not in desired]
    if remove:
        Reference.objects.filter(pk__in=remove).delete()
    Reference.objects.bulk_create([Reference(**{field: source}, target_kind=kind, target_id=pk)
                                   for kind, pk in desired - set(existing)])


class TargetInput(StrictSerializer):
    kind = serializers.ChoiceField(choices=['task', 'remark'])
    id = serializers.UUIDField()


class ResolveInput(StrictSerializer):
    targets = TargetInput(many=True, max_length=100, allow_empty=True)


def resolve_references(actor, data):
    actor = current_user(actor)
    values = validated(ResolveInput, data)
    tasks = {row.pk: row for row in Task.objects.filter(pk__in=[t['id'] for t in values['targets'] if t['kind'] == 'task']).select_related('project')}
    remarks = {row.pk: row for row in Remark.objects.filter(pk__in=[t['id'] for t in values['targets'] if t['kind'] == 'remark']).select_related('task__project')}
    result = []
    for target in values['targets']:
        row = (tasks if target['kind'] == 'task' else remarks).get(target['id'])
        item = {'kind': target['kind'], 'id': str(target['id']), 'available': False, 'label': 'Unavailable reference'}
        if row and (can_task(actor, row.project) if target['kind'] == 'task' else can_remark(actor, row.task.project)):
            item.update(available=True, task=str(row.pk if target['kind'] == 'task' else row.task_id),
                        label=row.title if target['kind'] == 'task' else f"Remark: {IMAGE_TOKEN.sub('Image', TOKEN.sub('Reference', row.body))[:120]}")
        result.append(item)
    return {'results': result}
