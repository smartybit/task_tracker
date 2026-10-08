from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Use bootstrap_admin for the first application administrator.'

    def handle(self, *args, **options):
        raise CommandError('Use bootstrap_admin --email ADDRESS, then manage accounts in the application.')
