from rest_framework import serializers

from access.models import OrganizationGrant, ProjectGrant
from access.policies import FLAGS, effective_flags, grant_flags
from core.api import StrictSerializer
from core.domain import DomainError, find, mutation, require_admin
from projects.models import Organization, Project
from django.contrib.auth import get_user_model


class GrantInput(StrictSerializer):
    task_read = serializers.BooleanField(default=False)
    task_write = serializers.BooleanField(default=False)
    remark_read = serializers.BooleanField(default=False)
    remark_write = serializers.BooleanField(default=False)


@mutation
def replace_grant(actor, user_id, scope, target_id, data):
    require_admin(actor)
    if scope not in {"organizations", "projects"}:
        raise DomainError("invalid_input", "Unknown grant scope.")
    user = find(get_user_model(), user_id)
    model, target_model, field = (OrganizationGrant, Organization, 'organization') if scope == 'organizations' else (ProjectGrant, Project, 'project')
    target = find(target_model, target_id)
    serializer = GrantInput(data=data)
    serializer.is_valid(raise_exception=True)
    grant, _ = model.objects.update_or_create(user=user, **{field: target}, defaults=serializer.validated_data)
    return {field: str(target.pk), **grant_flags(grant)}


def grants_data(actor, user_id):
    require_admin(actor)
    user = find(get_user_model(), user_id)
    return {
        'organizations': [{'organization': str(g.organization_id), **grant_flags(g)} for g in OrganizationGrant.objects.filter(user=user).order_by('organization_id')],
        'projects': [{'project': str(g.project_id), **grant_flags(g)} for g in ProjectGrant.objects.filter(user=user).order_by('project_id')],
        'effective_projects': [{'project': str(p.pk), **effective_flags(user, p)} for p in Project.objects.all()] if user.is_active else [],
    }
