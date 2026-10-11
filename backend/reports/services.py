"""Project-restricted reports, materialized inside one authorized read snapshot."""
import csv
from contextlib import contextmanager
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from io import TextIOWrapper
from tempfile import SpooledTemporaryFile
from uuid import UUID

from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.db.models import Q
from django.utils import timezone

from core.domain import DomainError, current_user
from projects.models import Project
from tasks.models import Task
from timesheets.models import TimeEntry
from timesheets.services import bounds, date_of


@contextmanager
def snapshot():
    # Set isolation before the first query, including the current-account check.
    # Responses and CSV bytes must be evaluated before leaving this transaction.
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        yield


def readable_projects(actor):
    return Project.objects.filter(
        Q(projectgrant__user=actor, projectgrant__task_read=True)
        | Q(organization__organizationgrant__user=actor, organization__organizationgrant__task_read=True)
    ).distinct().order_by('name', 'id')


def authorized_records(actor, projects):
    rows = TimeEntry.objects.filter(kind='task', task__project_id__in=projects)
    if not actor.read_others_timesheets:
        rows = rows.filter(timesheet_id=actor.pk)
    return rows


def person_data(person):
    return {'id': str(person.pk), 'name': person.display_name or 'Unnamed user'}


def choices(actor):
    projects = list(readable_projects(actor))
    project_ids = [p.pk for p in projects]
    tasks = list(Task.objects.filter(project_id__in=project_ids).order_by('title', 'id'))
    people = list(get_user_model().objects.filter(
        Q(pk=actor.pk) | Q(pk__in=authorized_records(actor, project_ids).values('timesheet_id'))
    ).order_by('display_name', 'id'))
    return projects, tasks, people


def options(actor):
    with snapshot():
        actor = current_user(actor)
        projects, tasks, people = choices(actor)
        return {'time_zone': str(timezone.get_default_timezone()),
                'today': date_of(timezone.now()).isoformat(),
                'read_others_timesheets': actor.read_others_timesheets,
                'projects': [{'id': str(p.pk), 'name': p.name} for p in projects],
                'tasks': [{'id': str(t.pk), 'title': t.title, 'project': str(t.project_id),
                           'parent': str(t.parent_id) if t.parent_id else None} for t in tasks],
                'people': [person_data(p) for p in people]}


def parameters(params, *, export=False):
    allowed = {'from', 'to'} if export else {'from', 'to', 'project', 'person', 'task'}
    if set(params) - allowed or any(len(params.getlist(k)) != 1 for k in params):
        raise DomainError('invalid_input', 'Unsupported or repeated report filter.')
    try:
        start, end = (date.fromisoformat(params[key]) for key in ('from', 'to'))
        if start > end or end == date.max:
            raise ValueError
        # Use the configured zone, not the browser or database session zone.
        window = bounds(start)[0], bounds(end)[1]
        filters = {key: UUID(params[key]) for key in ('project', 'person', 'task') if params.get(key)}
    except (KeyError, ValueError, OverflowError) as exc:
        raise DomainError('invalid_input', 'Supply an inclusive from/to date range and valid UUID filters.') from exc
    return start, end, window, filters


def subtree(tasks, root):
    children = {}
    for task in tasks:
        children.setdefault(task.parent_id, []).append(task.pk)
    selected, pending = set(), [root]
    while pending:
        key = pending.pop()
        if key not in selected:
            selected.add(key)
            pending.extend(children.get(key, []))
    return selected


def microseconds(span):
    return ((span.days * 86400 + span.seconds) * 1_000_000) + span.microseconds


def hours(duration):
    return format((Decimal(duration) / Decimal(3_600_000_000)).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP), 'f')


def fragments(rows, window):
    """Clip known spans to the period and split at local midnight without writes.

    Supports legacy unsplit spans and reallocation after a working-zone change.
    Unfinished entries belong only to their start day and always contribute zero.
    """
    lower, upper = window
    for row in rows:
        if row.ended_at is None:
            if lower <= row.started_at < upper:
                yield row, date_of(row.started_at), row.started_at, None, 0
            continue
        start, end = max(row.started_at, lower), min(row.ended_at, upper)
        while start < end:
            day = date_of(start)
            stop = min(end, bounds(day)[1])
            yield row, day, start, stop, microseconds(stop - start)
            start = stop


