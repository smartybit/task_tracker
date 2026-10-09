"""Authorized, revisioned timesheet commands. Planning never writes to storage."""
from copy import deepcopy
from datetime import datetime, time, timedelta
from uuid import NAMESPACE_URL, uuid4, uuid5

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from access.policies import can_task, can_timesheet
from core.api import StrictSerializer
from core.domain import DomainError, current_user, find, mutation
from core.models import MutationLock
from projects.services import validated
from tasks.models import Task
from timesheets.models import TimeEntry, Timesheet, WorkSession


class RowInput(StrictSerializer):
    id = serializers.UUIDField(required=False)
    client_key = serializers.CharField(max_length=100, required=False)
    kind = serializers.ChoiceField(choices=['task', 'break'])
    task = serializers.UUIDField(allow_null=True, default=None)
    started_at = serializers.DateTimeField()
    ended_at = serializers.DateTimeField(allow_null=True)

    def validate(self, attrs):
        if 'id' not in attrs and 'client_key' not in attrs:
            raise serializers.ValidationError({'client_key': ['A new row needs a stable client key.']})
        return attrs


class SessionInput(StrictSerializer):
    id = serializers.UUIDField(required=False)
    client_key = serializers.CharField(max_length=100, required=False)
    state = serializers.ChoiceField(choices=['active', 'unfinished', 'closed'])
    ended_at = serializers.DateTimeField(allow_null=True)
    rows = RowInput(many=True)


class CommandInput(StrictSerializer):
    command = serializers.ChoiceField(choices=['start', 'switch', 'break', 'append', 'end_day', 'continue', 'resume', 'boundary', 'delete_last', 'replace_day'])
    expected_revision = serializers.IntegerField(min_value=0)
    date = serializers.DateField()
    session = serializers.UUIDField(required=False)
    at = serializers.DateTimeField(required=False)
    task = serializers.UUIDField(allow_null=True, required=False)
    entry = serializers.UUIDField(required=False)
    edge = serializers.ChoiceField(choices=['start', 'end'], required=False)
    sessions = SessionInput(many=True, required=False)
    confirm = serializers.BooleanField(default=False)
    expected_domain_revision = serializers.IntegerField(min_value=0, required=False)


REQUIRED = {
    'start': {'at', 'task'}, 'switch': {'session', 'at', 'task'},
    'break': {'session', 'at'}, 'append': {'session', 'at', 'task'},
    'end_day': {'session', 'at'}, 'continue': {'session', 'at', 'task'},
    'resume': {'session', 'at', 'task'}, 'boundary': {'entry', 'edge', 'at'},
    'delete_last': {'entry'}, 'replace_day': {'sessions'},
}
PREVIEWED = {'boundary', 'delete_last', 'resume'}


def bounds(day):
    zone = timezone.get_default_timezone()
    return (timezone.make_aware(datetime.combine(day, time.min), zone),
            timezone.make_aware(datetime.combine(day + timedelta(days=1), time.min), zone))


def date_of(at):
    return timezone.localtime(at, timezone.get_default_timezone()).date()


def in_day(row, day):
    return date_of(row.started_at) == day


def fail(message, row=None, code='invalid_timeline'):
    key = (getattr(row, '_client_key', None) or str(row.pk)) if row else 'timeline'
    raise DomainError(code, message, 400, {key: [message]})


def gate(actor, owner, write=False):
    actor = current_user(actor)
    if not can_timesheet(actor, owner, write=write):
        raise DomainError('permission_denied', 'Timesheet access is required.', 403)
    return actor


def select_task(actor, pk, *, current=False):
    if pk is None:
        return None
    task = find(Task, pk)
    if not can_task(actor, task.project):
        raise DomainError('permission_denied', 'Task read access is required for a new selection.', 403)
    if current and task.status.final:
        raise DomainError('task_reopen_required', 'Reopen the task separately before recording current work.', 409)
    return task.pk


