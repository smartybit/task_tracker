import importlib.util
from argparse import Namespace
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

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
