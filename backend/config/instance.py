import re

from django.core.exceptions import ImproperlyConfigured


def instance_config(environ):
    path = environ.get('APP_BASE_PATH', '/')
    if not re.fullmatch(r'/(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_-]*', path):
        raise ImproperlyConfigured('APP_BASE_PATH must be / or an absolute path of plain URL segments.')
    path = path if path.endswith('/') else path + '/'
    identifier = environ.get('INSTANCE_ID', 'task-tracker-dev')
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,62}', identifier):
        raise ImproperlyConfigured('INSTANCE_ID must be a lowercase alphanumeric/hyphen slug, at most 63 characters.')
    secure = environ.get('DJANGO_COOKIE_SECURE', 'false')
    if secure not in ('true', 'false'):
        raise ImproperlyConfigured('DJANGO_COOKIE_SECURE must be true or false.')
    return path, identifier, secure == 'true'
