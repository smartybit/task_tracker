import time
from concurrent.futures import ThreadPoolExecutor

from django.db import close_old_connections, connection, transaction
from django.test import TransactionTestCase
from rest_framework.test import APIClient

from access.models import ProjectGrant
from core.models import MutationLock
from remarks.tests import RemarkFixtures
from tasks.services import change_task


class ConcurrentSearchTests(RemarkFixtures, TransactionTestCase):
    def test_waiting_search_rechecks_committed_revocation_before_counting_or_snippets(self):
        MutationLock.objects.get_or_create(key='domain')
        self.setup_remarks()
        change_task(self.alice, 'edit', {'description': 'Needle private task', 'expected_revision': 0}, self.task.pk)
        self.post(body='Needle protected discussion')
        def search():
            close_old_connections()
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET application_name = 'stage8_waiting_search'")
                    cursor.execute("SET lock_timeout = '5s'")
                client = APIClient()
                client.force_authenticate(self.bob)
                response = client.get('/api/v1/search/', {'q': 'needle'})
                return response.status_code, response.data
            finally:
                connection.close()
        with ThreadPoolExecutor(max_workers=1) as pool:
            with transaction.atomic():
                MutationLock.objects.select_for_update().get(pk='domain')
                ProjectGrant.objects.filter(user=self.bob, project=self.project).update(task_read=False)
                future = pool.submit(search)
                deadline = time.monotonic() + 5
                while True:
                    with connection.cursor() as cursor:
                        cursor.execute('SELECT pg_stat_clear_snapshot()')
                        cursor.execute("SELECT count(*) FROM pg_stat_activity WHERE application_name='stage8_waiting_search' AND wait_event_type='Lock'")
                        if cursor.fetchone()[0]:
                            break
                    self.assertLess(time.monotonic(), deadline, 'Search did not wait on domain lock')
                    time.sleep(0.02)
            status, data = future.result(timeout=6)
            self.assertEqual(status, 200)
            self.assertEqual(data, {'count': 0, 'next': None, 'results': []})
