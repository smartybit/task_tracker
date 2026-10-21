from django.core.exceptions import ImproperlyConfigured
from django.middleware.security import SecurityMiddleware
from django.test import RequestFactory, SimpleTestCase, override_settings

from config.deployment import deployment_settings


class DeploymentConfigurationTests(SimpleTestCase):
    def config(self, **values):
        return {'APP_ENV': 'evaluation', 'PUBLIC_ORIGIN': 'http://127.0.0.1:8181',
                'DJANGO_SECRET_KEY': '0123456789abcdef' * 5, **values}

    def test_development_defaults_are_preserved_and_unknown_roles_rejected(self):
        self.assertEqual(deployment_settings({}), {})
        self.assertEqual(deployment_settings({'APP_ENV': 'test'}), {})
        with self.assertRaises(ImproperlyConfigured):
            deployment_settings({'APP_ENV': 'prodution'})

    def test_loopback_ssh_and_public_https_have_explicit_origin_and_scheme_rules(self):
        local = deployment_settings(self.config())
        self.assertEqual(local['CSRF_TRUSTED_ORIGINS'], ['http://127.0.0.1:8181'])
        self.assertFalse(local['SECURE_SSL_REDIRECT'])
        secure = deployment_settings(self.config(PUBLIC_ORIGIN='https://projects.example.test',
                                                 DJANGO_COOKIE_SECURE='true', APP_ENV='production'))
        self.assertTrue(secure['SECURE_SSL_REDIRECT'])
        self.assertEqual(secure['ALLOWED_HOSTS'], ['projects.example.test', 'localhost', '127.0.0.1'])
        self.assertEqual(secure['SECURE_PROXY_SSL_HEADER'], ('HTTP_X_FORWARDED_PROTO', 'https'))

    def test_deployments_reject_debug_weak_keys_public_http_and_inconsistent_security(self):
        for changes in ({'DJANGO_DEBUG': 'true'}, {'DJANGO_SECRET_KEY': 'development-only'},
                        {'PUBLIC_ORIGIN': 'http://public.example.test'},
                        {'PUBLIC_ORIGIN': 'https://public.example.test'},
                        {'PUBLIC_ORIGIN': 'http://localhost:8181/path'},
                        {'PUBLIC_ORIGIN': 'https://user:pass@public.example.test'},
                        {'PUBLIC_ORIGIN': 'http://localhost:wrong'},
                        {'PUBLIC_SCHEME': 'https'}, {'DJANGO_COOKIE_SECURE': 'true'}):
            with self.subTest(changes=changes), self.assertRaises(ImproperlyConfigured):
                deployment_settings(self.config(**changes))

    def test_https_internal_health_works_at_root_and_prefixed_mounts(self):
        for mount in ('/', '/time-tracker-eval/', '/team/evaluation/'):
            with self.subTest(mount=mount):
                config = deployment_settings(self.config(
                    PUBLIC_ORIGIN='https://public.example.test', DJANGO_COOKIE_SECURE='true',
                    APP_BASE_PATH=mount))
                with override_settings(**config, FORCE_SCRIPT_NAME=mount.rstrip('/') or None):
                    middleware = SecurityMiddleware(lambda request: None)
                    factory = RequestFactory()
                    health = factory.get('/api/v1/health/', HTTP_HOST='127.0.0.1:8000')
                    self.assertEqual(health.path, mount + 'api/v1/health/')
                    self.assertIsNone(middleware.process_request(health))
                    # Other HTTP routes still require HTTPS; the exception is exact.
                    for path in ('/api/v1/auth/csrf/', '/api/v1/health/extra', '/api/v1/health'):
                        request = factory.get(path, HTTP_HOST='public.example.test')
                        response = middleware.process_request(request)
                        self.assertEqual(response.status_code, 301)
                        self.assertEqual(response['Location'], 'https://public.example.test' + request.path)
