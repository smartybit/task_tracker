import csv
import itertools
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from io import StringIO
from threading import Event
from unittest.mock import patch
from uuid import uuid4

from django.db import close_old_connections, connection, transaction
from django.http import QueryDict
from django.test import TransactionTestCase, override_settings
from rest_framework.test import APIClient

from access.models import OrganizationGrant, ProjectGrant
from access.services import replace_grant
from core.models import MutationLock
from reports import services
from tasks.tests import TaskFixtures, PASSWORD, User
from timesheets.models import TimeEntry, Timesheet, WorkSession
from timesheets.services import command, read_day
from timesheets.tests import stamp


class Stage7Tests(TaskFixtures, TransactionTestCase):
    def setUp(self):
        MutationLock.objects.get_or_create(key='domain')
        self.setup_tasks()
        self.root = self.create('Root')
        self.child = self.create('Child', parent=self.root)
        self.leaf = self.create('Leaf', parent=self.child)
        self.hidden = self.create('Private project work', project=self.other)
        self.entry(self.alice, self.root, '2026-10-09T09:00', '2026-10-09T10:00')
        self.entry(self.alice, self.child, '2026-10-09T10:00', '2026-10-09T12:00')
        self.entry(self.alice, self.leaf, '2026-10-09T12:00', '2026-10-09T12:30')
        self.entry(self.alice, None, '2026-10-09T12:30', '2026-10-09T13:00')
        self.entry(self.alice, self.root, '2026-10-10T11:00', None)
        self.entry(self.bob, self.root, '2026-10-09T09:00', '2026-10-09T10:00')
        self.entry(self.bob, self.hidden, '2026-10-09T10:00', '2026-10-09T12:00')
        self.client = APIClient(enforce_csrf_checks=True)
        self.client.force_authenticate(self.alice)

    def entry(self, owner, task, start, end):
        session = WorkSession.objects.create(timesheet_id=owner.pk, started_at=stamp(start),
                                             ended_at=stamp(end) if end else None,
                                             state='closed' if end else 'unfinished')
        return TimeEntry.objects.create(timesheet_id=owner.pk, session=session, task=task,
                                        kind='task' if task else 'break', started_at=session.started_at,
                                        ended_at=session.ended_at)

    def get(self, kind='projects', **params):
        return self.client.get(f'/api/v1/reports/{kind}/', {'from': '2026-10-09', 'to': '2026-10-10', **params})

    def records(self, **params):
        response = self.client.get('/api/v1/reports/records.csv', {'from': '2026-10-09', 'to': '2026-10-10', **params},
                                   HTTP_ACCEPT='text/csv')
        self.assertEqual(response.status_code, 200)
        rows = list(csv.DictReader(StringIO(b''.join(response.streaming_content).decode())))
        response.close()
        return rows

    def test_reports_reconcile_direct_descendant_daily_and_project_hours(self):
        data = self.get().json()
        self.assertEqual(data['total_hours'], '3.50')
        self.assertEqual({r['name']: r['hours'] for r in data['results']}, {'Website': '3.50', 'Portal': '0.00'})
        rows = {r['title']: r for r in self.get('tasks').json()['results']}
        self.assertEqual([(rows[k]['direct_hours'], rows[k]['descendant_hours'], rows[k]['total_hours'])
                          for k in ['Root', 'Child', 'Leaf']],
                         [('1.00', '2.50', '3.50'), ('2.00', '0.50', '2.50'), ('0.50', '0.00', '0.50')])
        self.assertEqual([rows[k]['depth'] for k in ['Root', 'Child', 'Leaf']], [0, 1, 2])
        daily = self.get('people-days').json()
        self.assertEqual([(r['name'], r['date'], r['hours']) for r in daily['results']],
                         [('Alice', '2026-10-09', '3.50'), ('Alice', '2026-10-10', '0.00')])

    def test_access_matrix_filters_before_totals_options_and_csv(self):
        ProjectGrant.objects.filter(user=self.alice).delete()
        local = ProjectGrant.objects.create(user=self.alice, project=self.project)
        inherited = OrganizationGrant.objects.create(user=self.alice, organization=self.project.organization)
        # Read/write are independent; role, timesheet write, and task write confer
        # no report read access. Either project or organization read suffices.
        for direct, org, task_write, read_others, write_others, admin in itertools.product([False, True], repeat=6):
            with self.subTest(direct=direct, org=org, task_write=task_write, read_others=read_others,
                              write_others=write_others, admin=admin):
                ProjectGrant.objects.filter(pk=local.pk).update(task_read=direct, task_write=task_write)
                OrganizationGrant.objects.filter(pk=inherited.pk).update(task_read=org)
                User.objects.filter(pk=self.alice.pk).update(read_others_timesheets=read_others,
                    write_others_timesheets=write_others, is_admin=admin)
                expected = '4.50' if read_others else '3.50'
                if not (direct or org):
                    expected = '0.00'
                for kind in ('projects', 'people-days', 'tasks'):
                    response = self.get(kind)
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.json()['total_hours'], expected)
                    self.assertNotIn('Private project work', str(response.json()))
                csv_rows = self.records()
                self.assertEqual(len(csv_rows), (5 if read_others else 4) if direct or org else 0)
                self.assertFalse(any(r['Project'] == 'Portal' for r in csv_rows))
                options = self.client.get('/api/v1/reports/options/').json()
                self.assertEqual(len(options['projects']), int(direct or org))
                self.assertNotIn('email', str(options))
                self.assertEqual(len(options['people']), 2 if read_others and (direct or org) else 1)

    def test_whole_sheet_can_exceed_project_report_and_permission_changes_apply(self):
        User.objects.filter(pk=self.alice.pk).update(read_others_timesheets=True)
        replace_grant(self.admin, self.alice.pk, 'projects', self.other.pk, {})
        sheet = read_day(self.alice, self.bob.pk, date(2026, 10, 9))
        self.assertEqual(sheet['work_seconds'], 10800)
        self.assertEqual(self.get(person=str(self.bob.pk)).json()['total_hours'], '1.00')
        self.assertEqual(len(self.records()), 5)
        User.objects.filter(pk=self.alice.pk).update(read_others_timesheets=False, write_others_timesheets=True)
        self.assertEqual(self.get().json()['total_hours'], '3.50')
        self.assertEqual(self.get(person=str(self.bob.pk)).status_code, 404)
        self.assertEqual(len(self.records()), 4)

    def test_subtree_person_and_date_filters_combine_without_double_counting(self):
        User.objects.filter(pk=self.alice.pk).update(read_others_timesheets=True)
        child = self.get('tasks', task=str(self.child.pk), person=str(self.alice.pk), to='2026-10-09').json()
        self.assertEqual(child['total_hours'], '2.50')
        self.assertEqual([r['title'] for r in child['results']], ['Child', 'Leaf'])
        self.assertEqual(child['results'][0]['parent'], None)
        self.assertEqual(self.get(task=str(self.root.pk), person=str(self.bob.pk)).json()['total_hours'], '1.00')
        self.assertEqual(self.get(project=str(self.other.pk), task=str(self.root.pk)).json()['total_hours'], '0.00')
        self.assertEqual(self.get('people-days', person=str(self.bob.pk), to='2026-10-09').json()['total_hours'], '3.00')

    def test_csv_actual_bytes_unicode_quoting_open_and_closed_records(self):
        Task = type(self.root)
        Task.objects.filter(pk=self.root.pk).update(title='Root, "quoted"\nЗадача')
        User.objects.filter(pk=self.alice.pk).update(display_name='Алиса, "A"')
        rows = self.records()
        self.assertEqual(list(rows[0]), ['Person', 'Project', 'Task', 'Date', 'Start Time', 'End Time', 'Duration'])
        self.assertEqual(rows[0], {'Person': 'Алиса, "A"', 'Project': 'Website', 'Task': 'Root, "quoted"\nЗадача',
                                 'Date': '2026-10-09', 'Start Time': '09:00:00', 'End Time': '10:00:00', 'Duration': '1.00'})
        self.assertEqual(rows[-1]['End Time'], '')
        self.assertEqual(rows[-1]['Duration'], '0.00')
        self.assertEqual(len(rows), 4)  # No break or closing marker.
        self.get(task=str(self.child.pk), person=str(self.alice.pk))
        self.assertEqual(len(self.records()), 4)  # Report filters do not persist into CSV.
        invalid = self.client.get('/api/v1/reports/records.csv', HTTP_ACCEPT='text/csv')
        self.assertEqual(invalid.status_code, 400)
        self.assertTrue(invalid['Content-Type'].startswith('application/json'))

    def test_invalid_ranges_filters_and_unavailable_selections(self):
        for params in [{'from': ''}, {'from': 'bad'}, {'from': '2026-10-11'}, {'to': '9999-12-31'},
                       {'project': 'bad'}, {'surprise': 'x'}, {'from': ['2026-10-09', '2026-10-10']}]:
            self.assertEqual(self.get(**params).status_code, 400, params)
        self.assertEqual(self.client.get('/api/v1/reports/projects/').status_code, 400)
        self.assertEqual(self.client.get('/api/v1/reports/options/', {'person': self.bob.pk}).status_code, 400)
        replace_grant(self.admin, self.alice.pk, 'projects', self.other.pk, {'task_write': True})
        for field, key in [('project', self.other.pk), ('task', self.hidden.pk), ('person', self.bob.pk),
                           ('project', uuid4()), ('task', uuid4()), ('person', uuid4())]:
            self.assertEqual(self.get(**{field: str(key)}).status_code, 404)
        for key in ('person', 'project', 'task'):
            response = self.client.get('/api/v1/reports/records.csv', {'from': '2026-10-09', 'to': '2026-10-10', key: str(uuid4())})
            self.assertEqual(response.status_code, 400)

    def test_real_session_authentication_and_deactivation(self):
        self.client.force_authenticate(user=None)
        self.assertEqual(self.get().status_code, 403)
        csrf = self.client.get('/api/v1/auth/csrf/').json()['csrf_token']
        result = self.client.post('/api/v1/auth/login/', {'email': self.alice.email, 'password': PASSWORD},
                                  format='json', HTTP_X_CSRFTOKEN=csrf)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(self.get().json()['total_hours'], '3.50')
        User.objects.filter(pk=self.alice.pk).update(is_active=False)
        self.assertEqual(self.get().status_code, 403)
        self.assertEqual(self.client.get('/api/v1/reports/options/').status_code, 403)
        self.assertEqual(self.client.get('/api/v1/reports/records.csv').status_code, 403)

    def test_rounding_sums_original_subsecond_durations(self):
        self.entry(self.alice, self.root, '2026-10-11T09:00:00', '2026-10-11T09:00:18')
        self.entry(self.alice, self.child, '2026-10-11T09:00:18', '2026-10-11T09:00:36')
        self.entry(self.alice, self.leaf, '2026-10-11T09:00:36', '2026-10-11T09:00:36.300000')
        data = self.get('tasks', **{'from': '2026-10-11', 'to': '2026-10-11'}).json()
        self.assertEqual(data['total_hours'], '0.01')
        rows = {r['title']: r for r in data['results']}
        self.assertEqual(rows['Root']['direct_hours'], '0.01')
        self.assertEqual(rows['Child']['direct_hours'], '0.01')
        self.assertEqual(rows['Root']['total_hours'], '0.01')
        self.entry(self.alice, self.root, '2026-10-12T09:00:00', '2026-10-12T09:00:17.900000')
        self.entry(self.alice, self.child, '2026-10-12T09:00:17.900000', '2026-10-12T09:00:18.100000')
        self.assertEqual(self.get(**{'from': '2026-10-12', 'to': '2026-10-12'}).json()['total_hours'], '0.01')

    @override_settings(TIME_ZONE='Europe/Berlin')
    def test_midnight_zone_reallocation_clipping_and_reads_never_write(self):
        # Deliberately stored as one UTC span: reads must allocate in the current zone.
        self.entry(self.alice, self.root, '2026-10-11T21:30', '2026-10-12T00:30')
        self.entry(self.alice, self.child, '2026-10-12T23:30', None)
        stored = list(TimeEntry.objects.order_by('id').values())
        revision = MutationLock.objects.get(pk='domain').revision
        daily = self.get('people-days', **{'from': '2026-10-11', 'to': '2026-10-13'}).json()
        self.assertEqual([(r['date'], r['hours']) for r in daily['results']],
                         [('2026-10-11', '0.50'), ('2026-10-12', '2.50'), ('2026-10-13', '0.00')])
        csv_rows = self.records(**{'from': '2026-10-12', 'to': '2026-10-12'})
        self.assertEqual(len(csv_rows), 1)
        self.assertEqual((csv_rows[0]['Start Time'], csv_rows[0]['End Time'], csv_rows[0]['Duration']), ('00:00:00', '02:30:00', '2.50'))
        self.assertEqual(list(TimeEntry.objects.order_by('id').values()), stored)
        self.assertEqual(MutationLock.objects.get(pk='domain').revision, revision)

    def test_historical_correction_owner_change_and_hierarchy_project_moves(self):
        row = TimeEntry.objects.get(task=self.leaf)
        # Correct an independent session edge through the actual timesheet command.
        data = {'command': 'replace_day', 'date': '2026-10-09',
                'expected_revision': Timesheet.objects.get(user=self.alice).revision,
                'sessions': []}
        day = read_day(self.alice, self.alice.pk, date(2026, 10, 9))
        for session in day['sessions']:
            values = {k: session[k] for k in ('id', 'state', 'ended_at')}
            values['rows'] = [{k: r[k] for k in ('id', 'kind', 'task', 'started_at', 'ended_at')} for r in session['rows']]
            if session['id'] == str(row.session_id):
                values['rows'][0]['started_at'] = '2026-10-09T12:15:00Z'
            data['sessions'].append(values)
        command(self.alice, self.alice.pk, data)
        self.assertEqual(self.get().json()['total_hours'], '3.25')
        self.root.owner = self.bob
        self.root.save(update_fields=['owner'])
        self.assertEqual(self.get(person=str(self.alice.pk)).json()['total_hours'], '3.25')
        self.compound(self.alice, 'move', {'parent': None}, self.child)
        root = next(r for r in self.get('tasks').json()['results'] if r['title'] == 'Root')
        self.assertEqual(root['total_hours'], '1.00')
        self.compound(self.alice, 'move', {'parent': None, 'project': str(self.other.pk)}, self.root)
        self.assertEqual({r['name']: r['hours'] for r in self.get().json()['results']}, {'Website': '2.25', 'Portal': '1.00'})
        self.assertEqual(self.records()[0]['Project'], 'Portal')

    def test_report_snapshot_stays_consistent_during_move_and_revocation(self):
        ready, release = Event(), Event()
        original = services.authorized_records
        def pause(*args):
            if not ready.is_set():
                ready.set()
                if not release.wait(10):
                    raise AssertionError('Writer did not finish')
            return original(*args)
        def reader():
            close_old_connections()
            try:
                return services.report(self.alice, 'projects', QueryDict('from=2026-10-09&to=2026-10-10'))
            finally:
                close_old_connections()
        with patch('reports.services.authorized_records', side_effect=pause), ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(reader)
            try:
                self.assertTrue(ready.wait(10))
                with transaction.atomic():
                    self.compound(self.alice, 'move', {'parent': None, 'project': str(self.other.pk)}, self.root)
                    replace_grant(self.admin, self.alice.pk, 'projects', self.project.pk, {})
                    replace_grant(self.admin, self.alice.pk, 'projects', self.other.pk, {})
            finally:
                release.set()
            result = future.result(timeout=10)
        self.assertEqual(result['total_hours'], '3.50')
        self.assertEqual({r['name']: r['hours'] for r in result['results']}, {'Website': '3.50', 'Portal': '0.00'})
        self.assertEqual(self.get().json()['results'], [])

    def test_csv_is_materialized_before_serving_and_transaction_is_read_only(self):
        response = self.client.get('/api/v1/reports/records.csv', {'from': '2026-10-09', 'to': '2026-10-10'})
        replace_grant(self.admin, self.alice.pk, 'projects', self.project.pk, {})
        with self.assertNumQueries(0):
            rows = list(csv.DictReader(StringIO(b''.join(response.streaming_content).decode())))
        response.close()
        self.assertEqual(len(rows), 4)
        self.assertEqual(self.records(), [])
        with services.snapshot(), connection.cursor() as cursor:
            cursor.execute('SHOW transaction_isolation')
            self.assertEqual(cursor.fetchone()[0], 'repeatable read')
            cursor.execute('SHOW transaction_read_only')
            self.assertEqual(cursor.fetchone()[0], 'on')
