from unittest.mock import patch
from uuid import uuid4

from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient

from access.services import replace_grant
from content.models import Reference
from content.references import resolve_references
from core.models import MutationLock
from remarks.services import change_remark
from remarks.tests import RemarkFixtures
from tasks.models import Task
from tasks.services import change_task


class ReferenceTests(RemarkFixtures, TestCase):
    def setUp(self):
        self.setup_remarks()
        self.target = self.create('Target title')
        self.remark = self.post(body='Target remark')

    def resolve(self, actor=None, targets=None):
        return resolve_references(actor or self.alice, {'targets': targets or [
            {'kind': 'task', 'id': str(self.target.pk)}, {'kind': 'remark', 'id': str(self.remark.pk)}]})['results']

    def test_source_sync_is_atomic_deduplicated_and_accepts_unavailable_targets(self):
        token = f'[task:{self.target.pk}]'
        missing = uuid4()
        body = f'{token} twice {token} [remark:{missing}]'
        change_task(self.alice, 'edit', {'description': body, 'expected_revision': 0}, self.task.pk)
        self.assertEqual(self.task.references.count(), 2)
        ids = set(self.task.references.values_list('id', flat=True))
        change_task(self.alice, 'edit', {'description': body + '!', 'expected_revision': 1}, self.task.pk)
        self.assertEqual(set(self.task.references.values_list('id', flat=True)), ids)
        change_remark(self.alice, 'edit', {'body': body, 'expected_revision': 0}, self.remark.pk)
        self.assertEqual(self.remark.references.count(), 2)
        before = MutationLock.objects.get(pk='domain').revision
        with patch('content.references.Reference.objects.bulk_create', side_effect=RuntimeError('Storage failed')):
            with self.assertRaises(RuntimeError):
                change_task(self.alice, 'edit', {'description': 'Replacement', 'expected_revision': 2}, self.task.pk)
        self.task.refresh_from_db()
        self.assertEqual(self.task.description, body + '!')
        self.assertEqual(self.task.revision, 2)
        self.assertEqual(self.task.references.count(), 2)
        self.assertEqual(MutationLock.objects.get(pk='domain').revision, before)
        change_task(self.alice, 'edit', {'description': 'Removed tokens', 'expected_revision': 2}, self.task.pk)
        self.assertFalse(self.task.references.exists())
        change_remark(self.alice, 'delete', {'expected_revision': 1}, self.remark.pk)
        self.assertFalse(Reference.objects.filter(source_remark_id=self.remark.pk).exists())

    def test_rename_move_revocation_and_deletion_resolve_using_current_access(self):
        self.assertTrue(all(row['available'] for row in self.resolve()))
        body = f'[task:{self.target.pk}] [remark:{self.remark.pk}]'
        source = self.post(body=body)
        change_task(self.alice, 'edit', {'title': 'Renamed target', 'expected_revision': 0}, self.target.pk)
        self.assertEqual(self.resolve()[0]['label'], 'Renamed target')
        self.compound(self.alice, 'move', {'parent': None, 'project': str(self.other.pk)}, self.target)
        replace_grant(self.admin, self.bob.pk, 'projects', self.other.pk, {})
        denied = self.resolve(self.bob)[0]
        self.assertEqual(denied, {'kind': 'task', 'id': str(self.target.pk), 'available': False, 'label': 'Unavailable reference'})
        replace_grant(self.admin, self.bob.pk, 'projects', self.other.pk, {'task_read': True})
        self.assertTrue(self.resolve(self.bob)[0]['available'])
        replace_grant(self.admin, self.bob.pk, 'projects', self.project.pk, {'task_read': True, 'remark_write': True})
        self.assertFalse(self.resolve(self.bob)[1]['available'])
        self.assertTrue(all(not row['available'] for row in self.resolve(self.admin)))
        self.compound(self.alice, 'delete', {}, self.target)
        self.assertEqual(self.resolve()[0], denied)
        change_remark(self.alice, 'delete', {'expected_revision': 0}, self.remark.pk)
        self.assertFalse(self.resolve()[1]['available'])
        source.refresh_from_db()
        self.assertEqual(source.body, body)
        self.assertEqual(source.references.count(), 2)

    def test_resolver_is_authenticated_strict_bounded_and_does_not_mutate(self):
        client = APIClient()
        path = '/api/v1/references/resolve/'
        self.assertEqual(client.post(path, {'targets': []}, format='json').status_code, 403)
        client.force_authenticate(self.alice)
        before = MutationLock.objects.get(pk='domain').revision
        for payload in ([], {'targets': [{'kind': 'other', 'id': str(uuid4())}]},
                        {'targets': [{'kind': 'task', 'id': 'bad'}]},
                        {'targets': [{'kind': 'task', 'id': str(uuid4()), 'label': 'forged'}]},
                        {'targets': [{'kind': 'task', 'id': str(uuid4())}] * 101}):
            self.assertEqual(client.post(path, payload, format='json').status_code, 400)
        result = client.post(path, {'targets': [{'kind': 'task', 'id': str(self.target.pk)}]}, format='json')
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.data['results'][0]['label'], 'Target title')
        self.assertEqual(MutationLock.objects.get(pk='domain').revision, before)

    def test_database_enforces_single_source_valid_kind_and_unique_targets(self):
        for fields in ({}, {'source_task': self.task, 'source_remark': self.remark},
                       {'source_task': self.task, 'target_kind': 'other'}):
            with self.assertRaises(IntegrityError), transaction.atomic():
                Reference.objects.create(**({'target_kind': 'task', 'target_id': self.target.pk} | fields))
        Reference.objects.create(source_task=self.task, target_kind='task', target_id=self.target.pk)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Reference.objects.create(source_task=self.task, target_kind='task', target_id=self.target.pk)


class ReferenceUpgradeTests(RemarkFixtures, TransactionTestCase):
    def test_existing_tokens_are_backfilled_without_changing_content_or_revisions(self):
        MutationLock.objects.get_or_create(key='domain')
        self.setup_remarks()
        remark = self.post(body=f'[task:{self.task.pk}]')
        body = f'[remark:{remark.pk}] [remark:{remark.pk}]'
        Task.objects.filter(pk=self.task.pk).update(description=body)
        latest = MigrationExecutor(connection).loader.graph.leaf_nodes()
        try:
            MigrationExecutor(connection).migrate([('content', None)])
            MigrationExecutor(connection).migrate(latest)
            self.assertEqual(self.task.references.count(), 1)
            self.assertEqual(remark.references.count(), 1)
            self.task.refresh_from_db()
            self.assertEqual(self.task.description, body)
            self.assertEqual(self.task.revision, 0)
        finally:
            MigrationExecutor(connection).migrate(latest)
