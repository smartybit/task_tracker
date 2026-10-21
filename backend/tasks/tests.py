import itertools
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient

from access.models import OrganizationGrant, ProjectGrant
from access.policies import FLAGS
from access.services import replace_grant
from accounts.services import bootstrap_admin, create_account
from core.domain import DomainError, mutation
from core.models import MutationLock
from projects.models import Organization, Project
from projects.services import delete_catalog, save_organization, save_project
from tasks.models import Task, TaskStatus, TaskStatusChange
from tasks.services import change_task, delete_status, preview_task, save_status
from timesheets.models import TimeEntry, Timesheet, WorkSession

PASSWORD = 'stage-four-long-test-password'
User = get_user_model()


class TaskFixtures:
    def setup_tasks(self):
        # TransactionTestCase flushes seed rows; restore catalog only in that case.
        if not TaskStatus.objects.exists():
            for name, final in [('In Progress', False), ('Postponed', False), ('Waiting for Customer Response', False), ('Canceled', True), ('Completed', True)]:
                TaskStatus.objects.create(name=name, final=final)
        self.admin = bootstrap_admin({'email': 'admin@example.test', 'password': PASSWORD})
        self.alice = create_account(self.admin, {'email': 'alice@example.test', 'password': PASSWORD, 'display_name': 'Alice'})
        self.bob = create_account(self.admin, {'email': 'bob@example.test', 'password': PASSWORD, 'display_name': 'Bob'})
        org = save_organization(self.admin, {'name': 'Studio'})
        self.project = save_project(self.admin, {'name': 'Website', 'organization': str(org.pk)})
        other_org = save_organization(self.admin, {'name': 'Client'})
        self.other = save_project(self.admin, {'name': 'Portal', 'organization': str(other_org.pk)})
        for user in (self.alice, self.bob):
            for project in (self.project, self.other):
                replace_grant(self.admin, user.pk, 'projects', project.pk, {'task_read': True, 'task_write': True})
        self.active = TaskStatus.objects.get(name='In Progress')
        self.final = TaskStatus.objects.get(name='Completed')

    def create(self, title='Task', parent=None, status=None, actor=None, project=None, **extra):
        actor = actor or self.alice
        data = dict(title=title, description='private description', project=str((project or self.project).pk),
                    parent=str(parent.pk) if parent else None, status=str((status or self.active).pk), **extra)
        result = self.compound(actor, 'create', data)
        return Task.objects.get(pk=result['id'])

    def compound(self, actor, kind, data, task=None):
        if task:
            task.refresh_from_db()
            data = {**data, 'expected_revision': task.revision}
        preview = preview_task(actor, kind, data, task.pk if task else None)
        return change_task(actor, kind, {**data, 'expected_domain_revision': preview['domain_revision'], 'confirm': True}, task.pk if task else None)


