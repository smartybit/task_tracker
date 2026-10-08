import itertools
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient

from access.models import OrganizationGrant, ProjectGrant
from access.policies import FLAGS, can_remark, can_report, can_task, can_timesheet, effective_flags, selectable_projects
from access.services import replace_grant
from accounts.services import bootstrap_admin, create_account, reset_password, update_account
from core.domain import DomainError
from core.models import MutationLock
from projects.models import Organization, Project
from projects.services import save_organization, save_project
from timesheets.models import Timesheet

User = get_user_model()
PASSWORD = 'stage-three-long-test-password'


class Stage3Tests(TestCase):
    def setUp(self):
        self.admin = bootstrap_admin({'email': 'admin@example.test', 'password': PASSWORD})
        self.alice = create_account(self.admin, {'email': 'alice@example.test', 'password': PASSWORD})
        self.org = save_organization(self.admin, {'name': 'Studio'})
        self.project = save_project(self.admin, {'organization': str(self.org.pk), 'name': 'Website'})
        self.client = APIClient(enforce_csrf_checks=True)

    def login(self, user=None, password=PASSWORD):
        user = user or self.admin
        token = self.client.get('/api/v1/auth/csrf/').json()['csrf_token']
        response = self.client.post('/api/v1/auth/login/', {'email': user.email, 'password': password}, format='json', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200, response.data)
        self.client.credentials(HTTP_X_CSRFTOKEN=response.json()['csrf_token'])
        return response

    def test_bootstrap_command_and_guard(self):
        with patch('accounts.management.commands.bootstrap_admin.getpass', return_value=PASSWORD):
            with self.assertRaises(CommandError):
                call_command('bootstrap_admin', email='another@example.test', stdout=StringIO())
        with self.assertRaises(DomainError) as raised:
            bootstrap_admin({'email': 'another@example.test', 'password': PASSWORD})
        self.assertEqual(raised.exception.code, 'bootstrap_unavailable')
        with self.assertRaises(CommandError):
            call_command('createsuperuser', stdout=StringIO())
        self.assertEqual(User.objects.filter(is_admin=True).count(), 1)

    def test_login_csrf_rotation_logout_and_no_registration(self):
        response = self.client.post('/api/v1/auth/login/', {'email': self.admin.email, 'password': PASSWORD}, format='json')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['code'], 'csrf_failed')
        old_token = self.client.get('/api/v1/auth/csrf/').json()['csrf_token']
        response = self.login()
        self.assertNotEqual(old_token, response.json()['csrf_token'])
        self.assertEqual(self.client.get('/api/v1/auth/me/').json()['id'], str(self.admin.pk))
        self.client.credentials()
        self.assertEqual(self.client.post('/api/v1/auth/logout/', {}, format='json').json()['code'], 'csrf_failed')
        self.client.credentials(HTTP_X_CSRFTOKEN=response.json()['csrf_token'])
        self.assertEqual(self.client.post('/api/v1/auth/logout/', {}, format='json').status_code, 200)
        self.assertEqual(self.client.get('/api/v1/auth/me/').json()['code'], 'authentication_required')
        self.assertEqual(self.client.post('/api/v1/auth/register/', {}, format='json').status_code, 404)
        self.assertEqual(self.client.get('/admin/').status_code, 404)

    def test_invalid_inactive_or_missing_login_has_same_error(self):
        token = self.client.get('/api/v1/auth/csrf/').json()['csrf_token']
        update_account(self.admin, self.alice.pk, {'is_active': False})
        bodies = [self.client.post('/api/v1/auth/login/', {'email': email, 'password': password}, format='json', HTTP_X_CSRFTOKEN=token).json()
                  for email, password in [(self.admin.email, 'wrong'), ('missing@example.test', PASSWORD), (self.alice.email, PASSWORD)]]
        self.assertEqual(bodies[0], bodies[1])
        self.assertEqual(bodies[1], bodies[2])
        self.assertEqual(bodies[0]['code'], 'invalid_credentials')

    def test_login_normalizes_email_and_returns_no_password(self):
        self.admin.email = ' ADMIN@EXAMPLE.TEST '
        response = self.login()
        self.assertNotIn('password', str(response.data))
        self.assertNotIn(PASSWORD, str(response.data))

    def test_unsafe_origin_is_rejected_even_with_token(self):
        self.login()
        for origin, expected in [('http://evil.invalid', 403), ('http://frontend:5173', 201)]:
            with self.settings(CSRF_TRUSTED_ORIGINS=['http://frontend:5173']):
                response = self.client.post('/api/v1/organizations/', {'name': 'Origin check'}, format='json', HTTP_ORIGIN=origin)
            self.assertEqual(response.status_code, expected, response.data)
        self.assertEqual(Organization.objects.filter(name='Origin check').count(), 1)

    def test_non_admin_cannot_read_or_modify_management(self):
        self.login(self.alice)
        for method, path, data in [
            ('get', '/api/v1/users/', None),
            ('get', f'/api/v1/users/{self.admin.pk}/', None),
            ('post', '/api/v1/users/', {'email': 'new@example.test', 'password': PASSWORD}),
            ('patch', f'/api/v1/users/{self.alice.pk}/', {'is_admin': True}),
            ('post', f'/api/v1/users/{self.admin.pk}/password-reset/', {'password': PASSWORD}),
            ('get', f'/api/v1/users/{self.alice.pk}/grants/', None),
            ('put', f'/api/v1/users/{self.alice.pk}/grants/projects/{self.project.pk}/', {'task_read': True}),
            ('post', '/api/v1/organizations/', {'name': 'Denied'}),
            ('delete', f'/api/v1/projects/{self.project.pk}/', None),
        ]:
            response = getattr(self.client, method)(path, data, format='json')
            self.assertEqual(response.status_code, 403, (path, response.data))
        self.alice.refresh_from_db()
        self.assertFalse(self.alice.is_admin)
        self.assertFalse(Organization.objects.filter(name='Denied').exists())

    def test_admin_account_create_update_reset_and_password_validation(self):
        self.login()
        response = self.client.post('/api/v1/users/', {'email': ' New@Example.TEST ', 'password': PASSWORD, 'display_name': 'New Person'}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        pk = response.data['id']
        self.assertTrue(Timesheet.objects.filter(user_id=pk).exists())
        self.assertNotIn('password', response.data)
        response = self.client.patch(f'/api/v1/users/{pk}/', {'write_others_timesheets': True}, format='json')
        self.assertTrue(response.data['write_others_timesheets'])
        self.assertFalse(response.data['read_others_timesheets'])
        response = self.client.post(f'/api/v1/users/{pk}/password-reset/', {'password': '123'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertTrue(User.objects.get(pk=pk).check_password(PASSWORD))
        response = self.client.post(f'/api/v1/users/{pk}/password-reset/', {'password': 'replacement-long-test-secret'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.get(pk=pk).check_password('replacement-long-test-secret'))

    def test_password_reset_and_deactivation_reject_existing_sessions(self):
        self.login(self.alice)
        reset_password(self.admin, self.alice.pk, {'password': 'replacement-long-test-secret'})
        self.assertEqual(self.client.get('/api/v1/auth/me/').json()['code'], 'authentication_required')
        self.login(self.alice, 'replacement-long-test-secret')
        update_account(self.admin, self.alice.pk, {'is_active': False})
        self.assertEqual(self.client.get('/api/v1/auth/me/').json()['code'], 'authentication_required')
        update_account(self.admin, self.alice.pk, {'is_active': True})
        self.assertEqual(self.client.get('/api/v1/auth/me/').json()['code'], 'authentication_required')

    def test_admin_revocation_applies_to_existing_session_and_stale_actor(self):
        self.login()
        other = create_account(self.admin, {'email': 'other@example.test', 'password': PASSWORD, 'is_admin': True})
        update_account(other, self.admin.pk, {'is_admin': False})
        self.assertEqual(self.client.get('/api/v1/users/').status_code, 403)
        with self.assertRaises(DomainError):
            save_organization(self.admin, {'name': 'Denied'})
        self.assertFalse(Organization.objects.filter(name='Denied').exists())

    def test_account_creation_rolls_back_with_timesheet_failure(self):
        revision = MutationLock.objects.get(pk='domain').revision
        with patch('timesheets.models.Timesheet.objects.create', side_effect=IntegrityError('private detail')):
            with self.assertRaises(DomainError):
                create_account(self.admin, {'email': 'rollback@example.test', 'password': PASSWORD})
        self.assertFalse(User.objects.filter(email='rollback@example.test').exists())
        self.assertEqual(MutationLock.objects.get(pk='domain').revision, revision)

    def test_duplicates_unknown_fields_and_protected_catalog_changes(self):
        self.login()
        self.assertEqual(self.client.post('/api/v1/users/', {'email': 'ALICE@example.test', 'password': PASSWORD}, format='json').status_code, 409)
        self.assertEqual(self.client.patch(f'/api/v1/users/{self.alice.pk}/', {'password': PASSWORD}, format='json').status_code, 400)
        path = f'/api/v1/users/{self.alice.pk}/grants/projects/{self.project.pk}/'
        self.assertEqual(self.client.put(path, {'inherited_task_read': True}, format='json').status_code, 400)
        self.assertEqual(self.client.delete(f'/api/v1/organizations/{self.org.pk}/').status_code, 409)
        self.assertEqual(self.client.patch(f'/api/v1/projects/{self.project.pk}/', {'organization': str(self.org.pk)}, format='json').status_code, 400)
        self.assertTrue(Project.objects.filter(pk=self.project.pk).exists())
        self.assertTrue(Organization.objects.filter(pk=self.org.pk).exists())
        self.assertEqual(User.objects.count(), 2)

    def test_catalog_crud_and_pagination(self):
        self.login()
        response = self.client.post('/api/v1/organizations/', {'name': 'Temporary'}, format='json')
        org = response.data['id']
        response = self.client.post('/api/v1/projects/', {'name': 'Temporary Project', 'organization': org}, format='json')
        project = response.data['id']
        self.assertEqual(self.client.patch(f'/api/v1/projects/{project}/', {'name': 'Renamed'}, format='json').data['name'], 'Renamed')
        self.assertEqual(self.client.patch(f'/api/v1/organizations/{org}/', {'name': 'Renamed Org'}, format='json').status_code, 200)
        self.assertEqual(self.client.delete(f'/api/v1/projects/{project}/').status_code, 204)
        self.assertEqual(self.client.delete(f'/api/v1/organizations/{org}/').status_code, 204)
        Organization.objects.bulk_create([Organization(name=f'Page {i:02d}') for i in range(53)])
        first = self.client.get('/api/v1/organizations/').data
        second = self.client.get('/api/v1/organizations/?page=2').data
        self.assertEqual(first['count'], 54)
        self.assertEqual(first['next'], 2)
        self.assertEqual(len(first['results']), 50)
        self.assertEqual(len(second['results']), 4)
        self.assertEqual(self.client.get('/api/v1/organizations/?page=bad').status_code, 400)

    def test_full_independent_grant_matrix_and_remark_prerequisite(self):
        # Expected values come from the four independent product flags, not from
        # the implementation's selector. Cover every local/inherited combination.
        for local_values, inherited_values in itertools.product(itertools.product([False, True], repeat=4), repeat=2):
            local = dict(zip(FLAGS, local_values))
            inherited = dict(zip(FLAGS, inherited_values))
            replace_grant(self.admin, self.alice.pk, 'projects', self.project.pk, local)
            replace_grant(self.admin, self.alice.pk, 'organizations', self.org.pk, inherited)
            expected = dict(zip(FLAGS, [a or b for a, b in zip(local_values, inherited_values)]))
            self.assertEqual(effective_flags(self.alice, self.project), expected)
            self.assertEqual(can_task(self.alice, self.project), expected['task_read'])
            self.assertEqual(can_task(self.alice, self.project, write=True), expected['task_write'])
            self.assertEqual(can_remark(self.alice, self.project), expected['task_read'] and expected['remark_read'])
            self.assertEqual(can_remark(self.alice, self.project, write=True), expected['task_read'] and expected['remark_write'])
        self.assertEqual(ProjectGrant.objects.filter(user=self.alice).count(), 1)
        self.assertEqual(OrganizationGrant.objects.filter(user=self.alice).count(), 1)

    def test_unique_grants_are_enforced_by_postgresql(self):
        replace_grant(self.admin, self.alice.pk, 'projects', self.project.pk, {})
        with self.assertRaises(IntegrityError), transaction.atomic():
            ProjectGrant.objects.create(user=self.alice, project=self.project)
        replace_grant(self.admin, self.alice.pk, 'organizations', self.org.pk, {})
        with self.assertRaises(IntegrityError), transaction.atomic():
            OrganizationGrant.objects.create(user=self.alice, organization=self.org)

    def test_catalog_choices_write_only_inheritance_and_admin_data_boundary(self):
        self.assertFalse(can_task(self.admin, self.project))
        self.assertFalse(selectable_projects(self.admin).exists())
        replace_grant(self.admin, self.alice.pk, 'projects', self.project.pk, {'task_write': True})
        self.login(self.alice)
        response = self.client.get('/api/v1/projects/')
        self.assertEqual([row['id'] for row in response.data['results']], [str(self.project.pk)])
        self.assertFalse(response.data['results'][0]['permissions']['task_read'])
        self.assertTrue(response.data['results'][0]['permissions']['task_write'])
        replace_grant(self.admin, self.alice.pk, 'projects', self.project.pk, {})
        self.assertEqual(self.client.get(f'/api/v1/projects/{self.project.pk}/').status_code, 404)
        self.assertEqual(self.client.get('/api/v1/projects/').data['results'], [])
        replace_grant(self.admin, self.alice.pk, 'organizations', self.org.pk, {'task_read': True})
        self.assertEqual(len(self.client.get('/api/v1/projects/').data['results']), 1)
        self.assertEqual(len(self.client.get('/api/v1/organizations/').data['results']), 1)
        other = save_organization(self.admin, {'name': 'Hidden'})
        self.assertEqual(self.client.get(f'/api/v1/organizations/{other.pk}/').status_code, 404)

    def test_timesheet_flags_self_exception_and_report_project_boundary(self):
        for read, write in itertools.product([False, True], repeat=2):
            update_account(self.admin, self.alice.pk, {'read_others_timesheets': read, 'write_others_timesheets': write})
            self.assertTrue(can_timesheet(self.alice, self.alice.pk))
            self.assertTrue(can_timesheet(self.alice, self.alice.pk, write=True))
            self.assertEqual(can_timesheet(self.alice, self.admin.pk), read)
            self.assertEqual(can_timesheet(self.alice, self.admin.pk, write=True), write)
            self.assertFalse(can_report(self.alice, self.project, self.admin.pk))
        replace_grant(self.admin, self.alice.pk, 'projects', self.project.pk, {'task_read': True})
        self.assertTrue(can_report(self.alice, self.project, self.admin.pk))
        update_account(self.admin, self.alice.pk, {'read_others_timesheets': False, 'write_others_timesheets': True})
        self.assertFalse(can_report(self.alice, self.project, self.admin.pk))
        self.assertTrue(can_report(self.alice, self.project, self.alice.pk))

    def test_seed_repeatedly_restores_fixture_state(self):
        # Foundation's seed test separately covers the three-user count from empty.
        call_command('seed_test_data', stdout=StringIO())
        alice = User.objects.get(email='alice@example.test')
        update_account(self.admin, alice.pk, {'is_active': False, 'write_others_timesheets': True})
        call_command('seed_test_data', stdout=StringIO())
        alice.refresh_from_db()
        self.assertTrue(alice.is_active)
        self.assertFalse(alice.write_others_timesheets)
        self.assertTrue(alice.check_password('synthetic-test-only-password'))
        self.assertEqual(Timesheet.objects.count(), User.objects.count())


class MigrationUpgradeTests(TransactionTestCase):
    def test_existing_stage2_users_receive_timesheets_without_account_changes(self):
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        # Remove only new Stage 3 apps; accounts/core/auth/sessions stay at their
        # existing migration heads. This is an isolated runner-created database.
        old = [('access', None), ('projects', None), ('timesheets', None), ('accounts', '0001_initial')]
        try:
            executor.migrate(old)
            state = executor.loader.project_state([('accounts', '0001_initial'), ('core', '0002_seed_mutation_lock')])
            OldUser = state.apps.get_model('accounts', 'User')
            legacy = OldUser.objects.create(email='legacy@example.test', password='existing-hash', display_name='Legacy', is_admin=True)
            executor = MigrationExecutor(connection)
            executor.migrate(latest)
            user = User.objects.get(pk=legacy.pk)
            self.assertEqual(user.password, 'existing-hash')
            self.assertEqual(user.display_name, 'Legacy')
            self.assertTrue(user.is_admin)
            self.assertEqual(Timesheet.objects.get(user=user).revision, 0)
        finally:
            MigrationExecutor(connection).migrate(latest)


class ConcurrentAdministrationTests(TransactionTestCase):
    def setUp(self):
        MutationLock.objects.get_or_create(key='domain')

    def worker(self, operation):
        close_old_connections()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET lock_timeout = '5s'")
            return operation()
        finally:
            connection.close()

    def test_bootstrap_command_creates_validated_account_and_sheet(self):
        output = StringIO()
        with patch('accounts.management.commands.bootstrap_admin.getpass', return_value=PASSWORD):
            call_command('bootstrap_admin', email='first@example.test', display_name='First', stdout=output)
        user = User.objects.get(email='first@example.test')
        self.assertTrue(user.is_admin)
        self.assertTrue(user.check_password(PASSWORD))
        self.assertTrue(Timesheet.objects.filter(user=user).exists())
        self.assertNotIn(PASSWORD, output.getvalue())

    def test_competing_bootstraps_create_exactly_one_admin_and_sheet(self):
        gate = Barrier(2)
        def attempt(email):
            gate.wait(timeout=5)
            try:
                bootstrap_admin({'email': email, 'password': PASSWORD})
                return 'created'
            except DomainError as error:
                return error.code
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda email: self.worker(lambda: attempt(email)), ['one@example.test', 'two@example.test']))
        self.assertCountEqual(results, ['created', 'bootstrap_unavailable'])
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(Timesheet.objects.count(), 1)

    def test_waiting_write_checks_admin_after_revocation_commits(self):
        admin = bootstrap_admin({'email': 'admin@example.test', 'password': PASSWORD})
        pool = ThreadPoolExecutor(max_workers=1)
        try:
            with transaction.atomic():
                MutationLock.objects.select_for_update().get(pk='domain')
                User.objects.filter(pk=admin.pk).update(is_admin=False)
                def waiting_write():
                    with connection.cursor() as cursor:
                        cursor.execute("SET application_name = 'stage3_waiting_writer'")
                    try:
                        save_organization(admin, {'name': 'Forbidden after revoke'})
                        return 'created'
                    except DomainError as error:
                        return error.code
                future = pool.submit(self.worker, waiting_write)
                deadline = time.monotonic() + 5
                while True:
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT pg_stat_clear_snapshot()")
                        cursor.execute("SELECT count(*) FROM pg_stat_activity WHERE application_name='stage3_waiting_writer' AND wait_event_type='Lock'")
                        if cursor.fetchone()[0]:
                            break
                    self.assertLess(time.monotonic(), deadline, 'Writer did not wait on domain lock')
                    time.sleep(0.02)
            self.assertEqual(future.result(timeout=6), 'permission_denied')
            self.assertFalse(Organization.objects.exists())
        finally:
            pool.shutdown(wait=True)

    def test_competing_grant_replacements_preserve_unique_row(self):
        admin = bootstrap_admin({'email': 'admin@example.test', 'password': PASSWORD})
        user = create_account(admin, {'email': 'alice@example.test', 'password': PASSWORD})
        org = save_organization(admin, {'name': 'Studio'})
        project = save_project(admin, {'name': 'Website', 'organization': str(org.pk)})
        gate = Barrier(2)
        values = [{'task_read': True}, {'task_write': True}]
        def write(data):
            gate.wait(timeout=5)
            replace_grant(admin, user.pk, 'projects', project.pk, data)
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda data: self.worker(lambda: write(data)), values))
        self.assertEqual(ProjectGrant.objects.count(), 1)
        grant = ProjectGrant.objects.get()
        self.assertNotEqual(grant.task_read, grant.task_write)
        self.assertFalse(grant.remark_read)
        self.assertFalse(grant.remark_write)
