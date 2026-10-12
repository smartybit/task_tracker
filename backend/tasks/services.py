from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers

from access.policies import can_remark, can_task
from core.api import StrictSerializer
from core.domain import DomainError, current_user, find, mutation, require_admin
from core.models import MutationLock
from projects.models import Project
from projects.services import validated
from tasks.models import Task, TaskStatus, TaskStatusChange


class StatusInput(StrictSerializer):
    name = serializers.CharField(max_length=200)
    final = serializers.BooleanField()


@mutation
def save_status(actor, data, pk=None):
    require_admin(actor)
    values = validated(StatusInput, data)
    status = find(TaskStatus, pk) if pk else TaskStatus()
    if status.first_used_at:
        raise DomainError('status_already_used', 'A used status cannot be changed.', 409)
    status.name, status.final = values['name'], values['final']
    status.save()
    return status


@mutation
def delete_status(actor, pk):
    require_admin(actor)
    status = find(TaskStatus, pk)
    if status.first_used_at:
        raise DomainError('status_already_used', 'A used status cannot be deleted.', 409)
    status.delete()


class RevisionInput(StrictSerializer):
    expected_revision = serializers.IntegerField(min_value=0)


class CompoundInput(RevisionInput):
    expected_domain_revision = serializers.IntegerField(min_value=0, required=False)
    confirm = serializers.BooleanField(default=False)
    reopen_status = serializers.UUIDField(required=False)


class CreateInput(CompoundInput):
    expected_revision = None
    title = serializers.CharField(max_length=200)
    description = serializers.CharField(allow_blank=True, default='')
    project = serializers.UUIDField()
    parent = serializers.UUIDField(allow_null=True, default=None)
    status = serializers.UUIDField()


class EditInput(RevisionInput):
    title = serializers.CharField(max_length=200, required=False)
    description = serializers.CharField(allow_blank=True, required=False)


class OwnerInput(RevisionInput):
    owner = serializers.UUIDField()


class StatusChangeInput(CompoundInput):
    status = serializers.UUIDField()


class MoveInput(CompoundInput):
    parent = serializers.UUIDField(allow_null=True)
    project = serializers.UUIDField(required=False)


class DeleteInput(CompoundInput):
    pass


INPUTS = {'create': CreateInput, 'edit': EditInput, 'owner': OwnerInput,
          'status': StatusChangeInput, 'move': MoveInput, 'delete': DeleteInput}
COMPOUND = {'create', 'status', 'move', 'delete'}


def require_write(actor, project):
    if not can_task(actor, project, write=True):
        raise DomainError('permission_denied', 'Task write access is required.', 403)


def eligible_owner(owner, project):
    if not owner.is_active or not can_task(owner, project, write=True):
        raise DomainError('owner_ineligible', 'The selected owner needs task write access in the project.', 409)


def descendants(task):
    # Build the adjacency map once, including every status and every descendant.
    rows = list(Task.objects.filter(project=task.project).select_related('status', 'project', 'owner'))
    children = {}
    for row in rows:
        children.setdefault(row.parent_id, []).append(row)
    result, pending = [], list(children.get(task.pk, []))
    while pending:
        row = pending.pop()
        result.append(row)
        pending.extend(children.get(row.pk, []))
    return result


def ancestors(parent):
    result, seen = [], set()
    while parent:
        if parent.pk in seen:
            raise DomainError('hierarchy_cycle', 'The hierarchy would contain a cycle.', 409)
        seen.add(parent.pk)
        result.append(parent)
        parent = parent.parent
    return result


def task_data(task):
    return {'id': str(task.pk), 'title': task.title, 'description': task.description,
            'project': str(task.project_id), 'parent': str(task.parent_id) if task.parent_id else None,
            'owner': str(task.owner_id), 'owner_name': task.owner.display_name or 'Unnamed user',
            'creator': str(task.creator_id), 'status': str(task.status_id), 'revision': task.revision}


def acknowledgement(task):
    return {'id': str(task.pk), 'revision': task.revision}