class Stage4Tests(TaskFixtures, TestCase):
    def setUp(self):
        self.setup_tasks()
        self.client = APIClient(enforce_csrf_checks=True)

    def login(self, actor):
        token = self.client.get('/api/v1/auth/csrf/').json()['csrf_token']
        result = self.client.post('/api/v1/auth/login/', {'email': actor.email, 'password': PASSWORD}, format='json', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(result.status_code, 200)
        self.client.credentials(HTTP_X_CSRFTOKEN=result.json()['csrf_token'])

    def test_creation_history_revision_csrf_and_strict_fields(self):
        task = self.create()
        self.assertEqual(task.creator, self.alice)
        self.assertEqual(task.owner, self.alice)
        self.assertEqual(task.history.count(), 1)
        self.assertIsNone(task.history.get().previous_status)
        self.login(self.alice)
        path = f'/api/v1/tasks/{task.pk}/'
        self.client.credentials()
        self.assertEqual(self.client.patch(path, {'title': 'Bad', 'expected_revision': 0}, format='json').status_code, 403)
        self.login(self.alice)
        self.assertEqual(self.client.patch(path, {'owner': str(self.bob.pk), 'expected_revision': 0}, format='json').status_code, 400)
        result = self.client.patch(path, {'title': 'Edited', 'expected_revision': 0}, format='json')
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual(result.data['revision'], 1)
        self.assertEqual(self.client.patch(path, {'title': 'Stale', 'expected_revision': 0}, format='json').data['code'], 'stale_revision')
        task.refresh_from_db()
        self.assertEqual(task.title, 'Edited')
        self.assertEqual(task.history.count(), 1)

    def test_preview_never_writes_and_stale_confirmation_rolls_back(self):
        task = self.create()
        revision = MutationLock.objects.get(pk='domain').revision
        data = {'status': str(self.final.pk), 'expected_revision': task.revision}
        preview = preview_task(self.alice, 'status', data, task.pk)
        self.assertEqual(MutationLock.objects.get(pk='domain').revision, revision)
        task.refresh_from_db()
        self.assertEqual(task.status, self.active)
        save_organization(self.admin, {'name': 'Intervening mutation'})
        with self.assertRaises(DomainError) as raised:
            change_task(self.alice, 'status', {**data, 'confirm': True, 'expected_domain_revision': preview['domain_revision']}, task.pk)
        self.assertEqual(raised.exception.code, 'stale_preview')
        self.assertEqual(task.history.count(), 1)
        with self.assertRaises(DomainError) as raised:
            change_task(self.alice, 'status', data, task.pk)
        self.assertEqual(raised.exception.code, 'confirmation_required')

    def test_finalization_descendants_and_reopening_history(self):
        root = self.create('Root')
        child = self.create('Child', root)
        leaf = self.create('Leaf', child)
        sibling = self.create('Sibling', root, self.final)
        with self.assertRaises(DomainError) as raised:
            self.compound(self.alice, 'status', {'status': str(self.final.pk)}, root)
        self.assertEqual(raised.exception.code, 'non_final_descendant')
        for task in (leaf, child, root):
            self.compound(self.alice, 'status', {'status': str(self.final.pk)}, task)
        data = {'status': str(self.active.pk), 'reopen_status': str(self.active.pk)}
        self.compound(self.alice, 'status', data, leaf)
        for task in (root, child, leaf):
            task.refresh_from_db()
            self.assertEqual(task.status, self.active)
            self.assertEqual(task.history.count(), 3)
        sibling.refresh_from_db()
        self.assertEqual(sibling.status, self.final)
        self.assertEqual(sibling.history.count(), 1)

    def test_final_ancestors_reopen_for_create_and_move(self):
        root = self.create('Final root', status=self.final)
        with self.assertRaises(DomainError) as raised:
            self.create('Child', root)
        self.assertEqual(raised.exception.code, 'reopen_status_required')
        self.assertEqual(Task.objects.count(), 1)
        self.create('Child', root, reopen_status=str(self.active.pk))
        root.refresh_from_db()
        self.assertEqual(root.status, self.active)
        target = self.create('Final target', status=self.final)
        self.compound(self.alice, 'move', {'parent': str(target.pk), 'reopen_status': str(self.active.pk)}, root)
        target.refresh_from_db()
        self.assertEqual(target.status, self.active)

    def test_move_cycles_project_consistency_and_atomic_owner_checks(self):
        root = self.create('Root')
        child = self.create('Child', root, actor=self.bob)
        leaf = self.create('Leaf', child)
        target = self.create('Destination', project=self.other)
        for data, code in [({'parent': str(leaf.pk)}, 'hierarchy_cycle'),
                           ({'parent': str(root.pk)}, 'hierarchy_cycle'),
                           ({'parent': str(target.pk)}, 'project_mismatch')]:
            with self.assertRaises(DomainError) as raised:
                self.compound(self.alice, 'move', data, root)
            self.assertEqual(raised.exception.code, code)
        replace_grant(self.admin, self.bob.pk, 'projects', self.other.pk, {})
        with self.assertRaises(DomainError) as raised:
            self.compound(self.alice, 'move', {'parent': str(target.pk), 'project': str(self.other.pk)}, root)
        self.assertEqual(raised.exception.code, 'owner_ineligible')
        self.assertEqual(Task.objects.filter(project=self.project).count(), 3)
        replace_grant(self.admin, self.bob.pk, 'projects', self.other.pk, {'task_write': True})
        self.compound(self.alice, 'move', {'parent': str(target.pk), 'project': str(self.other.pk)}, root)
        for task in (root, child, leaf):
            task.refresh_from_db()
            self.assertEqual(task.project, self.other)
        self.assertEqual(child.owner, self.bob)
        self.assertEqual(root.parent, target)
        self.assertEqual(leaf.parent, child)

    def test_owner_access_loss_preserved_and_transfer_requires_eligibility(self):
        task = self.create()
        replace_grant(self.admin, self.alice.pk, 'projects', self.project.pk, {})
        change_task(self.bob, 'edit', {'description': 'Still editable', 'expected_revision': 0}, task.pk)
        task.refresh_from_db()
        self.assertEqual(task.owner, self.alice)
        self.login(self.alice)
        self.assertEqual(self.client.get(f'/api/v1/tasks/{task.pk}/').status_code, 404)
        self.assertEqual(self.client.patch(f'/api/v1/tasks/{task.pk}/', {'title': 'Denied', 'expected_revision': 1}, format='json').status_code, 403)
        with self.assertRaises(DomainError):
            change_task(self.bob, 'owner', {'owner': str(self.alice.pk), 'expected_revision': 1}, task.pk)
        result = change_task(self.bob, 'owner', {'owner': str(self.bob.pk), 'expected_revision': 1}, task.pk)
        self.assertEqual(result['owner'], str(self.bob.pk))

    def test_status_catalog_and_database_permanent_protection(self):
        expected = {'In Progress': False, 'Postponed': False, 'Waiting for Customer Response': False, 'Canceled': True, 'Completed': True}
        self.assertEqual(dict(TaskStatus.objects.values_list('name', 'final')), expected)
        unused = save_status(self.admin, {'name': 'Unused', 'final': False})
        save_status(self.admin, {'name': 'Renamed', 'final': True}, unused.pk)
        delete_status(self.admin, unused.pk)
        task = self.create(status=self.final)
        self.compound(self.alice, 'status', {'status': str(self.active.pk)}, task)
        self.compound(self.alice, 'delete', {}, task)
        self.final.refresh_from_db()
        self.assertIsNotNone(self.final.first_used_at)
        for operation in [lambda: save_status(self.admin, {'name': 'Altered', 'final': True}, self.final.pk), lambda: delete_status(self.admin, self.final.pk)]:
            with self.assertRaises(DomainError) as raised:
                operation()
            self.assertEqual(raised.exception.code, 'status_already_used')
        for operation in [lambda: TaskStatus.objects.filter(pk=self.final.pk).update(name='Direct rename'),
                          lambda: TaskStatus.objects.filter(pk=self.final.pk).update(final=False),
                          lambda: TaskStatus.objects.filter(pk=self.final.pk).update(first_used_at=None),
                          lambda: TaskStatus.objects.filter(pk=self.final.pk).delete()]:
            with self.assertRaises(IntegrityError), transaction.atomic():
                operation()

    def test_real_time_references_and_children_prevent_all_deletion_paths(self):
        root = self.create('Root')
        child = self.create('Child', root)
        with self.assertRaises(DomainError) as raised:
            self.compound(self.alice, 'delete', {}, root)
        self.assertEqual(raised.exception.code, 'task_in_use')
        session = WorkSession.objects.create(timesheet_id=self.bob.pk, started_at=timezone.now())
        TimeEntry.objects.create(timesheet_id=self.bob.pk, session=session, kind='task', task=child, started_at=session.started_at)
        for actor in (self.alice, self.admin):
            if actor == self.admin:
                replace_grant(self.admin, actor.pk, 'projects', self.project.pk, {'task_write': True})
            with self.assertRaises(DomainError) as raised:
                self.compound(actor, 'delete', {}, child)
            self.assertEqual(raised.exception.code, 'task_in_use')
        with self.assertRaises(DomainError):
            delete_catalog(self.admin, Project, self.project.pk)
        with self.assertRaises(IntegrityError), transaction.atomic():
            child.delete()
        self.assertEqual(TimeEntry.objects.count(), 1)
        self.assertEqual(Task.objects.count(), 2)

    def test_api_grant_matrix_lists_trees_history_and_write_only_commands(self):
        task = self.create()
        self.login(self.admin)
        self.assertEqual(self.client.get('/api/v1/tasks/').data['count'], 0)
        self.assertEqual(self.client.get(f'/api/v1/tasks/{task.pk}/').status_code, 404)
        self.assertEqual(self.client.patch(f'/api/v1/tasks/{task.pk}/', {'title': 'Denied', 'expected_revision': 0}, format='json').status_code, 403)
        self.login(self.bob)
        # All 256 independent organization/project flag combinations reach real endpoints.
        for bits in itertools.product([False, True], repeat=8):
            local, inherited = dict(zip(FLAGS, bits[:4])), dict(zip(FLAGS, bits[4:]))
            replace_grant(self.admin, self.bob.pk, 'projects', self.project.pk, local)
            replace_grant(self.admin, self.bob.pk, 'organizations', self.project.organization_id, inherited)
            read, write = local['task_read'] or inherited['task_read'], local['task_write'] or inherited['task_write']
            for view in ('flat', 'tree'):
                result = self.client.get('/api/v1/tasks/', {'view': view})
                self.assertEqual(result.data['count'], int(read), bits)
            for route in ('', 'history/'):
                result = self.client.get(f'/api/v1/tasks/{task.pk}/{route}')
                self.assertEqual(result.status_code, 200 if read else 404, bits)
            task.refresh_from_db()
            result = self.client.patch(f'/api/v1/tasks/{task.pk}/', {'title': 'Private title', 'expected_revision': task.revision}, format='json')
            self.assertEqual(result.status_code, 200 if write else 403, bits)
            if write and not read:
                self.assertEqual(set(result.data), {'id', 'revision', 'domain_revision'})
                preview = self.client.post(f'/api/v1/tasks/{task.pk}/status/preview/', {'expected_revision': result.data['revision'], 'status': str(self.active.pk)}, format='json')
                self.assertEqual(preview.status_code, 200)
                self.assertEqual(preview.data['affected'], [])
                self.assertNotIn('private', str(preview.data))

    def test_api_filters_pagination_owner_directory_and_invalid_inputs(self):
        root = self.create('Root')
        child = self.create('Child', root, self.final)
        hidden = self.create('Hidden', project=self.other)
        replace_grant(self.admin, self.alice.pk, 'projects', self.other.pk, {})
        self.login(self.alice)
        result = self.client.get('/api/v1/tasks/', {'project': str(self.project.pk), 'status': [str(self.active.pk), str(self.final.pk)], 'view': 'tree'})
        self.assertEqual(result.data['count'], 2)
        self.assertEqual({row['id'] for row in result.data['results']}, {str(root.pk), str(child.pk)})
        result = self.client.get('/api/v1/tasks/', {'status': str(self.final.pk)})
        self.assertEqual(result.data['results'][0]['parent'], str(root.pk))
        self.assertEqual(result.data['count'], 1)
        self.assertEqual(self.client.get('/api/v1/tasks/', {'page': 2}).data['results'], [])
        for params in ({'page': 0}, {'status': 'bad'}, {'project': 'bad'}, {'view': 'bad'}):
            self.assertEqual(self.client.get('/api/v1/tasks/', params).status_code, 400)
        directory = self.client.get(f'/api/v1/projects/{self.project.pk}/eligible-owners/')
        self.assertEqual({row['id'] for row in directory.data['results']}, {str(self.alice.pk), str(self.bob.pk)})
        self.assertNotIn('email', str(directory.data))
        self.assertEqual(self.client.get(f'/api/v1/tasks/{hidden.pk}/').status_code, 404)
        self.assertEqual(self.client.post('/api/v1/statuses/', {'name': 'Denied', 'final': False}, format='json').status_code, 403)

    def test_write_only_preview_does_not_disclose_source_content_on_project_move(self):
        task = self.create()
        replace_grant(self.admin, self.bob.pk, 'projects', self.project.pk, {'task_write': True})
        data = {'parent': None, 'project': str(self.other.pk), 'expected_revision': 0}
        result = preview_task(self.bob, 'move', data, task.pk)
        self.assertEqual(result['affected'], [])
        self.assertNotIn('private description', str(result))
        # Once explicitly moved, the destination's read grant applies normally.
        result = self.compound(self.bob, 'move', data, task)
        self.assertEqual(result['description'], 'private description')

    def test_revoked_preview_and_write_only_status_owner_move_delete_endpoints(self):
        task = self.create()
        self.login(self.bob)
        replace_grant(self.admin, self.bob.pk, 'projects', self.project.pk, {'task_write': True})
        owner = self.client.post(f'/api/v1/tasks/{task.pk}/owner/', {'owner': str(self.bob.pk), 'expected_revision': 0}, format='json')
        self.assertEqual(owner.status_code, 200)
        self.assertEqual(set(owner.data), {'id', 'revision', 'domain_revision'})
        for kind, values in [('status', {'status': str(self.final.pk)}), ('move', {'parent': None}), ('delete', {})]:
            task.refresh_from_db()
            data = {**values, 'expected_revision': task.revision}
            preview = self.client.post(f'/api/v1/tasks/{task.pk}/{kind}/preview/', data, format='json')
            self.assertEqual(preview.status_code, 200)
            self.assertEqual(preview.data['affected'], [])
            data.update(confirm=True, expected_domain_revision=preview.data['domain_revision'])
            if kind == 'delete':
                # Permission loss between preview and confirmation must win over revisions.
                replace_grant(self.admin, self.bob.pk, 'projects', self.project.pk, {})
                denied = self.client.delete(f'/api/v1/tasks/{task.pk}/', data, format='json')
                self.assertEqual(denied.status_code, 403)
                self.assertTrue(Task.objects.filter(pk=task.pk).exists())
                replace_grant(self.admin, self.bob.pk, 'projects', self.project.pk, {'task_write': True})
                data['expected_domain_revision'] = MutationLock.objects.get(pk='domain').revision
                result = self.client.delete(f'/api/v1/tasks/{task.pk}/', data, format='json')
            else:
                result = self.client.post(f'/api/v1/tasks/{task.pk}/{kind}/', data, format='json')
            self.assertEqual(result.status_code, 200, result.data)
            self.assertEqual(set(result.data), {'id', 'revision', 'domain_revision'})

    def test_api_compound_commands_and_write_only_creation(self):
        self.login(self.alice)
        data = {'title': 'API task', 'description': 'Description', 'project': str(self.project.pk), 'status': str(self.active.pk)}
        preview = self.client.post('/api/v1/tasks/preview/', data, format='json')
        self.assertEqual(preview.status_code, 200, preview.data)
        result = self.client.post('/api/v1/tasks/', {**data, 'confirm': True, 'expected_domain_revision': preview.data['domain_revision']}, format='json')
        self.assertEqual(result.status_code, 201, result.data)
        task_id = result.data['id']
        self.assertEqual(self.client.post(f'/api/v1/tasks/{task_id}/owner/', {'owner': str(self.bob.pk), 'expected_revision': 0}, format='json').status_code, 200)
        for command, payload in [('status', {'status': str(self.final.pk)}), ('move', {'parent': None}), ('delete', {})]:
            revision = Task.objects.get(pk=task_id).revision
            payload['expected_revision'] = revision
            preview = self.client.post(f'/api/v1/tasks/{task_id}/{command}/preview/', payload, format='json')
            self.assertEqual(preview.status_code, 200, preview.data)
            payload.update(confirm=True, expected_domain_revision=preview.data['domain_revision'])
            url = f'/api/v1/tasks/{task_id}/' if command == 'delete' else f'/api/v1/tasks/{task_id}/{command}/'
            result = getattr(self.client, 'delete' if command == 'delete' else 'post')(url, payload, format='json')
            self.assertEqual(result.status_code, 200, result.data)
        replace_grant(self.admin, self.alice.pk, 'projects', self.project.pk, {'task_write': True})
        result = self.compound(self.alice, 'create', data)
        self.assertEqual(set(result), {'id', 'revision', 'domain_revision'})
        self.assertEqual(self.client.get(f"/api/v1/tasks/{result['id']}/").status_code, 404)


class ConcurrentTaskTests(TaskFixtures, TransactionTestCase):
    def setUp(self):
        MutationLock.objects.get_or_create(key='domain')
        self.setup_tasks()

    def worker(self, operation):
        close_old_connections()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET lock_timeout = '5s'")
            try:
                operation()
                return 'committed'
            except DomainError as error:
                return error.code
        finally:
            connection.close()

    def race(self, first, second):
        barrier = Barrier(2)
        def run(operation):
            barrier.wait(timeout=5)
            return self.worker(operation)
        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(run, [first, second]))

    def test_competing_reparents_cannot_create_cycle(self):
        a, b = self.create('A'), self.create('B')
        domain = MutationLock.objects.get(pk='domain').revision
        def move(task, parent):
            return lambda: change_task(self.alice, 'move', {'parent': str(parent.pk), 'expected_revision': 0, 'expected_domain_revision': domain, 'confirm': True}, task.pk)
        results = self.race(move(a, b), move(b, a))
        self.assertEqual(results.count('committed'), 1)
        a.refresh_from_db(); b.refresh_from_db()
        self.assertFalse(a.parent_id == b.pk and b.parent_id == a.pk)

    def test_deletion_races_child_creation_without_orphans(self):
        root = self.create('Root')
        domain = MutationLock.objects.get(pk='domain').revision
        results = self.race(
            lambda: change_task(self.alice, 'delete', {'expected_revision': 0, 'expected_domain_revision': domain, 'confirm': True}, root.pk),
            lambda: change_task(self.alice, 'create', {'title': 'Child', 'project': str(self.project.pk), 'parent': str(root.pk), 'status': str(self.active.pk), 'expected_domain_revision': domain, 'confirm': True}))
        self.assertEqual(results.count('committed'), 1)
        if Task.objects.filter(title='Child').exists():
            self.assertTrue(Task.objects.filter(pk=root.pk).exists())
        else:
            self.assertFalse(Task.objects.filter(pk=root.pk).exists())

    def test_deletion_races_real_time_reference(self):
        task = self.create()
        domain = MutationLock.objects.get(pk='domain').revision
        @mutation
        def record_reference():
            # Test-only persistence operation, not a Stage 5 command or endpoint.
            from core.domain import find
            target = find(Task, task.pk)
            sheet = Timesheet.objects.select_for_update().get(user=self.bob)
            session = WorkSession.objects.create(timesheet=sheet, started_at=timezone.now())
            TimeEntry.objects.create(timesheet=sheet, session=session, kind='task', task=target, started_at=session.started_at)
        results = self.race(
            lambda: change_task(self.alice, 'delete', {'expected_revision': 0, 'expected_domain_revision': domain, 'confirm': True}, task.pk), record_reference)
        self.assertEqual(results.count('committed'), 1)
        self.assertEqual(Task.objects.filter(pk=task.pk).exists(), TimeEntry.objects.exists())

    def test_finalization_races_descendant_reopening(self):
        root = self.create('Root')
        leaf = self.create('Leaf', root, self.final)
        domain = MutationLock.objects.get(pk='domain').revision
        def status(task, selected):
            return lambda: change_task(self.alice, 'status', {'status': str(selected.pk), 'reopen_status': str(self.active.pk), 'expected_revision': 0, 'expected_domain_revision': domain, 'confirm': True}, task.pk)
        results = self.race(status(root, self.final), status(leaf, self.active))
        self.assertEqual(results.count('committed'), 1)
        root.refresh_from_db(); leaf.refresh_from_db()
        self.assertFalse(root.status.final and not leaf.status.final)

    def test_waiting_writer_rechecks_revoked_grants(self):
        task = self.create()
        with ThreadPoolExecutor(max_workers=1) as pool:
            with transaction.atomic():
                MutationLock.objects.select_for_update().get(pk='domain')
                ProjectGrant.objects.filter(user=self.alice, project=self.project).update(task_read=False, task_write=False)
                def waiting():
                    with connection.cursor() as cursor:
                        cursor.execute("SET application_name = 'stage4_waiting_writer'")
                    change_task(self.alice, 'edit', {'title': 'Forbidden', 'expected_revision': 0}, task.pk)
                future = pool.submit(self.worker, waiting)
                deadline = time.monotonic() + 5
                while True:
                    with connection.cursor() as cursor:
                        cursor.execute('SELECT pg_stat_clear_snapshot()')
                        cursor.execute("SELECT count(*) FROM pg_stat_activity WHERE application_name='stage4_waiting_writer' AND wait_event_type='Lock'")
                        if cursor.fetchone()[0]:
                            break
                    self.assertLess(time.monotonic(), deadline, 'Writer did not wait on domain lock')
                    time.sleep(0.02)
            self.assertEqual(future.result(timeout=6), 'permission_denied')
        task.refresh_from_db()
        self.assertEqual(task.title, 'Task')
        self.assertEqual(task.history.count(), 1)


