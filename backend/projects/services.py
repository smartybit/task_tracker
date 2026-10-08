from rest_framework import serializers

from core.api import StrictSerializer
from core.domain import find, mutation, require_admin
from projects.models import Organization, Project


class NameInput(StrictSerializer):
    name = serializers.CharField(max_length=200)


class ProjectInput(NameInput):
    organization = serializers.UUIDField()


def validated(kind, data):
    serializer = kind(data=data)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


@mutation
def save_organization(actor, data, pk=None):
    require_admin(actor)
    values = validated(NameInput, data)
    organization = find(Organization, pk) if pk else Organization()
    organization.name = values['name']
    organization.save()
    return organization


@mutation
def save_project(actor, data, pk=None):
    require_admin(actor)
    # Existing projects cannot change organization through a field edit.
    values = validated(NameInput if pk else ProjectInput, data)
    project = find(Project, pk) if pk else Project(organization=find(Organization, values['organization']))
    project.name = values['name']
    project.save()
    return project


@mutation
def delete_catalog(actor, model, pk):
    require_admin(actor)
    find(model, pk).delete()