def entry_data(row, actor):
    task = Task.objects.select_related('project').get(pk=row.task_id) if row.task_id else None
    return {'id': str(row.pk), 'session': str(row.session_id), 'kind': row.kind,
            'task': str(row.task_id) if row.task_id else None,
            'task_label': task.title if task else 'Break',
            'task_readable': can_task(actor, task.project) if task else False,
            'started_at': row.started_at.isoformat(),
            'ended_at': row.ended_at.isoformat() if row.ended_at else None,
            'duration_seconds': (row.ended_at - row.started_at).total_seconds() if row.ended_at and row.kind == 'task' else 0}


def day_data(actor, sheet, day, sessions, rows):
    start, end = bounds(day)
    result = []
    total = timedelta()
    for session in sorted(sessions.values(), key=lambda s: (s.started_at, str(s.pk))):
        selected = sorted([r for r in rows if r.session_id == session.pk and in_day(r, day)], key=lambda r: r.started_at)
        marker = session.ended_at if session.ended_at and start < session.ended_at <= end else None
        if not selected and not marker:
            continue
        items = [entry_data(r, actor) for r in selected]
        total += sum((r.ended_at - r.started_at for r in selected if r.ended_at and r.kind == 'task'), timedelta())
        all_rows = [r for r in rows if r.session_id == session.pk]
        result.append({'id': str(session.pk), 'state': session.state, 'rows': items,
                       'ended_at': marker.isoformat() if marker else None,
                       'continues_before': any(r.started_at < start for r in all_rows),
                       'continues_after': any(r.started_at >= end for r in all_rows)})
    return {'date': day.isoformat(), 'revision': sheet.revision, 'sessions': result,
            'work_seconds': total.total_seconds(), 'unfinished': any(s['state'] != 'closed' and any(r['ended_at'] is None for r in s['rows']) for s in result),
            'time_zone': str(timezone.get_default_timezone())}


def load(sheet, *, normalized=True):
    rows = list(sheet.entries.order_by('started_at', 'id'))
    return ({s.pk: s for s in sheet.sessions.all()}, normalize(rows) if normalized else rows)


def normalize(rows):
    """Split only explicitly known spans; retain the original ID on the first part."""
    result = []
    for row in rows:
        while row.ended_at and row.ended_at > bounds(date_of(row.started_at))[1]:
            midnight = bounds(date_of(row.started_at))[1]
            tail = deepcopy(row)
            # Stable virtual fragments support reads/drafts after a zone change
            # and upgrades of existing unsplit records, without writing on GET.
            tail.pk = uuid5(NAMESPACE_URL, f'timesheet:{row.pk}:{midnight.timestamp()}')
            tail.started_at = midnight
            row.ended_at = midnight
            result.append(row)
            row = tail
        result.append(row)
    return result


def validate_timeline(sessions, rows):
    if sum(s.state == 'active' for s in sessions.values()) > 1:
        fail('Only one session may actively record work.')
    for session in sessions.values():
        entries = sorted([r for r in rows if r.session_id == session.pk], key=lambda r: r.started_at)
        if not entries:
            fail('A session must contain at least one row.', session)
        if entries[0].started_at != session.started_at:
            fail('The first row must match the session start.', entries[0])
        for i, row in enumerate(entries):
            if row.timesheet_id != session.timesheet_id or (row.kind == 'task') != (row.task_id is not None):
                fail('Row kind/task and session must agree.', row)
            if row.ended_at is not None and row.ended_at <= row.started_at:
                fail('A closed row must have positive duration.', row)
            if i < len(entries) - 1 and row.ended_at != entries[i + 1].started_at:
                fail('Rows must join exactly; fill gaps with a break.', row)
        tail = entries[-1]
        if session.state == 'closed':
            if session.ended_at is None or tail.ended_at != session.ended_at:
                fail('The closing marker must match the last row end.', tail)
        elif session.ended_at is not None or tail.ended_at is not None:
            fail('An active or unfinished session must have one open last row.', tail)
    known = sorted([r for r in rows if r.ended_at], key=lambda r: r.started_at)
    for previous, row in zip(known, known[1:]):
        if previous.ended_at > row.started_at:
            fail('Known intervals must not overlap other work.', row)
    # Unknown ends reserve no future span, but their start cannot sit inside known work.
    for row in rows:
        if row.ended_at is None and any(r.started_at <= row.started_at < r.ended_at for r in known):
            fail('An unfinished row cannot start inside known work.', row)
    starts = [r.started_at for r in rows]
    if len(starts) != len(set(starts)):
        fail('Two rows cannot start at the same instant.')


