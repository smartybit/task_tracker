from django.conf import settings
from django.db import models


class GrantFlags(models.Model):
    task_read = models.BooleanField(default=False)
    task_write = models.BooleanField(default=False)
    remark_read = models.BooleanField(default=False)
    remark_write = models.BooleanField(default=False)

    class Meta:
        abstract = True


class OrganizationGrant(GrantFlags):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    organization = models.ForeignKey('projects.Organization', on_delete=models.CASCADE)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'organization'], name='unique_organization_grant')]


class ProjectGrant(GrantFlags):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    project = models.ForeignKey('projects.Project', on_delete=models.CASCADE)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'project'], name='unique_project_grant')]
