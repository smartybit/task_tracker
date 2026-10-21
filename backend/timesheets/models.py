import uuid

from django.conf import settings
from django.db import models
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateTimeRangeField, RangeOperators


class Timesheet(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, primary_key=True, on_delete=models.PROTECT)
    revision = models.PositiveBigIntegerField(default=0)


class WorkSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    timesheet = models.ForeignKey(Timesheet, on_delete=models.PROTECT, related_name='sessions')
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    state = models.CharField(max_length=10, choices=[('active', 'Active'), ('unfinished', 'Unfinished'), ('closed', 'Closed')], default='active')

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(ended_at__isnull=True) | models.Q(ended_at__gt=models.F('started_at')), name='session_positive_duration'),
            models.UniqueConstraint(fields=['timesheet'], condition=models.Q(state='active'), name='one_active_session'),
            models.CheckConstraint(condition=models.Q(state='closed', ended_at__isnull=False) | models.Q(state__in=['active', 'unfinished'], ended_at__isnull=True), name='session_state_matches_end'),
        ]


class TimeEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    timesheet = models.ForeignKey(Timesheet, on_delete=models.PROTECT, related_name='entries')
    session = models.ForeignKey(WorkSession, on_delete=models.PROTECT, related_name='entries')
    kind = models.CharField(max_length=10, choices=[('task', 'Task'), ('break', 'Break')])
    task = models.ForeignKey('tasks.Task', null=True, blank=True, on_delete=models.PROTECT, related_name='time_entries')
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=(models.Q(kind='task', task__isnull=False) | models.Q(kind='break', task__isnull=True)), name='entry_kind_matches_task'),
            models.CheckConstraint(condition=models.Q(ended_at__isnull=True) | models.Q(ended_at__gt=models.F('started_at')), name='entry_positive_duration'),
            models.UniqueConstraint(fields=['session'], condition=models.Q(ended_at__isnull=True), name='one_unfinished_tail'),
            ExclusionConstraint(name='known_entries_do_not_overlap', expressions=[
                ('timesheet', RangeOperators.EQUAL),
                (models.Func('started_at', 'ended_at', models.Value('[)'), function='TSTZRANGE', output_field=DateTimeRangeField()), RangeOperators.OVERLAPS),
            ], condition=models.Q(ended_at__isnull=False)),
        ]
