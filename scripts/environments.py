"""Explicitly targeted deployments; no action defaults to evaluation or production."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
from urllib.parse import urlsplit
from urllib.error import HTTPError, URLError
from urllib.request import build_opener, HTTPRedirectHandler, ProxyHandler, Request
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ROOT = Path(__file__).resolve().parent.parent
DIRECTORY = ROOT / 'environments'
FIELDS = {'INSTANCE_ID', 'ENVIRONMENT_ROLE', 'APP_BASE_PATH', 'HTTP_PORT', 'PUBLIC_ORIGIN',
          'PUBLIC_SCHEME', 'PUBLIC_HOST', 'COOKIE_SECURE', 'DJANGO_SECRET_KEY', 'POSTGRES_PASSWORD',
          'RELEASE', 'WORKING_TIME_ZONE', 'WEB_WORKERS'}


def name_path(name, directory=DIRECTORY):
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,31}', name):
        raise ValueError('Names must be lowercase alphanumeric/hyphen slugs, at most 32 characters.')
    return directory / f'{name}.env'


def validate(config):
    if set(config) != FIELDS:
        raise ValueError('Environment configuration has missing or unsupported fields.')
    if config['ENVIRONMENT_ROLE'] not in {'production', 'evaluation', 'agent'}:
        raise ValueError('Invalid environment role.')
    if not re.fullmatch(r'task-tracker-env-[a-z0-9][a-z0-9-]{0,31}', config['INSTANCE_ID']):
        raise ValueError('Invalid instance identity.')
    base = config['APP_BASE_PATH']
    if not re.fullmatch(r'/(?:[A-Za-z0-9_-]+/)*', base):
        raise ValueError('The application mount must have plain URL segments and a trailing slash.')
    if not config['HTTP_PORT'].isdigit() or not 1024 <= int(config['HTTP_PORT']) <= 65535:
        raise ValueError('Choose a loopback TCP port between 1024 and 65535.')
    parsed = urlsplit(config['PUBLIC_ORIGIN'])
    if (parsed.scheme not in {'http', 'https'} or not parsed.hostname
            or not re.fullmatch(r'[A-Za-z0-9.-]+', parsed.hostname)
            or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment):
        raise ValueError('PUBLIC_ORIGIN must be an HTTP(S) origin without a path or credentials.')
    if parsed.port == 0:
        raise ValueError('Invalid origin port.')
    if parsed.scheme == 'http' and (parsed.hostname not in {'localhost', '127.0.0.1'}
                                   or (parsed.port or 80) != int(config['HTTP_PORT'])):
        raise ValueError('HTTP access must use localhost/127.0.0.1 and the configured loopback port.')
    if (config['PUBLIC_SCHEME'] != parsed.scheme or config['PUBLIC_HOST'] != parsed.hostname
            or config['COOKIE_SECURE'] != str(parsed.scheme == 'https').lower()):
        raise ValueError('Origin, scheme and cookie security settings must agree.')
    if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}', config['RELEASE']):
        raise ValueError('Invalid release tag.')
    if not config['WEB_WORKERS'].isdigit() or not 1 <= int(config['WEB_WORKERS']) <= 8:
        raise ValueError('WEB_WORKERS must be between 1 and 8.')
    for key in ('DJANGO_SECRET_KEY', 'POSTGRES_PASSWORD'):
        if not re.fullmatch(r'[0-9a-f]{64,}', config[key]):
            raise ValueError('Use independently generated hexadecimal environment secrets.')
    try:
        ZoneInfo(config['WORKING_TIME_ZONE'])
    except (ValueError, ZoneInfoNotFoundError) as exc:
        raise ValueError('Choose an installed IANA working time zone.') from exc
    if any('\n' in value or '\r' in value or '$' in value for value in config.values()):
        raise ValueError('Environment configuration must contain literal single-line values.')
    return config


def load(name, directory=DIRECTORY):
    path = name_path(name, directory)
    if path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o077:
        raise ValueError('Environment files must be private regular files (mode 600).')
    config = {}
    for line in path.read_text().splitlines():
        if not line or line.startswith('#'):
            continue
        key, separator, value = line.partition('=')
        if not separator or key in config:
            raise ValueError('Invalid or repeated configuration field.')
        config[key] = value
    validate(config)
    if config['INSTANCE_ID'] != f'task-tracker-env-{name}':
        raise ValueError('Environment name and instance identity differ.')
    return config


def save(name, config, directory=DIRECTORY, *, create=False):
    validate(config)
    path = name_path(name, directory)
    text = ''.join(f'{key}={value}\n' for key, value in config.items())
    if create:
        with open(path, 'x', opener=lambda filename, flags: os.open(filename, flags, 0o600)) as output:
            output.write(text)
    else:
        temporary = path.with_suffix('.env.tmp')
        with open(temporary, 'x', opener=lambda filename, flags: os.open(filename, flags, 0o600)) as output:
            output.write(text)
        temporary.replace(path)


def check_registry(config, directory=DIRECTORY, *, excluding=None):
    for file in directory.glob('*.env'):
        if file.stem == excluding:
            continue
        other = load(file.stem, directory)
        if config['HTTP_PORT'] == other['HTTP_PORT'] or config['INSTANCE_ID'] == other['INSTANCE_ID']:
            raise ValueError('Environment ports and instance identities must be distinct.')
        same_host = urlsplit(config['PUBLIC_ORIGIN']).hostname == urlsplit(other['PUBLIC_ORIGIN']).hostname
        if same_host and (config['APP_BASE_PATH'].startswith(other['APP_BASE_PATH'])
                          or other['APP_BASE_PATH'].startswith(config['APP_BASE_PATH'])):
            raise ValueError('Application mounts on one hostname must not overlap.')
        if any(config[key] == other[key] for key in ('DJANGO_SECRET_KEY', 'POSTGRES_PASSWORD')):
            raise ValueError('Environments must have independent secrets.')


@contextmanager
def locked():
    DIRECTORY.mkdir(mode=0o700, exist_ok=True)
    if DIRECTORY.is_symlink() or DIRECTORY.stat().st_mode & 0o077:
        raise ValueError('The environments directory must be private (mode 700).')
    with (DIRECTORY / '.operations.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def assert_new_project(config):
    selector = f"label=com.docker.compose.project={config['INSTANCE_ID']}"
    for command in (['ps', '-aq'], ['volume', 'ls', '-q'], ['network', 'ls', '-q']):
        result = subprocess.run(['docker', *command, '--filter', selector],
                                capture_output=True, text=True, check=True)
        if result.stdout.strip():
            raise ValueError('Docker resources already use this environment identity. Restore its original configuration or choose another name.')


def assert_project_owner(config):
    result = subprocess.run(['docker', 'ps', '-a', '--filter',
                             f"label=com.docker.compose.project={config['INSTANCE_ID']}",
                             '--format', '{{.Label "com.docker.compose.project.working_dir"}}'],
                            capture_output=True, text=True, check=True)
    for owner in result.stdout.splitlines():
        if not owner or Path(owner).resolve() != ROOT:
            raise ValueError('This Docker project belongs to a different workspace. No deployment changes were made.')


def compose(name, config, *arguments, check=True, **kwargs):
    if arguments[0] != 'config':
        assert_project_owner(config)
    # Explicit env files must win over the caller's shell or .env defaults.
    environment = {key: value for key, value in os.environ.items()
                   if key not in FIELDS and not key.startswith('COMPOSE_')}
    environment.update(BUILDKIT_PROGRESS='plain', COMPOSE_PROGRESS='plain', COMPOSE_ANSI='never')
    return subprocess.run(['docker', 'compose', '--project-directory', str(ROOT),
                           '--env-file', str(name_path(name)), '-f', str(ROOT / 'compose.environments.yaml'),
                           '-p', config['INSTANCE_ID'], *arguments], cwd=ROOT, env=environment,
                          check=check, **kwargs)


def image_exists(config, service):
    return subprocess.run(['docker', 'image', 'inspect', f"{config['INSTANCE_ID']}-{service}:{config['RELEASE']}"],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


def describe(name, config):
    print(f"{name}: {config['ENVIRONMENT_ROLE']}; {config['PUBLIC_ORIGIN']}{config['APP_BASE_PATH']}; release {config['RELEASE']}")


class FrontendAssets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.paths = []

    def handle_starttag(self, tag, attributes):
        attributes = dict(attributes)
        if tag == 'script' and attributes.get('src'):
            self.paths.append(attributes['src'])
        if tag == 'link' and 'stylesheet' in attributes.get('rel', '').split():
            self.paths.append(attributes.get('href', ''))


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        return None


def verify_response(opener, url, expected=200, *, host=None):
    try:
        response = opener.open(Request(url, headers={'Host': host} if host else {}), timeout=10)
    except HTTPError as exc:
        response = exc
    except URLError as exc:
        raise ValueError(f'Cannot reach {url}: {exc.reason}') from exc
    with response:
        if response.status != expected:
            raise ValueError(f'{url}: expected HTTP {expected}, received {response.status}.')
        body = response.read(8 * 1024 * 1024 + 1)
        if len(body) > 8 * 1024 * 1024:
            raise ValueError(f'{url}: response exceeds the verification size limit.')
        return response.headers, body


def verify_http(config):
    # Reach the private frontend directly and, if different, the configured public
    # origin too. Never follow redirects or send credentials to another location.
    opener = build_opener(ProxyHandler({}), NoRedirects())
    local = f"http://127.0.0.1:{config['HTTP_PORT']}"
    for origin in dict.fromkeys((local, config['PUBLIC_ORIGIN'])):
        base = origin + config['APP_BASE_PATH']
        host = urlsplit(config['PUBLIC_ORIGIN']).netloc
        headers, html = verify_response(opener, base, host=host)
        if 'no-store' not in headers.get('Cache-Control', '') or b'/@vite/' in html:
            raise ValueError('The frontend must serve uncached built HTML, without a Vite client.')
        _, metadata = verify_response(opener, base + 'instance.json', host=host)
        if json.loads(metadata) != {'basePath': config['APP_BASE_PATH'], 'instanceId': config['INSTANCE_ID']}:
            raise ValueError('The served frontend identity or mount differs from the configuration.')
        headers, health = verify_response(opener, base + 'api/v1/health/', host=host)
        if (json.loads(health) != {'status': 'ok', 'database': 'postgresql', 'api_version': 'v1'}
                or headers.get('X-Task-Tracker-Instance') != config['INSTANCE_ID']
                or headers.get('X-Task-Tracker-Base-Path') != config['APP_BASE_PATH']):
            raise ValueError('API/database health or backend identity does not match this environment.')
        assets = FrontendAssets()
        assets.feed(html.decode('utf-8'))
        if not assets.paths:
            raise ValueError('The frontend HTML contains no built assets.')
        for path in assets.paths:
            if (not path.startswith(config['APP_BASE_PATH'] + 'assets/')
                    or not re.fullmatch(r'/[A-Za-z0-9_./-]+', path) or '..' in path.split('/')):
                raise ValueError('A frontend asset URL escapes the configured asset mount.')
            headers, body = verify_response(opener, origin + path, host=host)
            if not body or 'immutable' not in headers.get('Cache-Control', ''):
                raise ValueError('Built assets must be nonempty and served with immutable caching.')
        verify_response(opener, base + 'assets/__deployment_verify_missing__.js', 404, host=host)
        print(f'PASS HTTP: frontend identity/assets and API/PostgreSQL health at {base}')
    verify_response(opener, local + config['APP_BASE_PATH'], 400, host='unexpected.invalid')


def verify(name, config):
    result = compose(name, config, 'ps', '--all', '--quiet', 'db', 'web', 'frontend',
                     capture_output=True, text=True, timeout=30)
    ids = result.stdout.split()
    if len(ids) != 3:
        raise ValueError('Expected one existing db, web and frontend container. Run status for details.')
    # Project only safe fields: Docker's full inspection includes environment secrets.
    template = ('{"service":{{json (index .Config.Labels "com.docker.compose.service")}},'
                '"image":{{json .Config.Image}},"user":{{json .Config.User}},'
                '"running":{{json .State.Running}},'
                '"health":{{if .State.Health}}{{json .State.Health.Status}}{{else}}null{{end}},'
                '"read_only":{{json .HostConfig.ReadonlyRootfs}},'
                '"restart":{{json .HostConfig.RestartPolicy.Name}},'
                '"ports":{{json .HostConfig.PortBindings}},'
                '"cap_drop":{{json .HostConfig.CapDrop}},'
                '"security":{{json .HostConfig.SecurityOpt}},"mounts":{{json .Mounts}}}')
    result = subprocess.run(['docker', 'inspect', '--format', template, *ids],
                            capture_output=True, text=True, check=True, timeout=30)
    containers = [json.loads(line) for line in result.stdout.splitlines()]
    if sorted(info['service'] for info in containers) != ['db', 'frontend', 'web']:
        raise ValueError('The selected project does not contain the expected services.')
    for info in containers:
        service = info['service']
        if not info['running'] or info['health'] != 'healthy' or info['restart'] != 'unless-stopped':
            raise ValueError(f'{service}: expected a healthy running service with restart policy unless-stopped.')
        ports = {'8080/tcp': [{'HostIp': '127.0.0.1', 'HostPort': config['HTTP_PORT']}]} if service == 'frontend' else {}
        if (info['ports'] or {}) != ports:
            raise ValueError(f'{service}: published ports differ from the configured loopback-only frontend binding.')
        if any(mount['Type'] == 'bind' for mount in info['mounts']):
            raise ValueError(f'{service}: deployment containers must not use host bind mounts.')
        if service in ('web', 'frontend'):
            if info['image'] != f"{config['INSTANCE_ID']}-{service}:{config['RELEASE']}":
                raise ValueError(f'{service}: running release differs from the selected release. Apply it with up.')
            if (info['user'].split(':')[0] in ('', '0', 'root') or not info['read_only']
                    or 'ALL' not in (info['cap_drop'] or [])
                    or 'no-new-privileges:true' not in (info['security'] or [])):
                raise ValueError(f'{service}: expected a non-root read-only container with restricted privileges.')
        if service in ('db', 'web'):
            volume, destination = (('database', '/var/lib/postgresql/data') if service == 'db'
                                   else ('uploads', '/var/lib/task-tracker/uploads'))
            if not any(mount['Type'] == 'volume' and mount['Name'] == f"{config['INSTANCE_ID']}_{volume}"
                       and mount['Destination'] == destination for mount in info['mounts']):
                raise ValueError(f'{service}: expected this environment\'s persistent {volume} volume.')
    print('PASS containers: health, selected release, loopback ports, persistent volumes and runtime restrictions')
    expected = dict(DEBUG=False, APP_ENV=config['ENVIRONMENT_ROLE'], INSTANCE_ID=config['INSTANCE_ID'],
                    APP_BASE_PATH=config['APP_BASE_PATH'], TIME_ZONE=config['WORKING_TIME_ZONE'],
                    SESSION_COOKIE_SECURE=config['COOKIE_SECURE'] == 'true',
                    CSRF_COOKIE_SECURE=config['COOKIE_SECURE'] == 'true',
                    SESSION_COOKIE_PATH=config['APP_BASE_PATH'], CSRF_COOKIE_PATH=config['APP_BASE_PATH'],
                    CSRF_TRUSTED_ORIGINS=[config['PUBLIC_ORIGIN']])
    source = ("import os,json; os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings'); "
              'from django.conf import settings; '
              f'print(json.dumps({{key:getattr(settings,key) for key in {list(expected)!r}}}))')
    result = compose(name, config, 'exec', '-T', 'web', 'python', '-c', source,
                     capture_output=True, text=True, timeout=30)
    if json.loads(result.stdout) != expected:
        raise ValueError('Backend settings differ from the configured role, identity, zone, debug or cookie/origin settings.')
    print('PASS settings: configured role, identity, time zone, debug disabled and cookie/origin settings')
    verify_http(config)
    print(f'PASS {name}: deployment verification complete; application data was not modified.')


def account(name, config, args):
    command = 'bootstrap_admin' if args.action == 'bootstrap' else 'reset_password'
    email = args.email or input('Administrator email: ').strip()
    if not email:
        raise ValueError('An email address is required.')
    options = {'email': email}
    if command == 'reset_password':
        options.update(reactivate=args.reactivate, grant_admin=args.grant_admin)
    if args.action == 'bootstrap' or args.generate_password:
        password = secrets.token_urlsafe(24)
        source = (
            'import json,sys; from unittest.mock import patch; '
            'from django.core.management import call_command; '
            'data=json.load(sys.stdin); '
            f"patcher=patch('accounts.management.commands.{command}.getpass', return_value=data.pop('password')); "
            f"patcher.start(); call_command('{command}', **data)"
        )
        compose(name, config, 'exec', '-T', 'web', 'python', 'manage.py', 'shell', '-c', source,
                input=json.dumps({**options, 'password': password}), text=True)
        print(f"URL: {config['PUBLIC_ORIGIN']}{config['APP_BASE_PATH']}\nEmail: {email}\nPassword: {password}")
    else:
        flags = [f'--email={email}']
        if command == 'reset_password':
            flags += [flag for key, flag in [('reactivate', '--reactivate'), ('grant_admin', '--grant-admin')] if options[key]]
        compose(name, config, 'exec', 'web', 'python', 'manage.py', command, *flags)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest='action', required=True)
    init = actions.add_parser('init', help='Create one private, independent environment configuration.')
    init.add_argument('name')
    init.add_argument('--role', choices=['production', 'evaluation', 'agent'], required=True)
    init.add_argument('--port', type=int, required=True)
    init.add_argument('--path', required=True)
    init.add_argument('--origin')
    init.add_argument('--zone', default='UTC')
    init.add_argument('--release')
    actions.add_parser('list', help='List configured environments without secrets.')
    for action in ('build', 'up', 'down', 'status', 'logs', 'check', 'verify'):
        help_options = {'help': 'Verify an existing deployment without changing application data.'} if action == 'verify' else {}
        action_parser = actions.add_parser(action, **help_options)
        action_parser.add_argument('name')
        if action == 'build':
            action_parser.add_argument('--release')
    for action in ('bootstrap', 'reset-password'):
        action_parser = actions.add_parser(action)
        action_parser.add_argument('name')
        action_parser.add_argument('--email', help='Omit to enter the email interactively.')
        action_parser.add_argument('--generate-password', action='store_true')
        if action == 'reset-password':
            action_parser.add_argument('--reactivate', action='store_true')
            action_parser.add_argument('--grant-admin', action='store_true')
    args = parser.parse_args()
    with locked():
        if args.action == 'list':
            for file in sorted(DIRECTORY.glob('*.env')):
                describe(file.stem, load(file.stem))
            return
        if args.action == 'init':
            origin = args.origin or f'http://127.0.0.1:{args.port}'
            config = dict(INSTANCE_ID=f'task-tracker-env-{args.name}', ENVIRONMENT_ROLE=args.role,
                          APP_BASE_PATH=args.path if args.path.endswith('/') else args.path + '/', HTTP_PORT=str(args.port),
                          PUBLIC_ORIGIN=origin.removesuffix('/'), PUBLIC_SCHEME=urlsplit(origin).scheme,
                          PUBLIC_HOST=urlsplit(origin).hostname,
                          COOKIE_SECURE=str(urlsplit(origin).scheme == 'https').lower(),
                          DJANGO_SECRET_KEY=secrets.token_hex(40), POSTGRES_PASSWORD=secrets.token_hex(32),
                          RELEASE=args.release or datetime.now(timezone.utc).strftime('prepared-%Y%m%dT%H%M%SZ'),
                          WORKING_TIME_ZONE=args.zone, WEB_WORKERS='2')
            name_path(args.name)
            validate(config)
            check_registry(config)
            if name_path(args.name).exists():
                raise ValueError('This environment already has a configuration; it was not overwritten.')
            assert_new_project(config)
            save(args.name, config, create=True)
            describe(args.name, config)
            return
        config = load(args.name)
        check_registry(config, excluding=args.name)
        if args.action == 'build':
            if args.release:
                config = {**config, 'RELEASE': args.release}
                validate(config)
            if all(image_exists(config, service) for service in ('web', 'frontend')):
                raise ValueError('This release already exists. Use up, or build with a new --release tag.')
            # Build using a temporary explicit release override; save the selection only on success.
            old = load(args.name)
            save(args.name, config)
            try:
                compose(args.name, config, 'build', 'web', 'frontend')
            except BaseException:
                save(args.name, old)
                raise
        elif args.action == 'up':
            if not all(image_exists(config, service) for service in ('web', 'frontend')):
                raise ValueError('Build this environment release before starting it.')
            compose(args.name, config, 'up', '-d', '--wait', '--wait-timeout', '150', 'db')
            compose(args.name, config, 'stop', 'frontend', 'web')
            compose(args.name, config, 'run', '--rm', '--no-deps', 'web', 'python', 'manage.py', 'migrate', '--noinput')
            compose(args.name, config, 'up', '-d', '--wait', '--wait-timeout', '150', 'web', 'frontend')
        elif args.action == 'down':
            compose(args.name, config, 'down')
        elif args.action == 'status':
            compose(args.name, config, 'ps')
        elif args.action == 'logs':
            compose(args.name, config, 'logs', '--tail', '100')
        elif args.action == 'check':
            compose(args.name, config, 'config', '--quiet')
            describe(args.name, config)
        elif args.action == 'verify':
            verify(args.name, config)
        else:
            account(args.name, config, args)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        sys.exit(f'Environment operation failed: {exc}')
