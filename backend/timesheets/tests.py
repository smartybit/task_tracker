from copy import deepcopy
from datetime import date, datetime, timezone as dtzone
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
import time

from django.db import IntegrityError, close_old_connections, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase, override_settings
from rest_framework.test import APIClient

from access.models import ProjectGrant
from access.services import replace_grant
from core.domain import DomainError
from core.models import MutationLock
from tasks.models import Task
from tasks.tests import TaskFixtures, PASSWORD, User
from timesheets.models import TimeEntry, Timesheet, WorkSession
from timesheets.services import command, preview, read_day


def stamp(value):
    return datetime.fromisoformat(value).replace(tzinfo=dtzone.utc)


class TimesheetFixtures(TaskFixtures):
    def setup_time(self):
        self.setup_tasks()
        self.task = self.create('Meeting')
        self.task2 = self.create('Email', project=self.other)
        self.clock = patch('timesheets.services.timezone.now', return_value=stamp('2026-10-09T12:00'))
        self.clock.start()
        self.addCleanup(lambda: self.clock.stop())

    def now(self, at):
        self.clock.stop()
        self.clock = patch('timesheets.services.timezone.now', return_value=stamp(at))
        self.clock.start()

    def sheet(self, owner=None):
        return Timesheet.objects.get(user=owner or self.alice)

    def send(self, kind, at=None, *, actor=None, owner=None, day=None, **extra):
        owner = owner or self.alice
        data = {'command': kind, 'date': day or at[:10], 'expected_revision': self.sheet(owner).revision, **extra}
        if at:
            data['at'] = at + 'Z' if '+' not in at and not at.endswith('Z') else at
        return command(actor or self.alice, owner.pk, data)

    def start(self, at='2026-10-09T09:00', task=None):
        self.send('start', at, task=str((task or self.task).pk))
        return WorkSession.objects.get(timesheet=self.sheet(), started_at=stamp(at))

    def day(self, day='2026-10-09', actor=None, owner=None):
        return read_day(actor or self.alice, (owner or self.alice).pk, date.fromisoformat(day))

    def draft(self, day='2026-10-09'):
        # Submit only the editable contract, not labels or derived connection flags.
        return [{'id': s['id'], 'state': s['state'], 'ended_at': s['ended_at'],
                 'rows': [{k: r[k] for k in ('id', 'kind', 'task', 'started_at', 'ended_at')} for r in s['rows']]}
                for s in self.day(day)['sessions']]

    def confirmed(self, kind, day='2026-10-09', **extra):
        data = dict(command=kind, date=day, expected_revision=self.sheet().revision, **extra)
        result = preview(self.alice, self.alice.pk, data)
        return command(self.alice, self.alice.pk, {**data, 'confirm': True, 'expected_domain_revision': result['domain_revision']})

    def snapshot(self):
        return (list(WorkSession.objects.order_by('id').values()), list(TimeEntry.objects.order_by('id').values()),
                list(Timesheet.objects.order_by('user_id').values()), MutationLock.objects.get(pk='domain').revision)


