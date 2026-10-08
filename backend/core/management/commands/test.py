from django.conf import settings
from django.core.management.base import CommandError
from django.core.management.commands.test import Command as DjangoTestCommand


class Command(DjangoTestCommand):
    def handle(self, *test_labels, **options):
        if settings.APP_ENV != "test":
            raise CommandError("Run tests using the isolated test configuration, not development.")
        return super().handle(*test_labels, **options)
