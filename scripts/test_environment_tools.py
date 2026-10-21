import importlib.util
from argparse import Namespace
from contextlib import redirect_stdout
from io import StringIO
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from types import SimpleNamespace

spec = importlib.util.spec_from_file_location('environment_tools', Path(__file__).with_name('environments.py'))
environment_tools = importlib.util.module_from_spec(spec)
spec.loader.exec_module(environment_tools)


class EnvironmentTargetTests(unittest.TestCase):
    def config(self, name='evaluation', **changes):
        return dict(INSTANCE_ID=f'task-tracker-env-{name}', ENVIRONMENT_ROLE='evaluation',
                    APP_BASE_PATH=f'/{name}/', HTTP_PORT='8181', PUBLIC_ORIGIN='http://127.0.0.1:8181',
                    PUBLIC_SCHEME='http', PUBLIC_HOST='127.0.0.1', COOKIE_SECURE='false', DJANGO_SECRET_KEY='ab' * 40,
                    POSTGRES_PASSWORD='cd' * 32, RELEASE='source-1234', WORKING_TIME_ZONE='UTC',
                    WEB_WORKERS='2', **changes)

    def test_private_config_targets_only_its_matching_name(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            environment_tools.save('evaluation', self.config(), directory, create=True)
            self.assertEqual(environment_tools.load('evaluation', directory), self.config())
            self.assertEqual((directory / 'evaluation.env').stat().st_mode & 0o777, 0o600)
            (directory / 'evaluation.env').rename(directory / 'agent.env')
            with self.assertRaisesRegex(ValueError, 'identity differ'):
                environment_tools.load('agent', directory)

    def test_shared_ports_overlapping_mounts_and_reused_secrets_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            environment_tools.save('evaluation', self.config(), directory, create=True)
            independent = {**self.config('agent'), 'HTTP_PORT': '8182', 'PUBLIC_ORIGIN': 'http://127.0.0.1:8182',
                           'DJANGO_SECRET_KEY': 'ef' * 40, 'POSTGRES_PASSWORD': '12' * 32}
            environment_tools.check_registry(independent, directory)
            for changes in ({'HTTP_PORT': '8181'}, {'APP_BASE_PATH': '/evaluation/nested/'},
                            {'DJANGO_SECRET_KEY': self.config()['DJANGO_SECRET_KEY']},
                            {'POSTGRES_PASSWORD': self.config()['POSTGRES_PASSWORD']}):
                with self.subTest(changes=changes), self.assertRaises(ValueError):
                    environment_tools.check_registry({**independent, **changes}, directory)

    def test_rejects_path_escape_public_http_and_shell_interpolation(self):
        for name in ('../evaluation', 'UPPER', 'agent/other', ''):
            with self.subTest(name=name), self.assertRaises(ValueError):
                environment_tools.name_path(name)
        for changes in ({'PUBLIC_ORIGIN': 'http://example.test:8181'}, {'APP_BASE_PATH': '/a/../b/'},
                        {'RELEASE': '$(echo unsafe)'}, {'PUBLIC_ORIGIN': 'http://localhost:other'},
                        {'WORKING_TIME_ZONE': 'Unknown/Not-A-Zone'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                environment_tools.validate({**self.config(), **changes})

    def test_bootstrap_asks_email_and_prints_generated_password_only_after_success(self):
        args = Namespace(action='bootstrap', email=None, generate_password=False)
        output = StringIO()
        with patch('builtins.input', return_value='operator@example.test') as prompt, \
                patch.object(environment_tools, 'compose') as command, redirect_stdout(output):
            environment_tools.account('evaluation', self.config(), args)
        prompt.assert_called_once_with('Administrator email: ')
        payload = json.loads(command.call_args.kwargs['input'])
        self.assertEqual(payload['email'], 'operator@example.test')
        self.assertGreaterEqual(len(payload['password']), 24)
        self.assertIn(f"Password: {payload['password']}", output.getvalue())
        output = StringIO()
        with patch('builtins.input', return_value='operator@example.test'), \
                patch.object(environment_tools, 'compose', side_effect=ValueError('already bootstrapped')), \
                redirect_stdout(output), self.assertRaises(ValueError):
            environment_tools.account('evaluation', self.config(), args)
        self.assertNotIn('Password:', output.getvalue())

    def test_foreign_workspace_cannot_receive_a_compose_operation(self):
        with patch.object(environment_tools.subprocess, 'run', return_value=SimpleNamespace(stdout='/another/workspace\n')) as run:
            with self.assertRaisesRegex(ValueError, 'different workspace'):
                environment_tools.compose('evaluation', self.config(), 'up', '-d')
        self.assertEqual(run.call_count, 1)
        self.assertEqual(run.call_args.args[0][0:3], ['docker', 'ps', '-a'])

    def test_existing_orphan_storage_cannot_be_registered_as_a_new_environment(self):
        with patch.object(environment_tools.subprocess, 'run', side_effect=[SimpleNamespace(stdout=''), SimpleNamespace(stdout='existing-volume\n')]) as run:
            with self.assertRaisesRegex(ValueError, 'original configuration'):
                environment_tools.assert_new_project(self.config())
        self.assertEqual(run.call_count, 2)


class EnvironmentVerificationTests(unittest.TestCase):
    def setUp(self):
        self.config = {**EnvironmentTargetTests().config('agent-3'),
                       'ENVIRONMENT_ROLE': 'agent', 'APP_BASE_PATH': '/team/agent-3/',
                       'WORKING_TIME_ZONE': 'Europe/Berlin'}
        self.runtime = dict(DEBUG=False, APP_ENV='agent', INSTANCE_ID='task-tracker-env-agent-3',
                            APP_BASE_PATH='/team/agent-3/', TIME_ZONE='Europe/Berlin',
                            SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False,
                            SESSION_COOKIE_PATH='/team/agent-3/', CSRF_COOKIE_PATH='/team/agent-3/',
                            CSRF_TRUSTED_ORIGINS=['http://127.0.0.1:8181'])
        self.containers = []
        for service in ('db', 'web', 'frontend'):
            self.containers.append(dict(service=service, image=f'task-tracker-env-agent-3-{service}:source-1234',
                                        user='1000:1000', running=True, health='healthy', read_only=True,
                                        restart='unless-stopped', cap_drop=['ALL'],
                                        security=['no-new-privileges:true'], mounts=[], ports={}))
        self.containers[0]['mounts'] = [dict(Type='volume', Name='task-tracker-env-agent-3_database',
                                             Destination='/var/lib/postgresql/data')]
        self.containers[1]['mounts'] = [dict(Type='volume', Name='task-tracker-env-agent-3_uploads',
                                             Destination='/var/lib/task-tracker/uploads')]
        self.containers[2]['ports'] = {'8080/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '8181'}]}

    def commands(self, runtime=None):
        return patch.object(environment_tools, 'compose', side_effect=[
            SimpleNamespace(stdout='db-id\nweb-id\nfrontend-id\n'),
            SimpleNamespace(stdout=json.dumps(self.runtime if runtime is None else runtime))])

    def inspection(self, containers=None):
        data = self.containers if containers is None else containers
        return patch.object(environment_tools.subprocess, 'run',
                            return_value=SimpleNamespace(stdout='\n'.join(json.dumps(info) for info in data)))

    def test_verification_targets_any_named_environment_and_only_inspects(self):
        for role in ('production', 'evaluation', 'agent'):
            config = {**self.config, 'ENVIRONMENT_ROLE': role}
            with self.subTest(role=role), self.commands({**self.runtime, 'APP_ENV': role}) as command, \
                    self.inspection() as inspect, patch.object(environment_tools, 'verify_http') as http, \
                    redirect_stdout(StringIO()) as output:
                environment_tools.verify('agent-3', config)
            self.assertIn('PASS agent-3', output.getvalue())
            self.assertEqual(command.call_args_list[0].args, ('agent-3', config, 'ps', '--all', '--quiet', 'db', 'web', 'frontend'))
            self.assertEqual(command.call_args_list[1].args[:7], ('agent-3', config, 'exec', '-T', 'web', 'python', '-c'))
            self.assertEqual(inspect.call_args.args[0][:3], ['docker', 'inspect', '--format'])
            http.assert_called_once_with(config)

    def test_unsafe_missing_or_stale_containers_fail_before_runtime_or_http_requests(self):
        cases = [(0, {'health': 'unhealthy'}), (0, {'mounts': []}),
                 (1, {'image': 'task-tracker-env-agent-3-web:old-release'}),
                 (1, {'ports': {'8000/tcp': [{'HostIp': '0.0.0.0', 'HostPort': '8000'}]}}),
                 (1, {'mounts': [dict(Type='bind', Destination='/app')]}),
                 (1, {'user': '0:0'}), (1, {'read_only': False}), (1, {'cap_drop': []}),
                 (1, {'security': []}), (2, {'restart': 'no'}),
                 (2, {'ports': {'8080/tcp': [{'HostIp': '0.0.0.0', 'HostPort': '8181'}]}})]
        for index, changes in cases:
            containers = json.loads(json.dumps(self.containers))
            containers[index].update(changes)
            with self.subTest(changes=changes), self.commands() as command, self.inspection(containers), \
                    patch.object(environment_tools, 'verify_http') as http, self.assertRaises(ValueError):
                environment_tools.verify('agent-3', self.config)
            self.assertEqual(command.call_count, 1)
            http.assert_not_called()
        with patch.object(environment_tools, 'compose', return_value=SimpleNamespace(stdout='')) as command, \
                patch.object(environment_tools.subprocess, 'run') as inspect, self.assertRaisesRegex(ValueError, 'existing'):
            environment_tools.verify('agent-3', self.config)
        inspect.assert_not_called()

    def test_runtime_settings_drift_stops_http_verification(self):
        for changes in ({'DEBUG': True}, {'TIME_ZONE': 'UTC'}, {'INSTANCE_ID': 'another-instance'},
                        {'SESSION_COOKIE_PATH': '/'}, {'CSRF_TRUSTED_ORIGINS': ['https://other.test']}):
            with self.subTest(changes=changes), self.commands({**self.runtime, **changes}), self.inspection(), \
                    patch.object(environment_tools, 'verify_http') as http, redirect_stdout(StringIO()), \
                    self.assertRaisesRegex(ValueError, 'Backend settings differ'):
                environment_tools.verify('agent-3', self.config)
            http.assert_not_called()


class EnvironmentHTTPVerificationTests(unittest.TestCase):
    def setUp(self):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.server.requests.append(self.path)
                status, headers, body = self.server.responses.get(self.path, (404, {}, b'missing'))
                if self.headers.get('Host') == 'unexpected.invalid':
                    status, headers, body = 400, {}, b'bad host'
                self.send_response(status)
                for key, value in headers.items():
                    self.send_header(key, value)
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.server.requests = []
        self.config = {**EnvironmentTargetTests().config('agent-3'),
                       'HTTP_PORT': str(self.server.server_port),
                       'PUBLIC_ORIGIN': f'http://127.0.0.1:{self.server.server_port}'}
        base = self.config['APP_BASE_PATH']
        self.base = base
        self.server.responses = {
            base: (200, {'Cache-Control': 'no-store'}, f'<script type="module" src="{base}assets/app.js"></script>'.encode()),
            base + 'instance.json': (200, {}, json.dumps(dict(basePath=base, instanceId=self.config['INSTANCE_ID'])).encode()),
            base + 'api/v1/health/': (200, {'X-Task-Tracker-Instance': self.config['INSTANCE_ID'], 'X-Task-Tracker-Base-Path': base},
                                      b'{"status":"ok","database":"postgresql","api_version":"v1"}'),
            base + 'assets/app.js': (200, {'Cache-Control': 'public, immutable'}, b'/* compiled JS */'),
        }
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def test_real_http_checks_identity_database_health_assets_and_rejections(self):
        with redirect_stdout(StringIO()) as output:
            environment_tools.verify_http(self.config)
        self.assertIn('PASS HTTP', output.getvalue())
        self.assertIn(self.base + 'assets/app.js', self.server.requests)
        self.assertIn(self.base + 'assets/__deployment_verify_missing__.js', self.server.requests)

    def test_configured_origin_is_also_checked_when_different_from_loopback_address(self):
        self.config['PUBLIC_ORIGIN'] = f'http://localhost:{self.server.server_port}'
        with redirect_stdout(StringIO()):
            environment_tools.verify_http(self.config)
        self.assertEqual(self.server.requests.count(self.base + 'api/v1/health/'), 2)

    def test_redirects_and_assets_outside_the_mount_are_rejected_without_following(self):
        for status, headers, body in (
            (302, {'Location': '/other-instance/'}, b''),
            (200, {'Cache-Control': 'no-store'}, b'<script src="/other-instance/app.js"></script>'),
        ):
            self.server.responses[self.base] = (status, headers, body)
            with self.subTest(status=status), self.assertRaises(ValueError):
                environment_tools.verify_http(self.config)
        self.assertNotIn('/other-instance/', self.server.requests)
        self.assertNotIn('/other-instance/app.js', self.server.requests)

    def test_wrong_identity_or_failed_database_cannot_pass_as_a_healthy_deployment(self):
        metadata = self.base + 'instance.json'
        original = self.server.responses[metadata]
        self.server.responses[metadata] = (200, {}, b'{"basePath":"/other/","instanceId":"other"}')
        with self.assertRaisesRegex(ValueError, 'frontend identity'):
            environment_tools.verify_http(self.config)
        self.server.responses[metadata] = original
        health = self.base + 'api/v1/health/'
        status, headers, body = self.server.responses[health]
        self.server.responses[health] = (status, {**headers, 'X-Task-Tracker-Instance': 'other'}, body)
        with self.assertRaisesRegex(ValueError, 'backend identity'):
            environment_tools.verify_http(self.config)
        self.server.responses[health] = (503, {}, b'{"status":"unavailable"}')
        with self.assertRaisesRegex(ValueError, 'HTTP 200, received 503'):
            environment_tools.verify_http(self.config)