def new_row(sheet, session, at, task):
    return TimeEntry(timesheet=sheet, session=session, kind='task' if task else 'break', task_id=task, started_at=at)


def replace_day(actor, sheet, values, sessions, rows):
    day = values['date']
    start, end = bounds(day)
    original = {r.pk: r for r in rows if in_day(r, day)}
    affected = {r.session_id for r in original.values()}
    affected.update(s.pk for s in sessions.values() if s.ended_at and start < s.ended_at <= end)
    outside = [r for r in rows if r.pk not in original]
    incoming, seen_rows, seen_sessions, seen_keys = [], set(), set(), set()
    for draft in values['sessions']:
        sid = draft.get('id') or uuid4()
        if sid in seen_sessions or ('id' in draft and sid not in affected):
            fail('Session identifiers must belong to the selected day.')
        seen_sessions.add(sid)
        session = sessions.get(sid)
        retained = [r for r in outside if r.session_id == sid]
        before = any(r.started_at < start for r in retained)
        after = any(r.started_at >= end for r in retained)
        if session is None:
            session = WorkSession(pk=sid, timesheet=sheet, state=draft['state'])
            sessions[sid] = session
            if draft['state'] == 'active' and (day != date_of(timezone.now()) or any(s.pk != sid and s.state == 'active' for s in sessions.values())):
                fail('New historical sessions must be unfinished or closed.')
        elif draft['state'] == 'active' and session.state != 'active':
            fail('Use explicit continuation to activate an existing historical session.')
        if after and (draft['state'] != session.state or draft['ended_at'] is not None):
            fail('A neighboring day fixes this session lifecycle and closing marker.')
        selected = []
        for item in draft['rows']:
            if 'client_key' in item:
                if item['client_key'] in seen_keys:
                    fail('Client row keys must be unique within the draft.')
                seen_keys.add(item['client_key'])
            rid = item.get('id') or uuid4()
            if rid in seen_rows or ('id' in item and (rid not in original or original[rid].session_id != sid)):
                fail('Row identifiers must belong to this day and session.')
            seen_rows.add(rid)
            row = TimeEntry(pk=rid, timesheet=sheet, session=session, kind=item['kind'], task_id=item['task'], started_at=item['started_at'], ended_at=item['ended_at'])
            row._client_key = item.get('client_key', str(rid))
            if not start <= row.started_at < end or (row.ended_at and row.ended_at > end):
                fail('Draft rows must stay within the selected calendar day.', row)
            if row.task_id and (rid not in original or original[rid].task_id != row.task_id):
                select_task(actor, row.task_id)
            selected.append(row)
        selected.sort(key=lambda r: r.started_at)
        if not selected:
            fail('Omit an independent session to clear it; connected sessions need coverage.', session)
        if before and selected[0].started_at != start:
            fail('The incoming midnight connection is fixed.', selected[0])
        if after and selected[-1].ended_at != end:
            fail('The outgoing midnight connection is fixed.', selected[-1])
        if not before:
            session.started_at = selected[0].started_at
        if not after:
            if draft['ended_at'] is not None and not start < draft['ended_at'] <= end:
                fail('The closing marker must be on the selected day.', session)
            session.state, session.ended_at = draft['state'], draft['ended_at']
        incoming.extend(selected)
    for sid in affected - seen_sessions:
        if any(r.session_id == sid for r in outside):
            fail('Connected overnight coverage cannot be removed.')
        del sessions[sid]
    return outside + incoming


