from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction


class Command(BaseCommand):
    help = "Seed synthetic accounts in the isolated test environment only."

    def handle(self, *args, **options):
        if (
            settings.APP_ENV != "test"
            or connection.settings_dict["NAME"] not in {
                "task_tracker_test", "test_task_tracker_test"
            }
            or connection.settings_dict["USER"] != "task_tracker_test"
        ):
            raise CommandError("Refusing to seed outside the dedicated test environment.")
        User = get_user_model()
        with transaction.atomic():
            for email, name, admin in [
                ("admin@example.test", "Test administrator", True),
                ("alice@example.test", "Alice Example", False),
                ("bob@example.test", "Bob Example", False),
            ]:
                user, _ = User.objects.get_or_create(email=email)
                user.display_name = name
                user.is_active = True
                user.is_admin = admin
                user.read_others_timesheets = False
                user.write_others_timesheets = False
                user.set_password("synthetic-test-only-password")
                user.save()
        self.stdout.write("Seeded 3 synthetic test accounts (no production data).")
