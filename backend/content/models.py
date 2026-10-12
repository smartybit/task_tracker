from django.db import models


class Reference(models.Model):
    source_task = models.ForeignKey('tasks.Task', null=True, on_delete=models.CASCADE, related_name='references')
    source_remark = models.ForeignKey('remarks.Remark', null=True, on_delete=models.CASCADE, related_name='references')
    target_kind = models.CharField(max_length=6, choices=[('task', 'Task'), ('remark', 'Remark')])
    target_id = models.UUIDField()

    class Meta:
        constraints = [
            models.CheckConstraint(condition=(models.Q(source_task__isnull=False, source_remark__isnull=True)
                                               | models.Q(source_task__isnull=True, source_remark__isnull=False)),
                                   name='reference_exactly_one_source'),
            models.CheckConstraint(condition=models.Q(target_kind__in=['task', 'remark']), name='reference_valid_kind'),
            models.UniqueConstraint(fields=['source_task', 'target_kind', 'target_id'], name='reference_unique_task_target'),
            models.UniqueConstraint(fields=['source_remark', 'target_kind', 'target_id'], name='reference_unique_remark_target'),
        ]
