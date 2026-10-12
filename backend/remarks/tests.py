import itertools
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.db import close_old_connections, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient

from access.models import ProjectGrant
from access.policies import FLAGS
from access.services import replace_grant
from core.domain import DomainError
from core.models import MutationLock
from remarks.models import Remark
from remarks.services import change_remark
from tasks.models import Task
from tasks.services import change_task, preview_task
from tasks.tests import PASSWORD, TaskFixtures


class RemarkFixtures(TaskFixtures):
    def setup_remarks(self):
        self.setup_tasks()
        self.task = self.create('Discussion task')
        for user in (self.alice, self.bob):
            replace_grant(self.admin, user.pk, 'projects', self.project.pk, dict.fromkeys(FLAGS, True))

    def post(self, actor=None, body='First remark\nВторая строка <script>alert(1)</script>'):
        result = change_remark(actor or self.alice, 'create', {'body': body}, self.task.pk)
        return Remark.objects.get(pk=result['id'])


class RemarksTests(RemarkFixtures, TestCase):
    def setUp(self):
        self.setup_remarks()
        self.client = APIClient(enforce_csrf_checks=True)

    def login(self, actor):
        token = self.client.get('/api/v1/auth/csrf/').json()['csrf_token']
        response = self.client.post('/api/v1/auth/login/', {'email': actor.email, 'password': PASSWORD},
                                    format='json', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200)
        self.client.credentials(HTTP_X_CSRFTOKEN=response.data['csrf_token'])

    def test_create_edit_shared_star_and_delete_preserve_authorship(self):
        self.login(self.alice)
        response = self.client.post(f'/api/v1/tasks/{self.task.pk}/remarks/', {'body': '  Text\nТекст  '}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        first = response.data
        self.assertEqual(first['body'], '  Text\nТекст  ')
        self.assertEqual(first['author'], str(self.alice.pk))
        self.assertIsNone(first['edited_at'])
        self.login(self.bob)
        path = f"/api/v1/remarks/{first['id']}/"
        edited = self.client.patch(path, {'body': 'Edited by colleague', 'expected_revision': 0}, format='json')
        self.assertEqual(edited.status_code, 200, edited.data)
        self.assertEqual(edited.data['author'], first['author'])
        self.assertEqual(edited.data['created_at'], first['created_at'])
        self.assertIsNotNone(edited.data['edited_at'])
        starred = self.client.post(f'{path}star/', {'starred': True, 'expected_revision': 1}, format='json')
        self.assertEqual(starred.status_code, 200, starred.data)
        self.assertEqual(starred.data['edited_at'], edited.data['edited_at'])
        self.assertEqual(starred.data['revision'], 2)
        self.login(self.alice)
        rows = self.client.get(f'/api/v1/tasks/{self.task.pk}/remarks/', {'starred': 'true'})
        self.assertEqual(rows.data['results'][0]['id'], first['id'])
        self.assertEqual(self.client.delete(path, {'expected_revision': 2}, format='json').status_code, 200)
        self.assertEqual(self.client.get(path).status_code, 404)
        self.assertFalse(Remark.objects.exists())

    def test_all_local_inherited_flag_combinations_gate_real_endpoints(self):
        remark = self.post(body='Protected discussion content')
        path = f'/api/v1/remarks/{remark.pk}/'
        self.login(self.bob)
        for bits in itertools.product([False, True], repeat=8):
            with self.subTest(bits=bits):
                local, inherited = dict(zip(FLAGS, bits[:4])), dict(zip(FLAGS, bits[4:]))
                replace_grant(self.admin, self.bob.pk, 'projects', self.project.pk, local)
                replace_grant(self.admin, self.bob.pk, 'organizations', self.project.organization_id, inherited)
                read_task = local['task_read'] or inherited['task_read']
                read = read_task and (local['remark_read'] or inherited['remark_read'])
                write = read_task and (local['remark_write'] or inherited['remark_write'])
                for url in (path, f'/api/v1/tasks/{self.task.pk}/remarks/'):
                    response = self.client.get(url)
                    self.assertEqual(response.status_code, 200 if read else 404)
                    if not read:
                        self.assertNotIn('Protected discussion content', str(response.data))
                remark.refresh_from_db()
                revision = remark.revision
                for url, method, data in [
                    (path, 'patch', {'body': 'Protected discussion content', 'expected_revision': revision}),
                    (f'{path}star/', 'post', {'starred': True, 'expected_revision': revision + int(write)}),
                    (f'/api/v1/tasks/{self.task.pk}/remarks/', 'post', {'body': 'New protected text'}),
                ]:
                    response = getattr(self.client, method)(url, data, format='json')
                    self.assertEqual(response.status_code, (201 if url.endswith('/remarks/') else 200) if write else 403)
                    if write and not read:
                        self.assertEqual(set(response.data), {'id', 'revision'})
                    if url.endswith('/remarks/') and write:
                        deleted = self.client.delete(f"/api/v1/remarks/{response.data['id']}/", {'expected_revision': 0}, format='json')
                        self.assertEqual(deleted.status_code, 200)
                # Delete denial must not require remark read, ownership, or task write.
                if not write:
                    denied = self.client.delete(path, {'expected_revision': revision}, format='json')
                    self.assertEqual(denied.status_code, 403)
        self.login(self.admin)
        self.assertEqual(self.client.get(path).status_code, 404)
        self.assertEqual(self.client.patch(path, {'body': 'Admin bypass', 'expected_revision': remark.revision}, format='json').status_code, 403)

    def test_validation_csrf_stale_commands_and_failure_are_atomic(self):
        remark = self.post()
        self.login(self.alice)
        path = f'/api/v1/remarks/{remark.pk}/'
        self.client.credentials()
        self.assertEqual(self.client.post(f'{path}star/', {'starred': True, 'expected_revision': 0}, format='json').status_code, 403)
        self.login(self.alice)
        before = MutationLock.objects.get(pk='domain').revision
        for payload in ({'body': ''}, {'body': ' \n '}, {'body': 'Valid', 'author': str(self.bob.pk)}, {'body': 'Valid', 'task': str(self.task.pk)}, ['bad'], 'bad', 42):
            response = self.client.post(f'/api/v1/tasks/{self.task.pk}/remarks/', payload, format='json')
            self.assertEqual(response.status_code, 400, response.data)
        for payload in ({'body': 'Missing revision'}, {'body': 'Bad revision', 'expected_revision': -1}):
            self.assertEqual(self.client.patch(path, payload, format='json').status_code, 400)
        self.assertEqual(MutationLock.objects.get(pk='domain').revision, before)
        change_remark(self.bob, 'star', {'starred': True, 'expected_revision': 0}, remark.pk)
        before = MutationLock.objects.get(pk='domain').revision
        for method, url, data in [('patch', path, {'body': 'Stale', 'expected_revision': 0}),
                                  ('post', f'{path}star/', {'starred': False, 'expected_revision': 0}),
                                  ('delete', path, {'expected_revision': 0})]:
            response = getattr(self.client, method)(url, data, format='json')
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.data['code'], 'stale_revision')
        original_save = Remark.save
        def failed_save(instance, *args, **kwargs):
            original_save(instance, *args, **kwargs)
            raise RuntimeError('Synthetic storage failure')
        with patch.object(Remark, 'save', failed_save), self.assertRaises(RuntimeError):
            change_remark(self.alice, 'edit', {'body': 'Lost edit', 'expected_revision': 1}, remark.pk)
        remark.refresh_from_db()
        self.assertIn('First remark', remark.body)
        self.assertIsNone(remark.edited_at)
        self.assertEqual(remark.revision, 1)
        self.assertEqual(MutationLock.objects.get(pk='domain').revision, before)

    def test_chronology_pagination_star_stream_and_task_isolation(self):
        fixed = timezone.now()
        rows = Remark.objects.bulk_create([Remark(task=self.task, author=self.alice, body=f'Remark {i}', starred=i in {0, 50}) for i in range(51)])
        Remark.objects.filter(task=self.task).update(created_at=fixed)
        other = self.create('Other discussion')
        Remark.objects.create(task=other, author=self.bob, body='Other task content', starred=True)
        self.login(self.alice)
        path = f'/api/v1/tasks/{self.task.pk}/remarks/'
        first, last = self.client.get(path), self.client.get(path, {'page': 2})
        self.assertEqual(first.data['count'], 51)
        self.assertEqual(first.data['next'], 2)
        self.assertIsNone(last.data['next'])
        ids = [row['id'] for row in first.data['results'] + last.data['results']]
        self.assertEqual(ids, sorted(str(row.pk) for row in rows))
        stars = self.client.get(path, {'starred': 'true'})
        self.assertEqual(stars.data['count'], 2)
        self.assertEqual({row['body'] for row in stars.data['results']}, {'Remark 0', 'Remark 50'})
        self.assertEqual(self.client.get(path, {'page': 0}).status_code, 400)

    def test_task_deletion_requires_content_write_and_previews_only_counts(self):
        remark = self.post()
        for flags in ({'task_write': True}, {'task_read': True, 'task_write': True},
                      {'task_read': True, 'task_write': True, 'remark_read': True}):
            replace_grant(self.admin, self.alice.pk, 'projects', self.project.pk, flags)
            with self.assertRaises(DomainError) as denied:
                preview_task(self.alice, 'delete', {'expected_revision': 0}, self.task.pk)
            self.assertEqual(denied.exception.code, 'permission_denied')
        replace_grant(self.admin, self.alice.pk, 'projects', self.project.pk,
                      {'task_read': True, 'task_write': True, 'remark_write': True})
        preview = preview_task(self.alice, 'delete', {'expected_revision': 0}, self.task.pk)
        self.assertEqual(preview['delete']['remarks'], 1)
        self.assertNotIn(remark.body, str(preview))
        change_remark(self.alice, 'star', {'starred': True, 'expected_revision': 0}, remark.pk)
        with self.assertRaises(DomainError) as stale:
            change_task(self.alice, 'delete', {'expected_revision': 0, 'expected_domain_revision': preview['domain_revision'], 'confirm': True}, self.task.pk)
        self.assertEqual(stale.exception.code, 'stale_preview')
        self.assertTrue(Remark.objects.filter(pk=remark.pk).exists())
        self.compound(self.alice, 'delete', {}, self.task)
        self.assertFalse(Remark.objects.filter(pk=remark.pk).exists())

    def test_task_move_and_live_revocation_apply_to_existing_remarks(self):
        remark = self.post()
        self.login(self.bob)
        path = f'/api/v1/remarks/{remark.pk}/'
        self.compound(self.alice, 'move', {'parent': None, 'project': str(self.other.pk)}, self.task)
        self.assertEqual(self.client.get(path).status_code, 404)
        self.assertEqual(self.client.patch(path, {'body': 'Denied', 'expected_revision': 0}, format='json').status_code, 403)
        replace_grant(self.admin, self.bob.pk, 'projects', self.other.pk, {'task_read': True, 'remark_read': True, 'remark_write': True})
        self.assertEqual(self.client.get(path).status_code, 200)
        replace_grant(self.admin, self.bob.pk, 'projects', self.other.pk, {'remark_read': True, 'remark_write': True})
        self.assertEqual(self.client.get(path).status_code, 404)
        self.assertEqual(self.client.delete(path, {'expected_revision': 0}, format='json').status_code, 403)
        self.assertTrue(Remark.objects.filter(pk=remark.pk).exists())


