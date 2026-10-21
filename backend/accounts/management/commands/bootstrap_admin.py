from getpass import getpass

from django.core.management.base import BaseCommand, CommandError
from rest_framework.exceptions import ValidationError

from accounts.services import bootstrap_admin
from core.domain import DomainError


class Command(BaseCommand):
    help = 'Interactively create the first application administrator (no default credentials).'

    def add_arguments(self, parser):
        parser.add_argument('--email', required=True)
        parser.add_argument('--display-name', default='')

    def handle(self, *args, **options):
        password = getpass('Password: ')
        if password != getpass('Password again: '):
            raise CommandError('Passwords do not match.')
        try:
            bootstrap_admin({'email': options['email'], 'display_name': options['display_name'], 'password': password})
        except (DomainError, ValidationError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write('First administrator created. Sign in to manage accounts and grants.')