class Stage5Tests(TimesheetFixtures, TestCase):
    def setUp(self):
        self.setup_time()

    def test_friday_to_monday_and_multiple_unfinished_days(self):
        friday = self.start()
        self.send('break', '2026-10-09T12:00', session=str(friday.pk))
        self.send('append', '2026-10-09T12:43', session=str(friday.pk), task=str(self.task2.pk))
        self.now('2026-10-12T09:00')
        monday = self.start('2026-10-12T09:00')
        before = list(TimeEntry.objects.filter(session=monday).values())
        self.assertEqual(self.day()['work_seconds'], 3 * 3600)
        friday.refresh_from_db()
        self.assertEqual(friday.state, 'unfinished')
        self.send('append', '2026-10-09T14:00', session=str(friday.pk), task=str(self.task.pk))
        self.send('end_day', '2026-10-09T17:00', session=str(friday.pk))
        self.assertEqual(self.day()['work_seconds'], 7 * 3600 + 17 * 60)
        self.assertEqual(list(TimeEntry.objects.filter(session=monday).values()), before)
        monday.refresh_from_db()
        self.assertEqual(monday.state, 'active')
        self.now('2026-10-13T09:00')
        tuesday = self.start('2026-10-13T09:00')
        self.now('2026-10-14T09:00')
        self.start('2026-10-14T09:00')
        self.assertEqual(WorkSession.objects.filter(state='unfinished').count(), 2)
        self.assertEqual(TimeEntry.objects.filter(ended_at=None).count(), 3)
        self.assertIsNone(TimeEntry.objects.get(session=tuesday).ended_at)

    def test_switch_break_end_and_nonpositive_rollback(self):
        session = self.start()
        self.assertEqual(self.day()['work_seconds'], 0)
        self.send('switch', '2026-10-09T10:00', session=str(session.pk), task=str(self.task2.pk))
        before = self.snapshot()
        with self.assertRaises(DomainError):
            self.send('break', '2026-10-09T10:00', session=str(session.pk))
        self.assertEqual(self.snapshot(), before)
        self.send('break', '2026-10-09T11:00', session=str(session.pk))
        self.send('end_day', '2026-10-09T12:00', session=str(session.pk))
        self.assertEqual(self.day()['work_seconds'], 7200)
        self.assertFalse(self.day()['unfinished'])
        self.assertEqual(self.day()['sessions'][0]['ended_at'], '2026-10-09T12:00:00+00:00')

    def test_durations_preserve_subsecond_precision_before_totalling(self):
        session = self.start('2026-10-09T09:00:00')
        self.send('switch', '2026-10-09T09:00:00.100000', session=str(session.pk), task=str(self.task2.pk))
        self.send('end_day', '2026-10-09T09:00:00.300000', session=str(session.pk))
        self.assertEqual(self.day()['work_seconds'], 0.3)
        self.assertEqual([r['duration_seconds'] for r in self.day()['sessions'][0]['rows']], [0.1, 0.2])

    def test_unknown_end_not_infinite_but_closure_cannot_overlap(self):
        friday = self.start()
        self.now('2026-10-12T09:00')
        monday = self.start('2026-10-12T09:00')
        self.send('end_day', '2026-10-12T10:00', session=str(monday.pk))
        before = self.snapshot()
        with self.assertRaises(DomainError):
            self.send('continue', '2026-10-12T11:00', session=str(friday.pk), task=str(self.task.pk))
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.day()['work_seconds'], 0)

    def test_overnight_closure_splits_known_work_only(self):
        self.now('2026-10-09T23:00')
        session = self.start('2026-10-09T23:00')
        self.now('2026-10-10T01:00')
        self.assertEqual(TimeEntry.objects.count(), 1)
        self.assertEqual(self.day()['work_seconds'], 0)
        self.send('end_day', '2026-10-10T01:00', session=str(session.pk))
        self.assertEqual(TimeEntry.objects.count(), 2)
        self.assertEqual(self.day()['work_seconds'], 3600)
        self.assertEqual(self.day('2026-10-10')['work_seconds'], 3600)
        self.assertTrue(self.day()['sessions'][0]['continues_after'])
        self.assertTrue(self.day('2026-10-10')['sessions'][0]['continues_before'])

    @override_settings(TIME_ZONE='Europe/Berlin')
    def test_midnight_uses_configured_shared_zone(self):
        self.now('2026-10-09T21:00')
        session = self.start('2026-10-09T21:00')  # 23:00 local
        self.now('2026-10-10T00:00')
        self.send('end_day', '2026-10-10T00:00', session=str(session.pk))
        self.assertEqual(self.day()['work_seconds'], 3600)
        self.assertEqual(self.day('2026-10-10')['work_seconds'], 7200)
        self.assertEqual(TimeEntry.objects.order_by('started_at').first().ended_at, stamp('2026-10-09T22:00'))
        self.assertEqual(self.day()['time_zone'], 'Europe/Berlin')

    def test_explicit_continuation_and_new_day_default(self):
        session = self.start('2026-10-09T23:00')
        self.now('2026-10-10T01:00')
        self.send('continue', '2026-10-10T01:00', session=str(session.pk), task=str(self.task2.pk))
        self.assertEqual(WorkSession.objects.count(), 1)
        self.assertEqual(self.day()['work_seconds'], 3600)
        self.assertEqual(self.day('2026-10-10')['work_seconds'], 3600)
        self.assertIsNone(TimeEntry.objects.order_by('started_at').last().ended_at)
        self.now('2026-10-11T09:00')
        self.start('2026-10-11T09:00')
        before = self.snapshot()
        with self.assertRaises(DomainError):
            self.send('continue', '2026-10-11T10:00', session=str(session.pk), task=str(self.task.pk))
        self.assertEqual(self.snapshot(), before)

    def test_zone_change_reallocates_existing_spans_and_keeps_drafts_stable(self):
        session = self.start('2026-10-09T21:00')
        self.send('end_day', '2026-10-10T00:00', day='2026-10-09', session=str(session.pk))
        stored = self.snapshot()
        with override_settings(TIME_ZONE='Europe/Berlin'):
            self.assertEqual(self.day()['work_seconds'], 3600)
            self.assertEqual(self.day('2026-10-10')['work_seconds'], 7200)
            draft = self.draft()
            self.assertEqual(self.draft(), draft)
            self.assertEqual(self.snapshot(), stored)
            draft[0]['rows'][0].update(kind='break', task=None)
            self.send('replace_day', day='2026-10-09', sessions=draft)
            self.assertEqual(self.day()['work_seconds'], 0)
            self.assertEqual(self.day('2026-10-10')['work_seconds'], 7200)
            self.assertEqual(TimeEntry.objects.count(), 2)

    def test_resume_requires_advice_confirmation_and_fills_break(self):
        session = self.start()
        self.send('end_day', '2026-10-09T17:00', session=str(session.pk))
        before = self.snapshot()
        with self.assertRaises(DomainError) as error:
            self.send('append', '2026-10-09T18:00', session=str(session.pk), task=str(self.task.pk))
        self.assertEqual(error.exception.code, 'resume_confirmation_required')
        data = dict(command='resume', date='2026-10-09', expected_revision=self.sheet().revision,
                    session=str(session.pk), at='2026-10-09T18:00Z', task=str(self.task2.pk))
        planned = preview(self.alice, self.alice.pk, data)
        self.assertIn('break', planned['advice'])
        self.assertEqual(self.snapshot(), before)
        command(self.alice, self.alice.pk, {**data, 'confirm': True, 'expected_domain_revision': planned['domain_revision']})
        self.assertEqual(self.day()['work_seconds'], 8 * 3600)
        filler = TimeEntry.objects.get(kind='break')
        self.assertEqual((filler.ended_at - filler.started_at).total_seconds(), 3600)

    def test_boundary_preview_shared_edges_staleness_and_rollback(self):
        session = self.start()
        self.send('switch', '2026-10-09T10:00', session=str(session.pk), task=str(self.task2.pk))
        self.send('end_day', '2026-10-09T11:00', session=str(session.pk))
        row = TimeEntry.objects.order_by('started_at').first()
        data = dict(command='boundary', date='2026-10-09', expected_revision=self.sheet().revision,
                    entry=str(row.pk), edge='end', at='2026-10-09T10:30Z')
        before = self.snapshot()
        result = preview(self.alice, self.alice.pk, data)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(result['after']['sessions'][0]['rows'][1]['started_at'], '2026-10-09T10:30:00+00:00')
        with self.assertRaises(DomainError):
            command(self.alice, self.alice.pk, data)
        MutationLock.objects.filter(pk='domain').update(revision=result['domain_revision'] + 1)
        with self.assertRaises(DomainError) as error:
            command(self.alice, self.alice.pk, {**data, 'confirm': True, 'expected_domain_revision': result['domain_revision']})
        self.assertEqual(error.exception.code, 'stale_preview')
        self.confirmed('boundary', entry=str(row.pk), edge='end', at='2026-10-09T10:30Z')
        self.assertEqual(self.day()['work_seconds'], 7200)
        before = self.snapshot()
        with self.assertRaises(DomainError):
            self.confirmed('boundary', entry=str(row.pk), edge='end', at='2026-10-09T11:30Z')
        self.assertEqual(self.snapshot(), before)

    def test_delete_last_open_closed_and_sole_session(self):
        session = self.start()
        first = TimeEntry.objects.get()
        self.send('switch', '2026-10-09T10:00', session=str(session.pk), task=str(self.task2.pk))
        tail = TimeEntry.objects.order_by('started_at').last()
        with self.assertRaises(DomainError):
            self.confirmed('delete_last', entry=str(first.pk))
        self.confirmed('delete_last', entry=str(tail.pk))
        first.refresh_from_db()
        self.assertIsNone(first.ended_at)
        self.send('switch', '2026-10-09T10:00', session=str(session.pk), task=str(self.task2.pk))
        self.send('end_day', '2026-10-09T11:00', session=str(session.pk))
        self.confirmed('delete_last', entry=str(TimeEntry.objects.order_by('started_at').last().pk))
        first.refresh_from_db()
        self.assertEqual(first.ended_at, stamp('2026-10-09T11:00'))
        self.confirmed('delete_last', entry=str(first.pk))
        self.assertFalse(WorkSession.objects.exists())
        self.assertEqual(self.day()['sessions'], [])

    def test_replace_day_arbitrary_rows_no_automatic_repair_and_stable_ids(self):
        session = self.start()
        self.send('end_day', '2026-10-09T12:00', session=str(session.pk))
        draft = self.draft()
        first = draft[0]['rows'][0]
        first['ended_at'] = '2026-10-09T10:00Z'
        middle = dict(client_key='new-break', kind='break', task=None, started_at='2026-10-09T10:15Z', ended_at='2026-10-09T11:00Z')
        last = dict(client_key='new-task', kind='task', task=str(self.task2.pk), started_at='2026-10-09T11:00Z', ended_at='2026-10-09T12:00Z')
        draft[0]['rows'] += [middle, last]
        before = self.snapshot()
        with self.assertRaises(DomainError) as error:
            self.send('replace_day', day='2026-10-09', sessions=draft)
        self.assertIn(first['id'], error.exception.fields)
        self.assertEqual(self.snapshot(), before)
        middle['started_at'] = '2026-10-09T10:00Z'
        self.send('replace_day', day='2026-10-09', sessions=draft)
        self.assertTrue(TimeEntry.objects.filter(pk=first['id']).exists())
        self.assertEqual(self.day()['work_seconds'], 7200)
        # Deleting a middle row does not silently extend another row.
        draft = self.draft()
        del draft[0]['rows'][1]
        before = self.snapshot()
        with self.assertRaises(DomainError):
            self.send('replace_day', day='2026-10-09', sessions=draft)
        self.assertEqual(self.snapshot(), before)
        draft[0]['rows'][0]['ended_at'] = draft[0]['rows'][1]['started_at']
        self.send('replace_day', day='2026-10-09', sessions=draft)
        self.assertEqual(self.day()['work_seconds'], 10800)

    def test_replace_independent_edges_empty_and_unfinished(self):
        self.start()
        draft = self.draft()
        draft[0]['rows'][0]['started_at'] = '2026-10-09T08:00Z'
        self.send('replace_day', day='2026-10-09', sessions=draft)
        self.assertEqual(WorkSession.objects.get().started_at, stamp('2026-10-09T08:00'))
        self.assertEqual(self.day()['work_seconds'], 0)
        self.send('replace_day', day='2026-10-09', sessions=[])
        self.assertFalse(WorkSession.objects.exists())
        self.send('replace_day', day='2026-10-09', sessions=[dict(client_key='session-new', state='unfinished', ended_at=None,
            rows=[dict(client_key='new', kind='task', task=str(self.task.pk), started_at='2026-10-09T09:00Z', ended_at=None)])])
        self.assertEqual(WorkSession.objects.get().state, 'unfinished')

    def test_historical_draft_preserves_monday_identity_and_rejects_stale_save(self):
        self.start()
        draft = self.draft()
        revision = self.sheet().revision
        self.now('2026-10-12T09:00')
        monday = self.start('2026-10-12T09:00')
        before = self.snapshot()
        with self.assertRaises(DomainError) as error:
            command(self.alice, self.alice.pk, dict(command='replace_day', date='2026-10-09', expected_revision=revision, sessions=draft))
        self.assertEqual(error.exception.code, 'stale_revision')
        self.assertEqual(self.snapshot(), before)
        monday_before = list(TimeEntry.objects.filter(session=monday).values())
        draft = self.draft()
        draft[0]['rows'][0]['ended_at'] = '2026-10-09T17:00Z'
        draft[0].update(state='closed', ended_at='2026-10-09T17:00Z')
        self.send('replace_day', day='2026-10-09', sessions=draft)
        self.assertEqual(list(TimeEntry.objects.filter(session=monday).values()), monday_before)
        self.assertEqual(WorkSession.objects.get(state='active').pk, monday.pk)

    def test_historical_last_deletion_and_storage_failure_preserve_current_work(self):
        friday = self.start()
        first = TimeEntry.objects.get()
        self.send('switch', '2026-10-09T10:00', session=str(friday.pk), task=str(self.task2.pk))
        tail = TimeEntry.objects.order_by('started_at').last()
        self.now('2026-10-12T09:00')
        monday = self.start('2026-10-12T09:00')
        monday_rows = list(TimeEntry.objects.filter(session=monday).values())
        self.confirmed('delete_last', entry=str(tail.pk))
        first.refresh_from_db()
        self.assertIsNone(first.ended_at)
        self.assertEqual(WorkSession.objects.get(pk=friday.pk).state, 'unfinished')
        self.assertEqual(list(TimeEntry.objects.filter(session=monday).values()), monday_rows)
        draft = self.draft()
        draft[0]['rows'][0]['started_at'] = '2026-10-09T08:00Z'
        before = self.snapshot()
        with patch('timesheets.services.TimeEntry.objects.bulk_create', side_effect=IntegrityError('storage failure')):
            with self.assertRaises(DomainError) as error:
                self.send('replace_day', day='2026-10-09', sessions=draft)
        self.assertEqual(error.exception.code, 'conflict')
        self.assertEqual(self.snapshot(), before)

    def test_fixed_midnight_connections_cannot_be_removed_or_shifted(self):
        session = self.start('2026-10-09T23:00')
        self.now('2026-10-10T02:00')
        self.send('end_day', '2026-10-10T02:00', session=str(session.pk))
        before = self.snapshot()
        for day in ['2026-10-09', '2026-10-10']:
            with self.assertRaises(DomainError):
                self.send('replace_day', day=day, sessions=[])
            draft = self.draft(day)
            if day.endswith('09'):
                draft[0]['rows'][-1]['ended_at'] = '2026-10-09T23:59Z'
            else:
                draft[0]['rows'][0]['started_at'] = '2026-10-10T00:01Z'
            with self.assertRaises(DomainError):
                self.send('replace_day', day=day, sessions=draft)
            self.assertEqual(self.snapshot(), before)
        draft = self.draft()
        draft[0]['rows'][0].update(kind='break', task=None)
        self.send('replace_day', day='2026-10-09', sessions=draft)
        self.assertEqual(self.day()['work_seconds'], 0)
        self.assertEqual(self.day('2026-10-10')['work_seconds'], 7200)

    def test_restricted_references_retained_new_selection_requires_read_and_final_rules(self):
        final = self.create('Historical final', status=self.final)
        before = self.snapshot()
        with self.assertRaises(DomainError) as error:
            self.start(task=final)
        self.assertEqual(error.exception.code, 'task_reopen_required')
        self.assertEqual(self.snapshot(), before)
        self.start()
        replace_grant(self.admin, self.alice.pk, 'projects', self.project.pk, {})
        draft = self.draft()
        self.assertEqual(self.day()['sessions'][0]['rows'][0]['task_label'], 'Meeting')
        self.assertFalse(self.day()['sessions'][0]['rows'][0]['task_readable'])
        self.send('replace_day', day='2026-10-09', sessions=draft)
        draft[0]['rows'][0]['task'] = str(final.pk)
        with self.assertRaises(DomainError) as error:
            self.send('replace_day', day='2026-10-09', sessions=draft)
        self.assertEqual(error.exception.code, 'permission_denied')
        replace_grant(self.admin, self.alice.pk, 'projects', self.project.pk, {'task_read': True})
        self.now('2026-10-12T09:00')
        session = WorkSession.objects.get()
        self.send('append', '2026-10-09T10:00', session=str(session.pk), task=str(final.pk))
        self.send('end_day', '2026-10-09T11:00', session=str(session.pk))
        final.refresh_from_db()
        self.assertTrue(final.status.final)
        self.assertEqual(final.history.count(), 1)

    def test_replace_identifiers_and_row_errors(self):
        self.start()
        draft = self.draft()
        original = deepcopy(draft)
        draft[0]['rows'][0].update(kind='break', task=str(self.task.pk))
        with self.assertRaises(DomainError) as error:
            self.send('replace_day', day='2026-10-09', sessions=draft)
        self.assertIn(draft[0]['rows'][0]['id'], error.exception.fields)
        draft = original
        draft[0]['rows'].append(deepcopy(draft[0]['rows'][0]))
        with self.assertRaises(DomainError):
            self.send('replace_day', day='2026-10-09', sessions=draft)
        with self.assertRaises(DomainError):
            self.send('replace_day', day='2026-10-12', sessions=original)

    def test_endpoint_permissions_all_flag_combinations_no_admin_bypass(self):
        session = self.start()
        self.send('switch', '2026-10-09T10:00', session=str(session.pk), task=str(self.task2.pk))
        client = APIClient()
        day_path = f'/api/v1/timesheets/{self.alice.pk}/days/2026-10-09/'
        cmd_path = f'/api/v1/timesheets/{self.alice.pk}/commands/'
        row = TimeEntry.objects.order_by('started_at').first()
        for read in [False, True]:
            for write in [False, True]:
                User.objects.filter(pk=self.admin.pk).update(read_others_timesheets=read, write_others_timesheets=write)
                client.force_authenticate(self.admin)
                result = client.get(day_path)
                self.assertEqual(result.status_code, 200 if read else 403)
                if read:
                    self.assertEqual(len(result.data['sessions'][0]['rows']), 2)
                    self.assertNotIn('description', str(result.data))
                data = dict(command='boundary', date='2026-10-09', expected_revision=self.sheet().revision,
                            entry=str(row.pk), edge='end', at='2026-10-09T10:15Z')
                planned = client.post(cmd_path + 'preview/', data, format='json')
                self.assertEqual(planned.status_code, 200 if write else 403)
                if write:
                    self.assertEqual('before' in planned.data, read)
                    failed = client.post(cmd_path + 'preview/', {**data, 'at': '2026-10-09T09:00Z'}, format='json')
                    self.assertEqual(failed.status_code, 400)
                    if not read:
                        self.assertEqual(set(failed.data['fields']), {'timeline'})
                        self.assertNotIn(str(row.pk), str(failed.data))
                    result = client.post(cmd_path, {**data, 'confirm': True, 'expected_domain_revision': planned.data['domain_revision']}, format='json')
                    self.assertEqual(result.status_code, 200, result.data)
                    self.assertEqual(set(result.data), {'user', 'revision'})
        client.force_authenticate(self.alice)
        self.assertEqual(client.get(day_path).status_code, 200)
        client.force_authenticate(self.bob)
        self.assertEqual(client.get(day_path).status_code, 403)

    def test_real_session_csrf_strict_fields_and_unsupported_middle_commands(self):
        client = APIClient(enforce_csrf_checks=True)
        token = client.get('/api/v1/auth/csrf/').data['csrf_token']
        response = client.post('/api/v1/auth/login/', dict(email=self.alice.email, password=PASSWORD), format='json', HTTP_X_CSRFTOKEN=token)
        path = f'/api/v1/timesheets/{self.alice.pk}/commands/'
        data = dict(command='start', date='2026-10-09', at='2026-10-09T09:00Z', task=str(self.task.pk), expected_revision=0)
        self.assertEqual(client.post(path, data, format='json').status_code, 403)
        client.credentials(HTTP_X_CSRFTOKEN=response.data['csrf_token'])
        self.assertEqual(client.post(path, {**data, 'duration': 10}, format='json').status_code, 400)
        self.assertEqual(client.post(path, {**data, 'command': 'insert'}, format='json').status_code, 400)
        self.assertEqual(client.post(path, data, format='json').status_code, 200)
        self.assertEqual(client.get(f'/api/v1/timesheets/{self.alice.pk}/days/invalid/').status_code, 400)

    def test_database_overlap_uniqueness_and_session_agreement(self):
        session = self.start()
        self.send('end_day', '2026-10-09T11:00', session=str(session.pk))
        other_session = WorkSession.objects.create(timesheet=self.sheet(), started_at=stamp('2026-10-09T10:00'), state='unfinished')
        with self.assertRaises(IntegrityError), transaction.atomic():
            TimeEntry.objects.create(timesheet=self.sheet(), session=other_session, kind='break', started_at=stamp('2026-10-09T10:00'), ended_at=stamp('2026-10-09T12:00'))
        # Unknown tails are not unbounded exclusion ranges.
        TimeEntry.objects.create(timesheet=self.sheet(), session=other_session, kind='break', started_at=stamp('2026-10-09T12:00'))
        with self.assertRaises(IntegrityError), transaction.atomic():
            TimeEntry.objects.create(timesheet=self.sheet(), session=other_session, kind='break', started_at=stamp('2026-10-09T13:00'))
        with self.assertRaises(IntegrityError), transaction.atomic():
            TimeEntry.objects.create(timesheet=self.sheet(self.bob), session=other_session, kind='break', started_at=stamp('2026-10-09T14:00'), ended_at=stamp('2026-10-09T15:00'))
        with self.assertRaises(IntegrityError), transaction.atomic():
            WorkSession.objects.filter(pk=other_session.pk).update(timesheet=self.sheet(self.bob))
        WorkSession.objects.create(timesheet=self.sheet(), started_at=stamp('2026-10-10T09:00'))
        with self.assertRaises(IntegrityError), transaction.atomic():
            WorkSession.objects.create(timesheet=self.sheet(), started_at=stamp('2026-10-11T09:00'))


