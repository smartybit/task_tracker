import uuid

from django.conf import settings
from django.db import models


class Remark(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey('tasks.Task', on_delete=models.CASCADE, related_name='remarks')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='remarks')
    body = models.TextField()
    starred = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(null=True, editable=False)
    revision = models.PositiveBigIntegerField(default=0)

    class Meta:
        ordering = ['created_at', 'id']
        indexes = [models.Index(fields=['task', 'created_at', 'id'], name='remark_task_chronology')]