def prepare(actor, kind, data, pk=None):
    actor = current_user(actor)
    values = validated(INPUTS[kind], data)
    task = find(Task, pk) if pk else None
    changes = []
    if task:
        require_write(actor, task.project)
        if values['expected_revision'] != task.revision:
            raise DomainError('stale_revision', 'The task changed. Refresh it and review your change again.', 409)
    if kind == 'create':
        project = find(Project, values['project'])
        require_write(actor, project)
        eligible_owner(actor, project)
        task = Task(title=values['title'], description=values['description'], project=project,
                    owner=actor, creator=actor, status=find(TaskStatus, values['status']))
        task.parent = find(Task, values['parent']) if values['parent'] else None
        if task.parent and task.parent.project_id != project.pk:
            raise DomainError('project_mismatch', 'Parent and child must belong to the same project.', 409)
        changes = [task]
    elif kind == 'edit':
        for field in ('title', 'description'):
            if field in values:
                setattr(task, field, values[field])
        changes = [task]
    elif kind == 'owner':
        owner = find(get_user_model(), values['owner'])
        eligible_owner(owner, task.project)
        task.owner = owner
        changes = [task]
    elif kind == 'status':
        selected = find(TaskStatus, values['status'])
        if selected.final and any(not row.status.final for row in descendants(task)):
            raise DomainError('non_final_descendant', 'Every descendant must be final before finalizing this task.', 409)
        task.status = selected
        changes = [task]
    elif kind == 'move':
        subtree = [task, *descendants(task)]
        parent = find(Task, values['parent']) if values['parent'] else None
        if parent and parent.pk in {row.pk for row in subtree}:
            raise DomainError('hierarchy_cycle', 'A task cannot be moved beneath itself or a descendant.', 409)
        destination = find(Project, values['project']) if 'project' in values else task.project
        require_write(actor, destination)
        if parent and parent.project_id != destination.pk:
            raise DomainError('project_mismatch', 'Select the destination project explicitly when moving across projects.', 409)
        if destination.pk != task.project_id:
            for row in subtree:
                eligible_owner(row.owner, destination)
                row.project = destination
        task.parent = parent
        changes = subtree if destination.pk != Task.objects.get(pk=task.pk).project_id else [task]
    elif kind == 'delete':
        if task.children.exists() or task.time_entries.exists():
            raise DomainError('task_in_use', 'This task has child tasks or recorded time and cannot be deleted.', 409)
        if task.remarks.exists() and not can_remark(actor, task.project, write=True):
            raise DomainError('permission_denied', 'Task read and remark write access are required to delete a task with remarks.', 403)
    if kind in {'create', 'status', 'move'}:
        has_non_final = not task.status.final
        if kind == 'move':
            has_non_final = any(not row.status.final for row in subtree)
        reopening = [row for row in ancestors(task.parent) if row.status.final] if has_non_final else []
        if reopening:
            if 'reopen_status' not in values:
                raise DomainError('reopen_status_required', 'Select a non-final status for the final ancestors that must reopen.', 409)
            reopen = find(TaskStatus, values['reopen_status'])
            if reopen.final:
                raise DomainError('invalid_reopen_status', 'Ancestors must reopen into a non-final status.', 409)
            for row in reopening:
                require_write(actor, row.project)
                row.status = reopen
                changes.append(row)
    return actor, task, changes, values


@transaction.atomic
def preview_task(actor, kind, data, pk=None):
    lock = MutationLock.objects.select_for_update().get(pk='domain')
    actor, task, changes, values = prepare(actor, kind, data, pk)
    originals = {row.pk: row for row in Task.objects.filter(pk__in=[row.pk for row in changes]).select_related('project')}
    visible = [row for row in changes if can_task(actor, row.project)
               and (row.pk not in originals or can_task(actor, originals[row.pk].project))]
    return {'domain_revision': lock.revision, 'confirmation_required': True,
            'affected': [task_data(row) for row in visible],
            'target': acknowledgement(task) if pk else None,
            'delete': {**acknowledgement(task), 'remarks': task.remarks.count()} if kind == 'delete' else None}


@mutation
def change_task(actor, kind, data, pk=None):
    actor, task, changes, values = prepare(actor, kind, data, pk)
    lock = MutationLock.objects.get(pk='domain')
    if kind in COMPOUND:
        if not values['confirm'] or 'expected_domain_revision' not in values:
            raise DomainError('confirmation_required', 'Preview and confirm this change first.', 409)
        if values['expected_domain_revision'] != lock.revision:
            raise DomainError('stale_preview', 'The preview is out of date. Review the change again.', 409)
    if kind == 'delete':
        result = acknowledgement(task)
        task.delete()
    else:
        for row in changes:
            previous = Task.objects.filter(pk=row.pk).values_list('status_id', flat=True).first()
            if previous is not None:
                row.revision += 1
            row.save()
            if kind in {'create', 'edit'}:
                from content.references import sync_references
                sync_references(row)
            if previous != row.status_id:
                TaskStatusChange.objects.create(task=row, previous_status_id=previous,
                                               new_status_id=row.status_id, actor=actor)
        result = task_data(task) if can_task(actor, task.project) else acknowledgement(task)
    return {**result, 'domain_revision': lock.revision + 1}
