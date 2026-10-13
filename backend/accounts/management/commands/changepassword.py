from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Use account management or the reset_password server command.'

    def handle(self, *args, **options):
        raise CommandError('Use application account management or reset_password --email EMAIL.')
