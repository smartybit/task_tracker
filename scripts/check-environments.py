"""Bounded synthetic deployment lifecycle; never targets persistent evaluation/agent names."""
import fcntl
import json
from pathlib import Path
import re
import signal
import socket
import subprocess
import sys
import threading
import traceback
import urllib.request

import environments as operations

ROOT = operations.ROOT
RESULTS = ROOT / '.artifacts' / 'verification'
NAMES = ('deployment-check-eval', 'deployment-check-agent', 'deployment-check-extra')


def cli(*arguments, **kwargs):
    return subprocess.run([sys.executable, str(ROOT / 'scripts/environments.py'), *arguments],
                          cwd=ROOT, check=True, **kwargs)


def free_port():
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        return probe.getsockname()[1]


def snapshot(name, config):
    source = """
import hashlib,json
from pathlib import Path
from django.apps import apps
from django.conf import settings
from django.db import connection
assert settings.INSTANCE_ID in ('task-tracker-env-deployment-check-eval', 'task-tracker-env-deployment-check-agent', 'task-tracker-env-deployment-check-extra')
assert settings.APP_ENV in ('evaluation','agent')
data={}
for model in apps.get_models():
    if model._meta.app_label in ('accounts','access','core','projects','tasks','timesheets','remarks','content'):
        data[model._meta.label]=list(model.objects.order_by(model._meta.pk.name).values())
images=apps.get_model('content','ContentImage').objects.all()
assert images.exists()
data['images']={str(image.pk):hashlib.sha256((Path(settings.MEDIA_ROOT)/image.file_name).read_bytes()).hexdigest() for image in images}
with connection.cursor() as cursor:
    cursor.execute('SELECT system_identifier FROM pg_control_system()')
    data['database_identity']=str(cursor.fetchone()[0])
print('SNAPSHOT:'+json.dumps(data,default=str,sort_keys=True))
"""
    result = operations.compose(name, config, 'exec', '-T', 'web', 'python', 'manage.py', 'shell', '-c', source,
                                capture_output=True, text=True)
    return next(line for line in result.stdout.splitlines() if line.startswith('SNAPSHOT:'))


def browser(label, phase, instances):
    subprocess.run(['docker', 'run', '--rm', '--network', 'host', '--user', '1000:1000', '--init', '-i',
                    '--mount', f'type=bind,source={ROOT / "frontend"},target=/work',
                    '--mount', f'type=bind,source={ROOT / "scripts"},target=/checks,readonly',
                    'mcr.microsoft.com/playwright:v1.64.0-noble', 'timeout', '240', 'node', '/checks/environment-browser.cjs'],
                   input=json.dumps(dict(label=label, phase=phase, instances=instances)), text=True, check=True)


