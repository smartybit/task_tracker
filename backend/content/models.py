from django.db import models
from uuid import uuid4
from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver


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


class ContentImage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    source_task = models.ForeignKey('tasks.Task', null=True, on_delete=models.CASCADE, related_name='images')
    source_remark = models.ForeignKey('remarks.Remark', null=True, on_delete=models.CASCADE, related_name='images')
    file_name = models.CharField(max_length=100, unique=True)
    format = models.CharField(max_length=4)
    size = models.PositiveIntegerField()
    width = models.PositiveIntegerField()
    height = models.PositiveIntegerField()

    class Meta:
        constraints = [models.CheckConstraint(
            condition=(models.Q(source_task__isnull=False, source_remark__isnull=True)
                       | models.Q(source_task__isnull=True, source_remark__isnull=False)),
            name='image_exactly_one_source')]


@receiver(post_delete, sender=ContentImage)
def remove_image_file(sender, instance, **kwargs):
    from content.images import image_storage
    storage, name = image_storage(), instance.file_name
    # Rollback must retain files. A cleanup I/O error must not disguise a committed
    # deletion as a failed mutation; prune_content_images can retry orphan cleanup.
    transaction.on_commit(lambda: storage.delete(name), robust=True)