class Stage4UpgradeTests(TransactionTestCase):
    def test_stage3_upgrade_preserves_accounts_grants_timesheets_and_seeds_statuses(self):
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        old = [('tasks', None), ('timesheets', '0002_backfill_users')]
        try:
            executor.migrate(old)
            state = MigrationExecutor(connection).loader.project_state([
                ('accounts', '0002_user_session_version'), ('access', '0001_initial'),
                ('projects', '0001_initial'), ('timesheets', '0002_backfill_users'),
                ('core', '0002_seed_mutation_lock')])
            apps = state.apps
            user = apps.get_model('accounts', 'User').objects.create(email='upgrade@example.test', password='existing-hash', display_name='Existing', session_version=3)
            apps.get_model('timesheets', 'Timesheet').objects.create(user=user, revision=7)
            org = apps.get_model('projects', 'Organization').objects.create(name='Existing org')
            project = apps.get_model('projects', 'Project').objects.create(name='Existing project', organization=org)
            apps.get_model('access', 'ProjectGrant').objects.create(user=user, project=project, task_read=True, task_write=True)
            MigrationExecutor(connection).migrate(latest)
            self.assertEqual(User.objects.get(pk=user.pk).password, 'existing-hash')
            self.assertEqual(User.objects.get(pk=user.pk).session_version, 3)
            self.assertEqual(Timesheet.objects.get(user_id=user.pk).revision, 7)
            self.assertTrue(ProjectGrant.objects.get(user_id=user.pk, project_id=project.pk).task_write)
            self.assertEqual(TaskStatus.objects.count(), 5)
            self.assertFalse(Task.objects.exists())
            status = TaskStatus.objects.get(name='Completed')
            Task.objects.create(title='Trigger check', project_id=project.pk, owner_id=user.pk, creator_id=user.pk, status=status)
            status.refresh_from_db()
            self.assertIsNotNone(status.first_used_at)
            with self.assertRaises(IntegrityError), transaction.atomic():
                TaskStatus.objects.filter(pk=status.pk).update(name='Forbidden')
        finally:
            MigrationExecutor(connection).migrate(latest)
