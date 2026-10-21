import uuid

from django.conf import settings
from django.db import models
from django.contrib.postgres.indexes import GinIndex
from content.search_config import search_vector


class TaskStatus(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, unique=True)
    final = models.BooleanField(default=False)
    first_used_at = models.DateTimeField(null=True, editable=False)

    class Meta:
        ordering = ['name', 'id']


class Task(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    project = models.ForeignKey('projects.Project', on_delete=models.PROTECT, related_name='tasks')
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.PROTECT, related_name='children')
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='owned_tasks')
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='created_tasks')
    status = models.ForeignKey(TaskStatus, on_delete=models.PROTECT)
    revision = models.PositiveBigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['title', 'id']
        indexes = [GinIndex(search_vector('title', 'description'), name='task_content_search')]
        constraints = [models.CheckConstraint(condition=~models.Q(parent=models.F('id')), name='task_not_own_parent')]


class TaskStatusChange(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='history')
    previous_status = models.ForeignKey(TaskStatus, null=True, on_delete=models.PROTECT, related_name='+')
    new_status = models.ForeignKey(TaskStatus, on_delete=models.PROTECT, related_name='+')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['changed_at', 'id']
