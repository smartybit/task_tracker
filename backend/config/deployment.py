"""Validate deployment settings independently from development/test defaults."""
import re
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured

DEPLOYED_ROLES = {'production', 'evaluation', 'agent'}


def deployment_settings(environ):
    role = environ.get('APP_ENV', 'development')
    if role not in {'development', 'test'} | DEPLOYED_ROLES:
        raise ImproperlyConfigured('APP_ENV must be development, test, production, evaluation or agent.')
    if role not in DEPLOYED_ROLES:
        return {}
    origin = environ.get('PUBLIC_ORIGIN', '')
    try:
        parsed = urlsplit(origin)
        port = parsed.port
    except ValueError as exc:
        raise ImproperlyConfigured('PUBLIC_ORIGIN has an invalid port.') from exc
    if (parsed.scheme not in {'http', 'https'} or not parsed.hostname
            or not re.fullmatch(r'[a-zA-Z0-9.-]+', parsed.hostname)
            or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment
            or origin != f'{parsed.scheme}://{parsed.netloc}' or port == 0):
        raise ImproperlyConfigured('PUBLIC_ORIGIN must be an HTTP(S) origin without a path or credentials.')
    secure = parsed.scheme == 'https'
    if not secure and parsed.hostname not in {'localhost', '127.0.0.1'}:
        raise ImproperlyConfigured('HTTP deployments require loopback/SSH access; public origins require HTTPS.')
    if environ.get('DJANGO_DEBUG', 'false') != 'false':
        raise ImproperlyConfigured('Deployed environments require DJANGO_DEBUG=false.')
    key = environ.get('DJANGO_SECRET_KEY', '')
    if len(key) < 50 or len(set(key)) < 5 or any(word in key.lower() for word in ('replace-with', 'development-only')):
        raise ImproperlyConfigured('Deployed environments require a unique random Django secret of at least 50 characters.')
    if environ.get('DJANGO_COOKIE_SECURE', 'false') != str(secure).lower():
        raise ImproperlyConfigured('DJANGO_COOKIE_SECURE must match the PUBLIC_ORIGIN scheme.')
    if environ.get('PUBLIC_SCHEME', parsed.scheme) != parsed.scheme:
        raise ImproperlyConfigured('PUBLIC_SCHEME must match PUBLIC_ORIGIN.')
    return {
        'ALLOWED_HOSTS': list(dict.fromkeys([parsed.hostname, 'localhost', '127.0.0.1'])),
        'CSRF_TRUSTED_ORIGINS': [origin],
        # Only the private frontend can reach the backend. It overwrites this
        # header with the configured scheme, ignoring client forwarding headers.
        'SECURE_PROXY_SSL_HEADER': ('HTTP_X_FORWARDED_PROTO', 'https'),
        'SECURE_SSL_REDIRECT': secure,
        'SECURE_REDIRECT_EXEMPT': [r'^api/v1/health/$'],
        # HSTS is owned by the public host proxy, shared by applications on that host.
        'SECURE_HSTS_SECONDS': 0,
    }
