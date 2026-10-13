from getpass import getpass

from django.core.management.base import BaseCommand, CommandError
from rest_framework.exceptions import ValidationError

from accounts.services import recover_account
from core.domain import DomainError


class Command(BaseCommand):
    help = 'Reset an existing account password, with explicit server recovery options.'

    def add_arguments(self, parser):
        parser.add_argument('--email', required=True)
        parser.add_argument('--reactivate', action='store_true', help='Reactivate the selected account.')
        parser.add_argument('--grant-admin', action='store_true', help='Grant application administrator privileges.')

    def handle(self, *args, **options):
        password = getpass('New password: ')
        if password != getpass('New password again: '):
            raise CommandError('Passwords do not match.')
        try:
            user = recover_account(options['email'], password,
                                   reactivate=options['reactivate'], grant_admin=options['grant_admin'])
        except (DomainError, ValidationError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(f'Password reset. Account is {"active" if user.is_active else "inactive"}; '
                          f'application administrator: {"yes" if user.is_admin else "no"}. '
                          'Existing sessions require a new sign-in.')