class ConcurrentTimesheetTests(TimesheetFixtures, TransactionTestCase):
    def setUp(self):
        MutationLock.objects.get_or_create(pk='domain')
        self.setup_time()

    def worker(self, fn):
        close_old_connections()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET lock_timeout = '6s'")
            fn()
            return 'committed'
        except DomainError as exc:
            return exc.code
        finally:
            close_old_connections()

    def race(self, *operations):
        barrier = Barrier(len(operations))
        def run(fn):
            barrier.wait(timeout=5)
            return self.worker(fn)
        with ThreadPoolExecutor(max_workers=len(operations)) as pool:
            futures = [pool.submit(run, fn) for fn in operations]
            return [f.result(timeout=15) for f in futures]

    def test_two_current_starts_share_revision_one_commits(self):
        data = dict(command='start', date='2026-10-09', at='2026-10-09T09:00Z', task=str(self.task.pk), expected_revision=0)
        results = self.race(*(lambda: command(self.alice, self.alice.pk, data) for _ in range(2)))
        self.assertCountEqual(results, ['committed', 'stale_revision'])
        self.assertEqual(WorkSession.objects.filter(state='active').count(), 1)
        self.assertEqual(TimeEntry.objects.count(), 1)
        self.assertEqual(self.sheet().revision, 1)

    def test_friday_day_save_races_monday_switch(self):
        self.start()
        self.now('2026-10-12T09:00')
        monday = self.start('2026-10-12T09:00')
        revision = self.sheet().revision
        draft = self.draft()
        draft[0]['state'] = 'closed'
        draft[0]['ended_at'] = draft[0]['rows'][0]['ended_at'] = '2026-10-09T17:00Z'
        save = dict(command='replace_day', date='2026-10-09', expected_revision=revision, sessions=draft)
        switch = dict(command='switch', date='2026-10-12', expected_revision=revision, session=str(monday.pk), at='2026-10-12T10:00Z', task=str(self.task2.pk))
        results = self.race(lambda: command(self.alice, self.alice.pk, save), lambda: command(self.alice, self.alice.pk, switch))
        self.assertCountEqual(results, ['committed', 'stale_revision'])
        self.assertEqual(WorkSession.objects.get(state='active').pk, monday.pk)
        self.assertEqual(self.sheet().revision, revision + 1)
        self.assertEqual(TimeEntry.objects.filter(session=monday, ended_at=None).count(), 1)
        self.assertEqual(self.day()['work_seconds'], 8 * 3600 if results[0] == 'committed' else 0)

    def test_two_day_saves_commit_one_complete_draft(self):
        self.start()
        first = self.draft()
        first[0]['state'] = 'closed'
        first[0]['ended_at'] = first[0]['rows'][0]['ended_at'] = '2026-10-09T17:00Z'
        second = deepcopy(first)
        second[0]['rows'][0]['started_at'] = '2026-10-09T10:00Z'
        second[0]['rows'][0]['task'] = str(self.task2.pk)
        revision = self.sheet().revision
        def save(draft):
            return lambda: command(self.alice, self.alice.pk, dict(command='replace_day', date='2026-10-09', expected_revision=revision, sessions=draft))
        results = self.race(save(first), save(second))
        self.assertCountEqual(results, ['committed', 'stale_revision'])
        row = TimeEntry.objects.get()
        if results[0] == 'committed':
            self.assertEqual((row.started_at, row.task_id), (stamp('2026-10-09T09:00'), self.task.pk))
        else:
            self.assertEqual((row.started_at, row.task_id), (stamp('2026-10-09T10:00'), self.task2.pk))
        self.assertEqual(WorkSession.objects.get().started_at, row.started_at)
        self.assertEqual(row.ended_at, stamp('2026-10-09T17:00'))

    def test_append_races_boundary_preview_one_revision_wins(self):
        session = self.start()
        self.send('switch', '2026-10-09T10:00', session=str(session.pk), task=str(self.task2.pk))
        first = TimeEntry.objects.order_by('started_at').first()
        revision = self.sheet().revision
        boundary = dict(command='boundary', date='2026-10-09', expected_revision=revision, entry=str(first.pk), edge='end', at='2026-10-09T10:15Z')
        p = preview(self.alice, self.alice.pk, boundary)
        boundary.update(confirm=True, expected_domain_revision=p['domain_revision'])
        append = dict(command='append', date='2026-10-09', expected_revision=revision, session=str(session.pk), at='2026-10-09T11:00Z', task=str(self.task.pk))
        results = self.race(lambda: command(self.alice, self.alice.pk, boundary), lambda: command(self.alice, self.alice.pk, append))
        self.assertCountEqual(results, ['committed', 'stale_revision'])
        rows = list(TimeEntry.objects.order_by('started_at'))
        self.assertTrue(all(a.ended_at == b.started_at for a, b in zip(rows, rows[1:])))
        self.assertIsNone(rows[-1].ended_at)

    def test_waiting_writer_rechecks_timesheet_flag_revocation(self):
        User.objects.filter(pk=self.bob.pk).update(write_others_timesheets=True)
        data = dict(command='start', date='2026-10-09', at='2026-10-09T09:00Z', task=str(self.task.pk), expected_revision=0)
        with ThreadPoolExecutor(max_workers=1) as pool:
            with transaction.atomic():
                MutationLock.objects.select_for_update().get(pk='domain')
                User.objects.filter(pk=self.bob.pk).update(write_others_timesheets=False)
                def waiting():
                    with connection.cursor() as cursor:
                        cursor.execute("SET application_name = 'stage5_waiting_writer'")
                    command(self.bob, self.alice.pk, data)
                future = pool.submit(self.worker, waiting)
                deadline = time.monotonic() + 5
                while True:
                    with connection.cursor() as cursor:
                        cursor.execute('SELECT pg_stat_clear_snapshot()')
                        cursor.execute("SELECT count(*) FROM pg_stat_activity WHERE application_name='stage5_waiting_writer' AND wait_event_type='Lock'")
                        if cursor.fetchone()[0]:
                            break
                    self.assertLess(time.monotonic(), deadline, 'Writer did not wait on domain lock')
                    time.sleep(0.02)
            self.assertEqual(future.result(timeout=8), 'permission_denied')
        self.assertFalse(TimeEntry.objects.exists())
        self.assertEqual(self.sheet().revision, 0)

    def test_recording_races_task_deletion_uses_real_command(self):
        from tasks.services import change_task
        domain = MutationLock.objects.get(pk='domain').revision
        data = dict(command='start', date='2026-10-09', at='2026-10-09T09:00Z', task=str(self.task.pk), expected_revision=0)
        delete = dict(expected_revision=0, expected_domain_revision=domain, confirm=True)
        results = self.race(lambda: command(self.alice, self.alice.pk, data),
                            lambda: change_task(self.alice, 'delete', delete, self.task.pk))
        self.assertEqual(results.count('committed'), 1)
        self.assertEqual(Task.objects.filter(pk=self.task.pk).exists(), TimeEntry.objects.exists())


