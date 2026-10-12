from django.utils import timezone
from rest_framework import serializers

from access.policies import can_remark
from core.api import StrictSerializer
from core.domain import DomainError, current_user, find, mutation
from projects.services import validated
from remarks.models import Remark
from tasks.models import Task


class CreateInput(StrictSerializer):
    body = serializers.CharField(trim_whitespace=False)

    def validate_body(self, value):
        if not value.strip():
            raise serializers.ValidationError('Enter some remark text.')
        return value


class RevisionInput(StrictSerializer):
    expected_revision = serializers.IntegerField(min_value=0)


class EditInput(CreateInput, RevisionInput):
    pass


class StarInput(RevisionInput):
    starred = serializers.BooleanField()


def require_remark(actor, task, *, write=False):
    if not can_remark(actor, task.project, write=write):
        raise DomainError('permission_denied' if write else 'not_found',
                          'Task read and remark write access are required.' if write
                          else 'The requested record is unavailable.', 403 if write else 404)


def remark_data(remark):
    return {'id': str(remark.pk), 'task': str(remark.task_id),
            'author': str(remark.author_id), 'author_name': remark.author.display_name or 'Unnamed user',
            'body': remark.body, 'starred': remark.starred,
            'created_at': remark.created_at.isoformat(),
            'edited_at': remark.edited_at.isoformat() if remark.edited_at else None,
            'revision': remark.revision}


@mutation
def change_remark(actor, kind, data, pk):
    actor = current_user(actor)
    remark = None if kind == 'create' else find(Remark, pk)
    task = find(Task, pk) if kind == 'create' else remark.task
    require_remark(actor, task, write=True)
    values = validated({'create': CreateInput, 'edit': EditInput,
                        'star': StarInput, 'delete': RevisionInput}[kind], data)
    if remark and values['expected_revision'] != remark.revision:
        raise DomainError('stale_revision', 'The remark changed. Reload remarks and review your change again.', 409)
    if kind == 'create':
        remark = Remark.objects.create(task=task, author=actor, body=values['body'])
    elif kind == 'delete':
        result = {'id': str(remark.pk), 'revision': remark.revision}
        remark.delete()
        return result
    else:
        if kind == 'edit':
            remark.body, remark.edited_at = values['body'], timezone.now()
        else:
            remark.starred = values['starred']
        remark.revision += 1
        remark.save()
    if kind in {'create', 'edit'}:
        from content.references import sync_references
        sync_references(remark)
    return remark_data(remark) if can_remark(actor, task.project) else {
        'id': str(remark.pk), 'revision': remark.revision}
