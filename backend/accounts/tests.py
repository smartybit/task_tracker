from django.contrib.auth import authenticate, get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

User = get_user_model()


class UserTests(TestCase):
    def test_email_normalization_and_password_hashing(self):
        user = User.objects.create_user(" Alice@Example.COM ", "test-only-password")
        self.assertEqual(user.email, "alice@example.com")
        self.assertNotEqual(user.password, "test-only-password")
        self.assertTrue(user.check_password("test-only-password"))
        self.assertFalse(user.is_admin)
        self.assertFalse(user.read_others_timesheets)
        self.assertFalse(user.write_others_timesheets)

    def test_database_rejects_case_insensitive_duplicate(self):
        User.objects.create_user("alice@example.com")
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create(email="ALICE@example.com")

    def test_email_is_required(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(" ")

    def test_authentication_normalizes_email_and_blocks_inactive_accounts(self):
        user = User.objects.create_user("alice@example.com", "test-only-password")
        self.assertEqual(
            authenticate(email=" ALICE@EXAMPLE.COM ", password="test-only-password"), user
        )
        user.is_active = False
        user.save(update_fields=["is_active"])
        self.assertIsNone(
            authenticate(email="alice@example.com", password="test-only-password")
        )

    def test_administrator_has_no_implicit_timesheet_flags(self):
        user = User.objects.create_superuser("admin@example.com", "test-only-password")
        self.assertTrue(user.is_admin)
        self.assertFalse(user.read_others_timesheets)
        self.assertFalse(user.write_others_timesheets)
        self.assertFalse(hasattr(user, "is_superuser"))
