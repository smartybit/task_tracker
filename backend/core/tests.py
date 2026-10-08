from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DatabaseError, connection
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from core.models import MutationLock


class FoundationTests(TestCase):
    def test_database_is_postgresql(self):
        self.assertEqual(connection.vendor, "postgresql")

    def test_coordination_row_exists_after_migrations(self):
        self.assertEqual(MutationLock.objects.get(key="domain").revision, 0)

    def test_health_is_public_and_checks_database(self):
        response = APIClient().get("/api/v1/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "status": "ok", "database": "postgresql", "api_version": "v1"
        })

    def test_database_failure_has_no_sensitive_details(self):
        with patch("core.views.connection.cursor", side_effect=DatabaseError("secret")):
            response = APIClient().get("/api/v1/health/")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "unavailable"})

    def test_no_unrestricted_admin_or_signup_route(self):
        client = APIClient()
        self.assertEqual(client.get("/admin/").status_code, 404)
        self.assertEqual(client.post("/api/v1/auth/register/", {}).status_code, 404)

    def test_seed_is_repeatable(self):
        call_command("seed_test_data", verbosity=0)
        call_command("seed_test_data", verbosity=0)
        self.assertEqual(get_user_model().objects.count(), 3)

    @override_settings(APP_ENV="development")
    def test_seed_refuses_development(self):
        with self.assertRaises(CommandError):
            call_command("seed_test_data", verbosity=0)
        self.assertEqual(get_user_model().objects.count(), 0)

    @override_settings(APP_ENV="development")
    def test_runner_refuses_development(self):
        with self.assertRaises(CommandError):
            call_command("test", verbosity=0)