def selected_records(actor, params, *, export=False):
    start, end, window, filters = parameters(params, export=export)
    projects, tasks, people = choices(actor)
    for field, available in [('project', projects), ('task', tasks), ('person', people)]:
        if field in filters and filters[field] not in {item.pk for item in available}:
            raise DomainError('not_found', 'The requested report selection is unavailable.', 404)
    if 'project' in filters:
        projects = [p for p in projects if p.pk == filters['project']]
        tasks = [t for t in tasks if t.project_id == filters['project']]
    if 'task' in filters:
        ids = subtree(tasks, filters['task'])
        tasks = [t for t in tasks if t.pk in ids]
    rows = authorized_records(actor, [p.pk for p in projects]).filter(task_id__in=[t.pk for t in tasks])
    if 'person' in filters:
        rows = rows.filter(timesheet_id=filters['person'])
    lower, upper = window
    rows = rows.filter(started_at__lt=upper).filter(
        Q(ended_at__gt=lower) | Q(ended_at__isnull=True, started_at__gte=lower)
    ).select_related('task__project', 'timesheet__user').order_by('started_at', 'timesheet_id', 'id')
    return start, end, window, projects, tasks, rows.iterator(chunk_size=1000) if export else list(rows)


def report(actor, kind, params):
    with snapshot():
        actor = current_user(actor)
        start, end, window, projects, tasks, rows = selected_records(actor, params)
        direct, project_totals, daily = {}, {}, {}
        total = 0
        for row, day, _, _, duration in fragments(rows, window):
            total += duration
            direct[row.task_id] = direct.get(row.task_id, 0) + duration
            project_totals[row.task.project_id] = project_totals.get(row.task.project_id, 0) + duration
            key = row.timesheet_id, day
            daily[key] = (row.timesheet.user, daily.get(key, (None, 0))[1] + duration)
        if kind == 'projects':
            results = [{'project': str(p.pk), 'name': p.name, 'hours': hours(project_totals.get(p.pk, 0))}
                       for p in projects]
        elif kind == 'people-days':
            results = [{'person': str(person.pk), 'name': person.display_name or 'Unnamed user',
                        'date': day.isoformat(), 'hours': hours(duration)}
                       for (_, day), (person, duration) in sorted(
                           daily.items(), key=lambda item: (item[0][1], item[1][0].display_name, str(item[0][0])))]
        elif kind == 'tasks':
            # Bottom-up accumulation counts each direct duration once per ancestor.
            # Iterative traversal supports deep trees without recursion limits.
            by_id = {t.pk: t for t in tasks}
            children = {}
            for task in tasks:
                children.setdefault(task.parent_id, []).append(task)
            ordered, pending = [], [(t, 0) for t in reversed(tasks) if t.parent_id not in by_id]
            while pending:
                task, depth = pending.pop()
                ordered.append((task, depth))
                pending.extend((child, depth + 1) for child in reversed(children.get(task.pk, [])))
            rollup = dict(direct)
            for task, _ in reversed(ordered):
                if task.parent_id in by_id:
                    rollup[task.parent_id] = rollup.get(task.parent_id, 0) + rollup.get(task.pk, 0)
            results = [{'task': str(t.pk), 'title': t.title, 'project': str(t.project_id),
                        'parent': str(t.parent_id) if t.parent_id in by_id else None, 'depth': depth,
                        'direct_hours': hours(direct.get(t.pk, 0)),
                        'descendant_hours': hours(rollup.get(t.pk, 0) - direct.get(t.pk, 0)),
                        'total_hours': hours(rollup.get(t.pk, 0))} for t, depth in ordered]
        else:
            raise ValueError('Unknown report kind')
        return {'from': start.isoformat(), 'to': end.isoformat(),
                'time_zone': str(timezone.get_default_timezone()),
                'total_hours': hours(total), 'results': results}


def export_csv(actor, params):
    # Spool larger exports to disk, completing database reads before serving bytes.
    output = SpooledTemporaryFile(max_size=1024 * 1024, mode='w+b')
    text = TextIOWrapper(output, encoding='utf-8', newline='')
    try:
        with snapshot():
            actor = current_user(actor)
            start, end, window, _, _, rows = selected_records(actor, params, export=True)
            writer = csv.writer(text)
            writer.writerow(['Person', 'Project', 'Task', 'Date', 'Start Time', 'End Time', 'Duration'])
            zone = timezone.get_default_timezone()
            for row, day, began, stopped, duration in fragments(rows, window):
                writer.writerow([row.timesheet.user.display_name or 'Unnamed user', row.task.project.name,
                                 row.task.title, day.isoformat(), timezone.localtime(began, zone).time().isoformat(),
                                 timezone.localtime(stopped, zone).time().isoformat() if stopped else '', hours(duration)])
            text.flush()
        text.detach()
        output.seek(0)
        return output, f'task-records-{start.isoformat()}-to-{end.isoformat()}.csv'
    except Exception:
        text.close()
        output.close()
        raise