def verify(label):
    created = []
    try:
        for name in NAMES:
            if operations.name_path(name).exists():
                raise RuntimeError(f'Reserved configuration {name} already exists; inspect it before retrying.')
        ports = set()
        instances = []
        for index, name in enumerate(NAMES):
            port = free_port()
            while port in ports:
                port = free_port()
            ports.add(port)
            role = 'evaluation' if index == 0 else 'agent'
            path = f'/deployment-check-{index}/' if index != 1 else '/team/deployment-check-1/'
            cli('init', name, '--role', role, '--port', str(port), '--path', path, '--release', label)
            created.append(name)
            cli('check', name)
            cli('build', name)
            cli('up', name)
            # Exercise the real interactive email prompt. These are disposable
            # synthetic passwords; neither the prompt output nor password is logged.
            bootstrap = cli('bootstrap', name, input='deployment@example.test\n', capture_output=True, text=True)
            assert 'Administrator email:' in bootstrap.stdout
            password = next(line.removeprefix('Password: ') for line in bootstrap.stdout.splitlines() if line.startswith('Password: '))
            duplicate = subprocess.run([sys.executable, str(ROOT / 'scripts/environments.py'), 'bootstrap', name,
                                        '--email', 'other@example.test'], cwd=ROOT, capture_output=True, text=True)
            assert duplicate.returncode != 0 and 'Password:' not in duplicate.stdout
            config = operations.load(name)
            instances.append(dict(url=config['PUBLIC_ORIGIN'] + config['APP_BASE_PATH'],
                                  id=config['INSTANCE_ID'], email='deployment@example.test', password=password))
            print(f'{name}: isolated bootstrap and duplicate refusal passed.', flush=True)
        first = operations.load(NAMES[0])
        bad = operations.compose(NAMES[0], first, 'run', '--rm', '--no-deps', '-e', 'APP_BASE_PATH=/wrong/', 'frontend',
                                 check=False, capture_output=True, text=True)
        assert bad.returncode != 0 and 'image/runtime instance mismatch' in bad.stdout + bad.stderr
        browser(label, 'before', instances)
        before = {name: snapshot(name, operations.load(name)) for name in NAMES}
        sibling_ids = operations.compose(NAMES[0], first, 'ps', '-q', capture_output=True, text=True).stdout
        extra = operations.load(NAMES[2])
        extra_ids = operations.compose(NAMES[2], extra, 'ps', '-q', capture_output=True, text=True).stdout
        stop = threading.Event()
        observations = []
        failures = []

        def observe():
            while not stop.is_set():
                try:
                    with urllib.request.urlopen(instances[0]['url'] + 'api/v1/health/', timeout=3) as response:
                        assert response.status == 200
                        assert response.headers['X-Task-Tracker-Instance'] == first['INSTANCE_ID']
                    observations.append(True)
                except Exception as exc:
                    failures.append(str(exc))
                stop.wait(0.5)

        observer = threading.Thread(target=observe, daemon=True)
        observer.start()
        try:
            cli('build', NAMES[1], '--release', f'{label}-updated')
            cli('up', NAMES[1])
            cli('down', NAMES[1])
            cli('up', NAMES[1])
        finally:
            stop.set()
            observer.join(5)
        assert len(observations) >= 2 and not failures, failures
        assert sibling_ids == operations.compose(NAMES[0], first, 'ps', '-q', capture_output=True, text=True).stdout
        assert extra_ids == operations.compose(NAMES[2], extra, 'ps', '-q', capture_output=True, text=True).stdout
        for name in NAMES:
            assert before[name] == snapshot(name, operations.load(name)), f'{name}: data or image bytes changed.'
        browser(label, 'after', instances)
        print(f'Evaluation stayed healthy across {len(observations)} observations during agent update and restart.', flush=True)
        print('Three-environment deployment acceptance passed.', flush=True)
    finally:
        cleanup_failed = False
        for name in reversed(created):
            try:
                config = operations.load(name)
                assert name in NAMES and config['INSTANCE_ID'] == f'task-tracker-env-{name}'
                operations.compose(name, config, 'down', '--volumes', '--remove-orphans')
                operations.name_path(name).unlink()
            except Exception:
                cleanup_failed = True
                traceback.print_exc()
        if cleanup_failed:
            raise RuntimeError('Synthetic deployment cleanup failed; retained configuration identifies the exact projects.')


def main():
    if len(sys.argv) == 3 and sys.argv[1] == '--run':
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
        verify(sys.argv[2])
        return 0
    if len(sys.argv) != 2 or not re.fullmatch(r'[a-zA-Z0-9_-]{1,70}', sys.argv[1]):
        raise ValueError('Usage: python3 scripts/check-environments.py LABEL (letters, digits, underscores and hyphens).')
    label = sys.argv[1]
    RESULTS.mkdir(parents=True, exist_ok=True)
    with (RESULTS / 'deployment-check.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        log = RESULTS / f'{label}.log'
        status = RESULTS / f'{label}.status'
        if log.exists() or status.exists():
            raise ValueError('Choose a fresh verification label.')
        print(f'Log: {log}\nStatus: {status}', flush=True)
        with log.open('x') as output:
            result = subprocess.run(['timeout', '--foreground', '1500', sys.executable,
                                     str(Path(__file__).resolve()), '--run', label], stdout=output,
                                    stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
        status.write_text(f'{result.returncode}\n')
        return result.returncode


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError) as exc:
        sys.exit(str(exc))
