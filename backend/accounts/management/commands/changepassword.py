from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Use administrator account management to reset passwords.'

    def handle(self, *args, **options):
        raise CommandError('Reset passwords through the application account management screen.')
