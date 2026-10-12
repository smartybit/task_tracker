import itertools

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient

from access.policies import FLAGS
from access.services import replace_grant
from content.search import normalized_queries
from content.search_config import search_vector
from core.models import MutationLock
from remarks.models import Remark
from remarks.services import change_remark
from remarks.tests import RemarkFixtures
from tasks.models import Task
from tasks.services import change_task


class SearchTests(RemarkFixtures, TestCase):
    def setUp(self):
        self.setup_remarks()
        self.client = APIClient()
        self.client.force_authenticate(self.alice)

    def search(self, query, **params):
        response = self.client.get('/api/v1/search/', {'q': query, **params})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        return response.data

    def test_english_russian_and_mixed_inflections_search_titles_descriptions_and_remarks(self):
        change_task(self.alice, 'edit', {'title': 'Running releases', 'description': 'Планирование задачи', 'expected_revision': 0}, self.task.pk)
        remark = self.post(body='We discussed running задачи')
        for query in ('runs', 'задачами', 'runs задачами'):
            result = self.search(query)
            self.assertEqual({(r['kind'], r['id']) for r in result['results']}, {('task', str(self.task.pk)), ('remark', str(remark.pk))})
        self.assertEqual(self.search('release')['results'][0]['id'], str(self.task.pk))
        self.assertEqual(self.search('планированием')['results'][0]['id'], str(self.task.pk))
        self.assertEqual(self.search('unrelated задачами')['count'], 0)

    def test_permissions_filter_matches_counts_and_snippets_before_returning_data(self):
        change_task(self.alice, 'edit', {'description': 'signal public description', 'expected_revision': 0}, self.task.pk)
        self.post(body='signal protected remark')
        hidden = self.create('signal HIDDEN TITLE', project=self.other)
        Remark.objects.create(task=hidden, author=self.alice, body='signal HIDDEN BODY')
        replace_grant(self.admin, self.bob.pk, 'projects', self.other.pk, {})
        self.client.force_authenticate(self.bob)
        for bits in itertools.product([False, True], repeat=4):
            flags = dict(zip(FLAGS, bits))
            replace_grant(self.admin, self.bob.pk, 'projects', self.project.pk, flags)
            result = self.search('signal')
            self.assertEqual(result['count'], int(flags['task_read']) + int(flags['task_read'] and flags['remark_read']))
            self.assertNotIn('HIDDEN', str(result))
            if not (flags['task_read'] and flags['remark_read']):
                self.assertNotIn('protected', str(result))
        replace_grant(self.admin, self.bob.pk, 'projects', self.project.pk, {})
        replace_grant(self.admin, self.bob.pk, 'organizations', self.project.organization_id,
                      {'task_read': True, 'remark_read': True})
        self.assertEqual(self.search('signal')['count'], 2)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.search('signal')['count'], 0)

    def test_stable_pagination_and_live_edit_move_deletion(self):
        rows = Task.objects.bulk_create([Task(title='Needle', description='Searchable needle', project=self.project,
                                              owner=self.alice, creator=self.alice, status=self.active) for _ in range(51)])
        first, last = self.search('needle'), self.search('needle', page=2)
        self.assertEqual(first['count'], 51)
        self.assertEqual(first['next'], 2)
        self.assertIsNone(last['next'])
        ids = [r['id'] for r in first['results'] + last['results']]
        self.assertEqual(ids, sorted(str(row.pk) for row in rows))
        change_task(self.alice, 'edit', {'title': 'Gone', 'description': '', 'expected_revision': 0}, rows[0].pk)
        self.assertEqual(self.search('needle')['count'], 50)
        replace_grant(self.admin, self.bob.pk, 'projects', self.other.pk, {})
        self.compound(self.alice, 'move', {'parent': None, 'project': str(self.other.pk)}, rows[1])
        self.client.force_authenticate(self.bob)
        self.assertEqual(self.search('needle')['count'], 49)
        self.compound(self.alice, 'delete', {}, rows[2])
        self.assertEqual(self.search('needle')['count'], 48)
        remark = self.post(body='Needle in discussion')
        self.assertEqual(self.search('needle')['count'], 49)
        change_remark(self.alice, 'edit', {'body': 'Removed keyword', 'expected_revision': 0}, remark.pk)
        self.assertEqual(self.search('needle')['count'], 48)

    def test_snippets_find_distant_words_and_exclude_reference_and_image_ids(self):
        body = 'Earlier unrelated words. ' * 150 + f'Needle <script>alert(1)</script> [task:{self.task.pk}] [image:{self.task.pk}]'
        change_task(self.alice, 'edit', {'description': body, 'expected_revision': 0}, self.task.pk)
        result = self.search('needle')
        self.assertEqual(result['count'], 1)
        snippets = result['results'][0]['snippets']
        self.assertIn('[Needle]', ' '.join(snippets))
        self.assertTrue(all(len(text) <= 500 for text in snippets))
        self.assertNotIn(str(self.task.pk), str(snippets))
        self.assertEqual(self.search(str(self.task.pk))['count'], 0)

    def test_strict_queries_stop_words_authentication_and_usable_gin_indexes(self):
        before = MutationLock.objects.get(pk='domain').revision
        for params in ({}, {'q': ''}, {'q': 'x' * 201}, {'q': 'word', 'page': 0},
                       {'q': 'word', 'page': 'bad'}, {'q': 'word', 'extra': 'bad'}):
            self.assertEqual(self.client.get('/api/v1/search/', params).status_code, 400)
        self.assertEqual(self.client.get('/api/v1/search/?q=one&q=two').status_code, 400)
        self.assertEqual(self.search('the and or')['count'], 0)
        self.assertEqual(self.search('и или')['count'], 0)
        self.assertEqual(self.search('!!!')['count'], 0)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get('/api/v1/search/', {'q': 'word'}).status_code, 403)
        self.assertEqual(MutationLock.objects.get(pk='domain').revision, before)
        with connection.cursor() as cursor:
            cursor.execute('SET LOCAL enable_seqscan = off')
        query = normalized_queries('running')['english']
        for model, fields, name in [(Task, ('title', 'description'), 'task_content_search'),
                                    (Remark, ('body',), 'remark_content_search')]:
            plan = model.objects.annotate(document=search_vector(*fields)).filter(document=query).explain()
            self.assertIn(name, plan)


class SearchUpgradeTests(RemarkFixtures, TransactionTestCase):
    def test_existing_content_is_searchable_after_index_upgrade(self):
        MutationLock.objects.get_or_create(key='domain')
        self.setup_remarks()
        remark = self.post(body='Running задачи')
        latest = MigrationExecutor(connection).loader.graph.leaf_nodes()
        try:
            MigrationExecutor(connection).migrate([('tasks', '0002_initial_statuses_and_protection'), ('remarks', '0001_initial')])
            MigrationExecutor(connection).migrate(latest)
            client = APIClient()
            client.force_authenticate(self.alice)
            response = client.get('/api/v1/search/', {'q': 'runs задачами'})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data['results'][0]['id'], str(remark.pk))
            self.assertEqual(Remark.objects.get(pk=remark.pk).revision, 0)
        finally:
            MigrationExecutor(connection).migrate(latest)