def plan(actor, sheet, values):
    sessions, rows = load(sheet)
    kind, day = values['command'], values['date']
    at = values.get('at')
    midnight_end = (kind == 'end_day' or (kind == 'boundary' and values.get('edge') == 'end')) and at == bounds(day)[1]
    if at is not None and date_of(at) != day and not midnight_end:
        fail('Supply a timestamp on the selected day.')
    current = day == date_of(timezone.now())
    if kind == 'replace_day':
        rows = replace_day(actor, sheet, values, sessions, rows)
    elif kind == 'start':
        if any(in_day(r, day) for r in rows):
            if any(s.state == 'closed' and s.ended_at and date_of(s.ended_at) == day for s in sessions.values()):
                raise DomainError('resume_confirmation_required', 'Convert the End of Working Day marker to a break before resuming.', 409)
            fail('Target the existing session to append or resume work on this day.')
        task = select_task(actor, values['task'], current=current)
        if current:
            for previous in sessions.values():
                if previous.state == 'active':
                    previous.state = 'unfinished'
        session = WorkSession(timesheet=sheet, started_at=at, state='active' if current else 'unfinished')
        sessions[session.pk] = session
        rows.append(new_row(sheet, session, at, task))
    elif kind in {'boundary', 'delete_last'}:
        row = next((r for r in rows if r.pk == values['entry'] and in_day(r, day)), None)
        if row is None:
            fail('Select a row on this day.')
        session = sessions[row.session_id]
        entries = sorted([r for r in rows if r.session_id == session.pk], key=lambda r: r.started_at)
        index = entries.index(row)
        if kind == 'delete_last':
            if index != len(entries) - 1:
                fail('Only the last session row can be deleted ordinarily.', row)
            if index and not in_day(entries[index - 1], day):
                fail('Use Edit day to preserve connected overnight coverage.', row)
            if index:
                entries[index - 1].ended_at = row.ended_at
            else:
                del sessions[session.pk]
            rows.remove(row)
        else:
            if values['edge'] == 'start':
                if index and date_of(entries[index - 1].started_at) != day:
                    fail('The incoming midnight connection is fixed.', row)
                row.started_at = at
                if index:
                    entries[index - 1].ended_at = at
                else:
                    session.started_at = at
            else:
                if row.ended_at is None:
                    fail('Close an unfinished tail with End of Working Day.', row)
                if index + 1 < len(entries):
                    if not in_day(entries[index + 1], day):
                        fail('The outgoing midnight connection is fixed.', row)
                    entries[index + 1].started_at = at
                else:
                    session.ended_at = at
                row.ended_at = at
    else:
        session = sessions.get(values['session'])
        if session is None:
            fail('Select a session in this timesheet.')
        entries = sorted([r for r in rows if r.session_id == session.pk], key=lambda r: r.started_at)
        if not entries:
            fail('The session has no records.')
        tail = entries[-1]
        if kind != 'continue' and not (kind == 'end_day' and session.state == 'active' and current) and not in_day(tail, day):
            fail('Target the day containing the unfinished tail or use explicit continuation.')
        if kind == 'resume':
            if session.state != 'closed':
                fail('Only a closed session can be resumed.')
            if at <= session.ended_at:
                fail('Resumption must follow the closing marker.')
            rows.append(TimeEntry(timesheet=sheet, session=session, kind='break', started_at=session.ended_at, ended_at=at))
            session.state = 'active' if current and not any(s.state == 'active' for s in sessions.values()) else 'unfinished'
            session.ended_at = None
        else:
            if session.state == 'closed':
                raise DomainError('resume_confirmation_required', 'Convert the End of Working Day marker to a break before resuming.', 409)
            if at <= tail.started_at:
                fail('The next boundary must follow the unfinished tail.', tail)
            tail.ended_at = at
        if kind == 'end_day':
            session.state, session.ended_at = 'closed', at
        else:
            if kind == 'continue':
                if not current:
                    fail('Explicit recording continuation targets today.')
                if any(s.pk != session.pk and s.state == 'active' for s in sessions.values()):
                    fail('Another session is actively recording; do not merge it implicitly.')
                session.state = 'active'
            task = None if kind == 'break' else select_task(actor, values['task'], current=current and session.state == 'active')
            rows.append(new_row(sheet, session, at, task))
    validate_timeline(sessions, rows)
    return sessions, normalize(rows)


