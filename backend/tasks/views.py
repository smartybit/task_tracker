from django.contrib.auth import get_user_model
from rest_framework.response import Response
from rest_framework.views import APIView

from access.policies import can_task, selectable_projects
from core.api import page
from core.domain import DomainError, current_user, find
from core.models import MutationLock
from projects.models import Project
from projects.views import visible_record
from tasks.models import Task, TaskStatus
from tasks.services import change_task, delete_status, preview_task, save_status, task_data


def status_data(status):
    return {'id': str(status.pk), 'name': status.name, 'final': status.final, 'used': status.first_used_at is not None}


def readable_tasks(user):
    current_user(user)
    projects = [p.pk for p in selectable_projects(user) if can_task(user, p)]
    return Task.objects.filter(project_id__in=projects).select_related('owner', 'project', 'status')


class StatusesView(APIView):
    def get(self, request):
        current_user(request.user)
        return page(TaskStatus.objects.all(), request, status_data)

    def post(self, request):
        return Response(status_data(save_status(request.user, request.data)), status=201)


class StatusView(APIView):
    def patch(self, request, pk):
        return Response(status_data(save_status(request.user, request.data, pk)))

    def delete(self, request, pk):
        delete_status(request.user, pk)
        return Response(status=204)


class OwnersView(APIView):
    def get(self, request, pk):
        project = find(Project, pk)
        if not can_task(request.user, project, write=True):
            raise DomainError('permission_denied', 'Task write access is required.', 403)
        # A scoped selection directory exposes only labels needed for assignment.
        users = [user for user in get_user_model().objects.filter(is_active=True).order_by('display_name', 'id') if can_task(user, project, write=True)]
        return Response({'results': [{'id': str(user.pk), 'display_name': user.display_name or 'Unnamed user'} for user in users]})


class TasksView(APIView):
    def get(self, request):
        rows = readable_tasks(request.user)
        from uuid import UUID
        try:
            if request.query_params.get('project'):
                rows = rows.filter(project_id=UUID(request.query_params['project']))
            statuses = request.query_params.getlist('status')
            if statuses:
                rows = rows.filter(status_id__in=[UUID(value) for value in statuses])
        except ValueError as exc:
            raise DomainError('invalid_input', 'Project and status filters must be UUIDs.') from exc
        view = request.query_params.get('view', 'flat')
        if view not in {'flat', 'tree'}:
            raise DomainError('invalid_input', 'View must be flat or tree.')
        response = page(rows, request, task_data)
        # Parent IDs let the client build a forest even when a filter excludes parents.
        response.data['domain_revision'] = MutationLock.objects.get(pk='domain').revision
        return response

    def post(self, request):
        return Response(change_task(request.user, 'create', request.data), status=201)


class TaskView(APIView):
    def get(self, request, pk):
        data = task_data(visible_record(readable_tasks(request.user), pk))
        data['domain_revision'] = MutationLock.objects.get(pk='domain').revision
        return Response(data)

    def patch(self, request, pk):
        return Response(change_task(request.user, 'edit', request.data, pk))

    def delete(self, request, pk):
        return Response(change_task(request.user, 'delete', request.data, pk))


class HistoryView(APIView):
    def get(self, request, pk):
        task = visible_record(readable_tasks(request.user), pk)
        return page(task.history.select_related('actor', 'previous_status', 'new_status'), request, lambda row: {
            'id': row.pk, 'previous_status': str(row.previous_status_id) if row.previous_status_id else None,
            'new_status': str(row.new_status_id), 'actor_name': row.actor.display_name or 'Unnamed user',
            'changed_at': row.changed_at.isoformat()})


class CommandView(APIView):
    def post(self, request, pk, kind):
        return Response(change_task(request.user, kind, request.data, pk))


class PreviewView(APIView):
    def post(self, request, kind, pk=None):
        return Response(preview_task(request.user, kind, request.data, pk))
