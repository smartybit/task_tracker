import itertools
import time
from concurrent.futures import ThreadPoolExecutor
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient

from access.models import OrganizationGrant, ProjectGrant
from accounts.services import bootstrap_admin, create_account, recover_account, update_account
from core.domain import DomainError
from core.models import MutationLock
from projects.services import save_organization, save_project
from timesheets.models import Timesheet

User = get_user_model()
PASSWORD = 'stage-nine-original-long-password'
REPLACEMENT = 'stage-nine-replacement-long-password'


class AdministratorLifecycleTests(TestCase):
    def setUp(self):
        self.admin = bootstrap_admin({'email': 'admin@example.test', 'password': PASSWORD})
        self.user = create_account(self.admin, {'email': 'person@example.test', 'password': PASSWORD})

    def login(self, user, password=PASSWORD):
        client = APIClient(enforce_csrf_checks=True)
        token = client.get('/api/v1/auth/csrf/').json()['csrf_token']
        response = client.post('/api/v1/auth/login/', {'email': user.email, 'password': password},
                               format='json', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200, response.data)
        client.credentials(HTTP_X_CSRFTOKEN=response.json()['csrf_token'])
        return client

    def command(self, email=None, password=REPLACEMENT, **options):
        output = StringIO()
        with patch('accounts.management.commands.reset_password.getpass', return_value=password):
            call_command('reset_password', email=email or self.user.email, stdout=output, **options)
        self.assertNotIn(password, output.getvalue())
        return output.getvalue()

    def test_self_protection_api_is_atomic_with_or_without_other_administrators(self):
        client = self.login(self.admin)
        for other_admin in (False, True):
            if other_admin:
                create_account(self.admin, {'email': 'other@example.test', 'password': PASSWORD, 'is_admin': True})
            for fields in ({'is_active': False}, {'is_admin': False}, {'is_active': False, 'is_admin': False}):
                with self.subTest(other_admin=other_admin, fields=fields):
                    revision = MutationLock.objects.get(pk='domain').revision
                    response = client.patch(f'/api/v1/users/{self.admin.pk}/',
                                            {**fields, 'display_name': 'Must roll back'}, format='json')
                    self.assertEqual(response.status_code, 400, response.data)
                    self.assertEqual(response.data['code'], 'self_protection')
                    self.admin.refresh_from_db()
                    self.assertTrue(self.admin.is_active)
                    self.assertTrue(self.admin.is_admin)
                    self.assertEqual(self.admin.display_name, '')
                    self.assertEqual(self.admin.session_version, 0)
                    self.assertEqual(MutationLock.objects.get(pk='domain').revision, revision)
                    self.assertEqual(client.get('/api/v1/auth/me/').status_code, 200)

    def test_self_can_edit_other_fields_and_keep_protected_flags(self):
        client = self.login(self.admin)
        response = client.patch(f'/api/v1/users/{self.admin.pk}/', {
            'display_name': 'My new name', 'is_admin': True, 'is_active': True,
            'write_others_timesheets': True,
        }, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(client.get('/api/v1/auth/me/').data['display_name'], 'My new name')

    def test_other_administrator_can_be_deactivated_reactivated_and_demoted(self):
        other = create_account(self.admin, {'email': 'other@example.test', 'password': PASSWORD, 'is_admin': True})
        old_session = self.login(other)
        client = self.login(self.admin)
        for values in ({'is_active': False}, {'is_active': True}, {'is_admin': False}):
            response = client.patch(f'/api/v1/users/{other.pk}/', values, format='json')
            self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(old_session.get('/api/v1/auth/me/').status_code, 403)
        new_session = self.login(other)
        self.assertEqual(new_session.get('/api/v1/users/').status_code, 403)

    def test_direct_service_also_rejects_self_changes(self):
        for field in ('is_admin', 'is_active'):
            with self.assertRaises(DomainError) as caught:
                update_account(self.admin, self.admin.pk, {field: False})
            self.assertEqual(caught.exception.code, 'self_protection')

    def test_server_reset_preserves_all_active_and_admin_status_combinations(self):
        for active, admin in itertools.product((False, True), repeat=2):
            with self.subTest(active=active, admin=admin):
                User.objects.filter(pk=self.user.pk).update(is_active=active, is_admin=admin)
                output = self.command(email=' PERSON@EXAMPLE.TEST ')
                self.user.refresh_from_db()
                self.assertEqual((self.user.is_active, self.user.is_admin), (active, admin))
                self.assertTrue(self.user.check_password(REPLACEMENT))
                self.assertNotEqual(self.user.password, REPLACEMENT)
                self.assertIn(f'Account is {"active" if active else "inactive"}', output)
                self.assertIn(f'administrator: {"yes" if admin else "no"}', output)

    def test_recovery_options_independent_and_combined_without_active_admin(self):
        organization = save_organization(self.admin, {'name': 'Recovery catalog'})
        save_project(self.admin, {'name': 'No implicit data access', 'organization': str(organization.pk)})
        User.objects.filter(pk=self.admin.pk).update(is_active=False)
        sheet_id = Timesheet.objects.get(user=self.user).pk
        for reactivate, grant_admin in ((True, False), (False, True), (True, True)):
            with self.subTest(reactivate=reactivate, grant_admin=grant_admin):
                User.objects.filter(pk=self.user.pk).update(is_active=False, is_admin=False)
                self.command(reactivate=reactivate, grant_admin=grant_admin)
                self.user.refresh_from_db()
                self.assertEqual((self.user.is_active, self.user.is_admin), (reactivate, grant_admin))
                self.assertEqual(Timesheet.objects.get(user=self.user).pk, sheet_id)
                self.assertFalse(self.user.read_others_timesheets)
                self.assertFalse(self.user.write_others_timesheets)
                self.assertFalse(ProjectGrant.objects.exists())
                self.assertFalse(OrganizationGrant.objects.exists())
                if reactivate:
                    client = self.login(self.user, REPLACEMENT)
                    projects = client.get('/api/v1/projects/').data
                    self.assertEqual(projects['count'], 1 if grant_admin else 0)
                    for project in projects['results']:
                        self.assertFalse(any(project['permissions'].values()))
                    self.assertEqual(client.get('/api/v1/users/').status_code, 200 if grant_admin else 403)
        self.assertEqual(User.objects.count(), 2)

    def test_server_reset_preserves_existing_permissions_and_timesheet(self):
        organization = save_organization(self.admin, {'name': 'Existing access'})
        grant = OrganizationGrant.objects.create(user=self.user, organization=organization, task_read=True)
        User.objects.filter(pk=self.user.pk).update(read_others_timesheets=True, write_others_timesheets=True)
        sheet = Timesheet.objects.get(user=self.user)
        Timesheet.objects.filter(pk=sheet.pk).update(revision=7)
        self.command(reactivate=True, grant_admin=True)
        self.user.refresh_from_db()
        self.assertTrue(self.user.read_others_timesheets)
        self.assertTrue(self.user.write_others_timesheets)
        grant.refresh_from_db()
        self.assertTrue(grant.task_read)
        self.assertFalse(grant.task_write)
        self.assertFalse(grant.remark_read)
        self.assertFalse(grant.remark_write)
        self.assertEqual(Timesheet.objects.get(user=self.user).pk, sheet.pk)
        self.assertEqual(Timesheet.objects.get(user=self.user).revision, 7)

    def test_reset_invalidates_password_and_all_existing_sessions(self):
        clients = [self.login(self.user), self.login(self.user)]
        self.command()
        for client in clients:
            self.assertEqual(client.get('/api/v1/auth/me/').status_code, 403)
        token = clients[0].get('/api/v1/auth/csrf/').data['csrf_token']
        response = clients[0].post('/api/v1/auth/login/', {'email': self.user.email, 'password': PASSWORD},
                                   format='json', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.data['code'], 'invalid_credentials')
        self.assertEqual(self.login(self.user, REPLACEMENT).get('/api/v1/auth/me/').status_code, 200)

    def test_recovery_does_not_revive_sessions_from_before_deactivation(self):
        old_session = self.login(self.user)
        update_account(self.admin, self.user.pk, {'is_active': False})
        self.command(reactivate=True, grant_admin=True)
        self.assertEqual(old_session.get('/api/v1/auth/me/').status_code, 403)
        self.assertEqual(self.login(self.user, REPLACEMENT).get('/api/v1/users/').status_code, 200)

    def test_command_rejects_mismatch_invalid_password_and_unknown_user_atomically(self):
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        before = User.objects.values().get(pk=self.user.pk)
        revision = MutationLock.objects.get(pk='domain').revision
        with patch('accounts.management.commands.reset_password.getpass', side_effect=[REPLACEMENT, 'different']):
            with self.assertRaisesMessage(CommandError, 'Passwords do not match'):
                call_command('reset_password', email=self.user.email, reactivate=True, grant_admin=True)
        for email, password in ((self.user.email, '123'), ('missing@example.test', REPLACEMENT)):
            with self.subTest(email=email), self.assertRaises(CommandError):
                self.command(email=email, password=password, reactivate=True, grant_admin=True)
        self.assertEqual(User.objects.values().get(pk=self.user.pk), before)
        self.assertEqual(MutationLock.objects.get(pk='domain').revision, revision)
        self.assertEqual(User.objects.count(), 2)
        self.assertEqual(Timesheet.objects.count(), 2)

    def test_recovery_storage_failure_rolls_back_password_statuses_and_revision(self):
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        before = User.objects.values().get(pk=self.user.pk)
        revision = MutationLock.objects.get(pk='domain').revision
        real_save = User.save
        def fail_after_save(user, *args, **kwargs):
            real_save(user, *args, **kwargs)
            raise IntegrityError('injected private storage failure')
        with patch.object(User, 'save', fail_after_save), self.assertRaises(DomainError) as caught:
            recover_account(self.user.email, REPLACEMENT, reactivate=True, grant_admin=True)
        self.assertEqual(caught.exception.code, 'conflict')
        self.assertEqual(User.objects.values().get(pk=self.user.pk), before)
        self.assertEqual(MutationLock.objects.get(pk='domain').revision, revision)


class ConcurrentAccountLifecycleTests(TransactionTestCase):
    def setUp(self):
        MutationLock.objects.get_or_create(key='domain')
        self.admin = bootstrap_admin({'email': 'admin@example.test', 'password': PASSWORD})
        self.other = create_account(self.admin, {'email': 'other@example.test', 'password': PASSWORD, 'is_admin': True})

    def worker(self, operation):
        close_old_connections()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET lock_timeout = '8s'")
                cursor.execute("SET application_name = 'stage9_waiting_account'")
            try:
                operation()
                return 'saved'
            except DomainError as error:
                return error.code
        finally:
            connection.close()

    def wait_for_writer(self):
        deadline = time.monotonic() + 5
        while True:
            with connection.cursor() as cursor:
                cursor.execute('SELECT pg_stat_clear_snapshot()')
                cursor.execute("SELECT count(*) FROM pg_stat_activity WHERE application_name='stage9_waiting_account' AND wait_event_type='Lock'")
                if cursor.fetchone()[0]:
                    return
            self.assertLess(time.monotonic(), deadline, 'Account writer did not wait on the domain lock')
            time.sleep(0.02)

    def test_waiting_account_update_rechecks_demotion_and_deactivation(self):
        for field, expected in (('is_admin', 'permission_denied'), ('is_active', 'authentication_required')):
            with self.subTest(field=field), ThreadPoolExecutor(max_workers=1) as pool:
                User.objects.filter(pk=self.admin.pk).update(is_admin=True, is_active=True)
                with transaction.atomic():
                    MutationLock.objects.select_for_update().get(pk='domain')
                    update_account(self.other, self.admin.pk, {field: False})
                    revision = MutationLock.objects.get(pk='domain').revision
                    future = pool.submit(self.worker, lambda: update_account(self.admin, self.other.pk, {'display_name': 'Unauthorized'}))
                    self.wait_for_writer()
                self.assertEqual(future.result(timeout=10), expected)
                self.other.refresh_from_db()
                self.assertEqual(self.other.display_name, '')
                self.assertEqual(MutationLock.objects.get(pk='domain').revision, revision)

    def test_waiting_recovery_preserves_status_changes_committed_before_its_lock(self):
        with ThreadPoolExecutor(max_workers=1) as pool:
            with transaction.atomic():
                MutationLock.objects.select_for_update().get(pk='domain')
                update_account(self.admin, self.other.pk, {'is_active': False, 'is_admin': False})
                future = pool.submit(self.worker, lambda: recover_account(self.other.email, REPLACEMENT))
                self.wait_for_writer()
            self.assertEqual(future.result(timeout=10), 'saved')
        self.other.refresh_from_db()
        self.assertFalse(self.other.is_active)
        self.assertFalse(self.other.is_admin)
        self.assertTrue(self.other.check_password(REPLACEMENT))
