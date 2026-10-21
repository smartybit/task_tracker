from django.db.models import Q

from access.models import OrganizationGrant, ProjectGrant
from core.domain import current_user
from projects.models import Project

FLAGS = ('task_read', 'task_write', 'remark_read', 'remark_write')


def grant_flags(grant):
    return {flag: bool(grant and getattr(grant, flag)) for flag in FLAGS}


def effective_flags(user, project):
    user = current_user(user)
    local = grant_flags(ProjectGrant.objects.filter(user=user, project=project).first())
    inherited = grant_flags(OrganizationGrant.objects.filter(user=user, organization_id=project.organization_id).first())
    return {flag: local[flag] or inherited[flag] for flag in FLAGS}


def can_task(user, project, *, write=False):
    return effective_flags(user, project)['task_write' if write else 'task_read']


def can_remark(user, project, *, write=False):
    flags = effective_flags(user, project)
    return flags['task_read'] and flags['remark_write' if write else 'remark_read']


def can_timesheet(user, owner_id, *, write=False):
    user = current_user(user)
    return str(user.pk) == str(owner_id) or getattr(user, 'write_others_timesheets' if write else 'read_others_timesheets')


def can_report(user, project, owner_id):
    return can_task(user, project) and can_timesheet(user, owner_id)


def selectable_projects(user):
    user = current_user(user)
    # This selector deliberately has no administrator bypass. Management views
    # separately expose catalogs; they never authorize application data.
    return Project.objects.filter(
        Q(projectgrant__user=user, projectgrant__task_read=True)
        | Q(projectgrant__user=user, projectgrant__task_write=True)
        | Q(organization__organizationgrant__user=user, organization__organizationgrant__task_read=True)
        | Q(organization__organizationgrant__user=user, organization__organizationgrant__task_write=True)
    ).distinct().order_by('name', 'id')
