from io import BytesIO

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.handlers.wsgi import WSGIHandler
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse, set_script_prefix
from rest_framework.test import APIClient

from config.instance import instance_config


class InstanceConfigurationTests(TestCase):
    def test_default_and_nested_configuration_and_invalid_values(self):
        self.assertEqual(instance_config({}), ('/', 'task-tracker-dev', False))
        self.assertEqual(instance_config({'APP_BASE_PATH': '/team/test', 'INSTANCE_ID': 'prefix-a',
                                          'DJANGO_COOKIE_SECURE': 'true'}), ('/team/test/', 'prefix-a', True))
        for path in ('', 'relative/', '//other/', '/a//b', '/./', '/../', '/a\\b', '/a%2fb',
                     '/a?b', '/a#b', '/a b', '/a/\n', 'https://other/'):
            with self.subTest(path=path), self.assertRaises(ImproperlyConfigured):
                instance_config({'APP_BASE_PATH': path})
        for identifier in ('', '-leading', 'Upper', 'a_b', 'a' * 64, 'a\n'):
            with self.subTest(identifier=identifier), self.assertRaises(ImproperlyConfigured):
                instance_config({'INSTANCE_ID': identifier})
        with self.assertRaises(ImproperlyConfigured):
            instance_config({'DJANGO_COOKIE_SECURE': 'yes'})

    def test_root_health_contract_and_instance_headers(self):
        response = APIClient().get('/api/v1/health/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['X-Task-Tracker-Base-Path'], settings.APP_BASE_PATH)
        self.assertEqual(response['X-Task-Tracker-Instance'], settings.INSTANCE_ID)
        self.assertEqual(response.json(), {'status': 'ok', 'database': 'postgresql', 'api_version': 'v1'})


class InstanceWSGITests(TransactionTestCase):
    @override_settings(APP_BASE_PATH='/team/test/', INSTANCE_ID='prefix-a', FORCE_SCRIPT_NAME='/team/test',
                       CSRF_COOKIE_NAME='task_tracker_prefix-a_csrf', CSRF_COOKIE_PATH='/team/test/',
                       CSRF_COOKIE_SECURE=True)
    def test_real_wsgi_stripped_path_generates_prefixed_redirect_and_scoped_cookie(self):
        handler = WSGIHandler()
        self.addCleanup(set_script_prefix, '/')
        def request(path, query=''):
            result = {}
            environ = {'REQUEST_METHOD': 'GET', 'PATH_INFO': path, 'SCRIPT_NAME': '',
                       'QUERY_STRING': query, 'SERVER_NAME': 'localhost', 'SERVER_PORT': '80',
                       'SERVER_PROTOCOL': 'HTTP/1.1', 'wsgi.version': (1, 0), 'wsgi.url_scheme': 'http',
                       'wsgi.input': BytesIO(), 'wsgi.errors': BytesIO(), 'wsgi.multithread': False,
                       'wsgi.multiprocess': False, 'wsgi.run_once': False}
            def start_response(status, headers):
                result.update(status=status, headers=dict(headers))
            response = handler(environ, start_response)
            try:
                result['body'] = b''.join(response)
            finally:
                response.close()
            return result
        result = request('/api/v1/health', 'page=2')
        self.assertTrue(result['status'].startswith('301'))
        self.assertEqual(result['headers']['Location'], '/team/test/api/v1/health/?page=2')
        self.assertEqual(reverse('health'), '/team/test/api/v1/health/')
        result = request('/api/v1/auth/csrf/')
        self.assertTrue(result['status'].startswith('200'))
        cookie = result['headers']['Set-Cookie']
        self.assertIn('task_tracker_prefix-a_csrf=', cookie)
        self.assertIn('Path=/team/test/', cookie)
        self.assertIn('Secure', cookie)
