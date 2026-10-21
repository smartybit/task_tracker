from django.db.models import Q
from rest_framework.response import Response
from rest_framework.views import APIView

from access.models import OrganizationGrant
from access.policies import effective_flags, selectable_projects
from core.api import page
from core.domain import DomainError, current_user
from projects.models import Organization, Project
from projects.services import delete_catalog, save_organization, save_project


def organization_data(org):
    return {'id': str(org.pk), 'name': org.name}


def project_data(project, user):
    return {'id': str(project.pk), 'name': project.name, 'organization': str(project.organization_id),
            'permissions': effective_flags(user, project)}


def visible_organizations(user):
    user = current_user(user)
    if user.is_admin:
        return Organization.objects.all()
    direct = OrganizationGrant.objects.filter(user=user).filter(Q(task_read=True) | Q(task_write=True))
    return Organization.objects.filter(Q(projects__in=selectable_projects(user)) | Q(pk__in=direct.values('organization_id'))).distinct().order_by('name', 'id')


def visible_projects(user):
    user = current_user(user)
    return Project.objects.all() if user.is_admin else selectable_projects(user)


def visible_record(queryset, pk):
    result = queryset.filter(pk=pk).first()
    if result is None:
        raise DomainError('not_found', 'The requested record is unavailable.', 404)
    return result


class OrganizationsView(APIView):
    def get(self, request):
        return page(visible_organizations(request.user), request, organization_data)

    def post(self, request):
        return Response(organization_data(save_organization(request.user, request.data)), status=201)


class OrganizationView(APIView):
    def get(self, request, pk):
        return Response(organization_data(visible_record(visible_organizations(request.user), pk)))

    def patch(self, request, pk):
        return Response(organization_data(save_organization(request.user, request.data, pk)))

    def delete(self, request, pk):
        delete_catalog(request.user, Organization, pk)
        return Response(status=204)


class ProjectsView(APIView):
    def get(self, request):
        return page(visible_projects(request.user), request, lambda p: project_data(p, request.user))

    def post(self, request):
        return Response(project_data(save_project(request.user, request.data), request.user), status=201)


class ProjectView(APIView):
    def get(self, request, pk):
        return Response(project_data(visible_record(visible_projects(request.user), pk), request.user))

    def patch(self, request, pk):
        return Response(project_data(save_project(request.user, request.data, pk), request.user))

    def delete(self, request, pk):
        delete_catalog(request.user, Project, pk)
        return Response(status=204)