class ConcurrentRemarkTests(RemarkFixtures, TransactionTestCase):
    def setUp(self):
        MutationLock.objects.get_or_create(key='domain')
        self.setup_remarks()

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

    def test_competing_star_and_edit_cannot_overwrite_each_other(self):
        remark = self.post()
        results = self.race(
            lambda: change_remark(self.alice, 'edit', {'body': 'Competing edit', 'expected_revision': 0}, remark.pk),
            lambda: change_remark(self.bob, 'star', {'starred': True, 'expected_revision': 0}, remark.pk))
        self.assertCountEqual(results, ['committed', 'stale_revision'])
        remark.refresh_from_db()
        self.assertEqual(remark.revision, 1)
        self.assertNotEqual(remark.body == 'Competing edit', remark.starred)

    def test_post_races_confirmed_task_deletion_without_silent_cascade(self):
        preview = preview_task(self.alice, 'delete', {'expected_revision': 0}, self.task.pk)
        results = self.race(
            lambda: change_task(self.alice, 'delete', {'expected_revision': 0, 'expected_domain_revision': preview['domain_revision'], 'confirm': True}, self.task.pk),
            lambda: self.post())
        self.assertEqual(results.count('committed'), 1)
        self.assertEqual(Task.objects.filter(pk=self.task.pk).exists(), Remark.objects.exists())
        self.assertTrue('stale_preview' in results or 'not_found' in results)

    def test_waiting_remark_writer_rechecks_revocation(self):
        remark = self.post()
        with ThreadPoolExecutor(max_workers=1) as pool:
            with transaction.atomic():
                MutationLock.objects.select_for_update().get(pk='domain')
                ProjectGrant.objects.filter(user=self.alice, project=self.project).update(remark_write=False)
                def waiting():
                    with connection.cursor() as cursor:
                        cursor.execute("SET application_name = 'stage8_waiting_remark'")
                    change_remark(self.alice, 'edit', {'body': 'Forbidden', 'expected_revision': 0}, remark.pk)
                future = pool.submit(self.worker, waiting)
                deadline = time.monotonic() + 5
                while True:
                    with connection.cursor() as cursor:
                        cursor.execute('SELECT pg_stat_clear_snapshot()')
                        cursor.execute("SELECT count(*) FROM pg_stat_activity WHERE application_name='stage8_waiting_remark' AND wait_event_type='Lock'")
                        if cursor.fetchone()[0]:
                            break
                    self.assertLess(time.monotonic(), deadline, 'Remark writer did not wait on domain lock')
                    time.sleep(0.02)
            self.assertEqual(future.result(timeout=6), 'permission_denied')
        remark.refresh_from_db()
        self.assertIn('First remark', remark.body)
        self.assertEqual(remark.revision, 0)


class RemarkUpgradeTests(RemarkFixtures, TransactionTestCase):
    def test_stage7_upgrade_preserves_tasks_accounts_and_grants(self):
        MutationLock.objects.get_or_create(key='domain')
        self.setup_remarks()
        latest = MigrationExecutor(connection).loader.graph.leaf_nodes()
        try:
            MigrationExecutor(connection).migrate([('remarks', None)])
            self.assertEqual(Task.objects.get(pk=self.task.pk).description, 'private description')
            MigrationExecutor(connection).migrate(latest)
            self.assertEqual(Task.objects.get(pk=self.task.pk).revision, 0)
            self.assertTrue(ProjectGrant.objects.get(user=self.alice, project=self.project).remark_write)
            self.assertFalse(Remark.objects.exists())
            remark = self.post()
            self.assertEqual(remark.author_id, self.alice.pk)
        finally:
            MigrationExecutor(connection).migrate(latest)