def input_values(data):
    values = validated(CommandInput, data)
    kind = values['command']
    missing = REQUIRED[kind] - values.keys()
    allowed = REQUIRED[kind] | {'command', 'date', 'expected_revision', 'confirm', 'expected_domain_revision'}
    if missing or values.keys() - allowed:
        raise DomainError('invalid_input', 'Check fields required for this command.', fields={k: ['Missing or inappropriate field.'] for k in missing | (values.keys() - allowed)})
    return values


def prepare(actor, owner, data):
    actor = gate(actor, owner, write=True)
    values = input_values(data)
    sheet = Timesheet.objects.select_for_update().filter(user_id=owner).first()
    if sheet is None:
        raise DomainError('not_found', 'The timesheet is unavailable.', 404)
    if sheet.revision != values['expected_revision']:
        raise DomainError('stale_revision', 'The timesheet changed. Reload and review your changes.', 409)
    return actor, sheet, values


def safe_plan(actor, sheet, values):
    try:
        return plan(actor, sheet, values)
    except DomainError as exc:
        # Whole-sheet write does not authorize discovering stored row identifiers
        # through validation against a different day or session.
        if exc.code == 'invalid_timeline' and not can_timesheet(actor, sheet.user_id):
            exc.fields = {'timeline': [exc.message]}
        raise


def persist(sheet, sessions, rows):
    old_sessions, old_rows = load(sheet, normalized=False)
    fields = ('session_id', 'kind', 'task_id', 'started_at', 'ended_at')
    proposed = {r.pk: r for r in rows}
    changed = {r.pk for r in old_rows if r.pk not in proposed or any(getattr(r, f) != getattr(proposed[r.pk], f) for f in fields)}
    TimeEntry.objects.filter(timesheet=sheet, pk__in=changed).delete()
    # Remove the old active flag before activating another session.
    sheet.sessions.filter(state='active').exclude(pk__in=[s.pk for s in sessions.values() if s.state == 'active']).update(state='unfinished')
    for session in sessions.values():
        session.save()
    old_ids = {r.pk for r in old_rows}
    TimeEntry.objects.bulk_create([r for r in rows if r.pk in changed or r.pk not in old_ids])
    sheet.sessions.filter(pk__in=old_sessions.keys() - sessions.keys()).delete()
    sheet.revision += 1
    sheet.save(update_fields=['revision'])


@mutation
def command(actor, owner, data):
    actor, sheet, values = prepare(actor, owner, data)
    if values['command'] in PREVIEWED:
        if not values['confirm']:
            raise DomainError('confirmation_required', 'Preview and confirm the affected changes first.', 409)
        if values.get('expected_domain_revision') != MutationLock.objects.get(pk='domain').revision:
            raise DomainError('stale_preview', 'Access or data changed. Preview the changes again.', 409)
    sessions, rows = safe_plan(actor, sheet, values)
    persist(sheet, sessions, rows)
    return {'user': str(owner), 'revision': sheet.revision}


@transaction.atomic
def preview(actor, owner, data):
    lock = MutationLock.objects.select_for_update().get(pk='domain')
    actor, sheet, values = prepare(actor, owner, data)
    if values['command'] not in PREVIEWED:
        raise DomainError('invalid_input', 'This command does not use a preview.')
    sessions, rows = safe_plan(actor, sheet, values)
    result = {'user': str(owner), 'revision': sheet.revision, 'domain_revision': lock.revision,
              'advice': 'Convert the closing marker to a break.' if values['command'] == 'resume' else 'Review the affected boundaries.'}
    if can_timesheet(actor, owner):
        old_sessions, old_rows = load(sheet)
        result['before'] = day_data(actor, sheet, values['date'], old_sessions, old_rows)
        result['after'] = day_data(actor, sheet, values['date'], sessions, rows)
    return result


@transaction.atomic
def read_day(actor, owner, day):
    # Coordinate the multi-query response with all domain writers.
    MutationLock.objects.select_for_update().get(pk='domain')
    actor = gate(actor, owner)
    sheet = find(Timesheet, owner)
    sessions, rows = load(sheet)
    return day_data(actor, sheet, day, sessions, rows)