class Stage5UpgradeTests(TransactionTestCase):
    def test_stage4_upgrade_preserves_open_closed_entries_ids_and_revisions(self):
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        old = [node for node in latest if node[0] != 'timesheets'] + [('timesheets', '0003_worksession_timeentry_and_more')]
        try:
            executor.migrate(old)
            apps = MigrationExecutor(connection).loader.project_state(old).apps
            OldUser = apps.get_model('accounts', 'User')
            OldSheet = apps.get_model('timesheets', 'Timesheet')
            OldSession = apps.get_model('timesheets', 'WorkSession')
            OldEntry = apps.get_model('timesheets', 'TimeEntry')
            user = OldUser.objects.create(email='timesheet-upgrade@example.test', password='existing-hash')
            sheet = OldSheet.objects.create(user=user, revision=13)
            closed = OldSession.objects.create(timesheet=sheet, started_at=stamp('2026-10-08T09:00'), ended_at=stamp('2026-10-08T10:00'))
            finished = OldEntry.objects.create(timesheet=sheet, session=closed, kind='break', started_at=closed.started_at, ended_at=closed.ended_at)
            opened = OldSession.objects.create(timesheet=sheet, started_at=stamp('2026-10-09T09:00'))
            tail = OldEntry.objects.create(timesheet=sheet, session=opened, kind='break', started_at=opened.started_at)
            MigrationExecutor(connection).migrate(latest)
            self.assertEqual(Timesheet.objects.get(pk=user.pk).revision, 13)
            self.assertEqual(WorkSession.objects.get(pk=closed.pk).state, 'closed')
            self.assertEqual(WorkSession.objects.get(pk=opened.pk).state, 'active')
            self.assertEqual(TimeEntry.objects.get(pk=finished.pk).ended_at, finished.ended_at)
            self.assertIsNone(TimeEntry.objects.get(pk=tail.pk).ended_at)
            WorkSession.objects.filter(pk=opened.pk).update(state='unfinished')
            new = WorkSession.objects.create(timesheet_id=user.pk, started_at=stamp('2026-10-12T09:00'))
            TimeEntry.objects.create(timesheet_id=user.pk, session=new, kind='break', started_at=new.started_at)
            self.assertEqual(TimeEntry.objects.filter(ended_at=None).count(), 2)
            with connection.cursor() as cursor:
                cursor.execute("SELECT conname FROM pg_constraint WHERE conrelid IN ('timesheets_timeentry'::regclass, 'timesheets_worksession'::regclass)")
                names = {row[0] for row in cursor.fetchall()}
            self.assertNotIn('one_running_entry', names)
            self.assertNotIn('one_running_session', names)
            self.assertIn('known_entries_do_not_overlap', names)
        finally:
            MigrationExecutor(connection).migrate(latest)
