from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from access.services import replace_grant
from accounts.services import bootstrap_admin, create_account, reset_password, update_account
from core.domain import mutation
from projects.models import Organization, Project
from projects.services import save_organization, save_project
from timesheets.models import Timesheet


class Command(BaseCommand):
    help = 'Reset synthetic Stage 3 fixtures in the isolated test environment only.'

    @mutation
    def seed(self):
        User = get_user_model()
        password = 'synthetic-test-only-password'
        admin = User.objects.filter(email='admin@example.test').first()
        # This guarded test-only reset restores its known fixture administrator;
        # normal account/grant writes below use the same services as the API.
        if admin:
            admin.is_active = admin.is_admin = True
            admin.save(update_fields=['is_active', 'is_admin'])
        else:
            admin = bootstrap_admin({'email': 'admin@example.test', 'password': password})
        for email, name, is_admin in [
            ('admin@example.test', 'Test administrator', True),
            ('alice@example.test', 'Alice Example', False),
            ('bob@example.test', 'Bob Example', False),
        ]:
            values = dict(email=email, display_name=name, is_admin=is_admin, is_active=True,
                          read_others_timesheets=False, write_others_timesheets=False)
            user = User.objects.filter(email=email).first()
            if user is None:
                create_account(admin, {**values, 'password': password})
            else:
                Timesheet.objects.get_or_create(user=user)
                update_account(admin, user.pk, values)
                reset_password(admin, user.pk, {'password': password})
        from access.models import OrganizationGrant, ProjectGrant
        fixture_users = User.objects.filter(email__in=['admin@example.test', 'alice@example.test', 'bob@example.test'])
        OrganizationGrant.objects.filter(user__in=fixture_users).delete()
        ProjectGrant.objects.filter(user__in=fixture_users).delete()
        orgs = []
        for name in ['Example Studio', 'Example Client']:
            org = Organization.objects.filter(name=name).first()
            orgs.append(org or save_organization(admin, {'name': name}))
        for org, name in [(orgs[0], 'Internal'), (orgs[0], 'Website'), (orgs[1], 'Client Portal')]:
            if not Project.objects.filter(name=name, organization=org).exists():
                save_project(admin, {'name': name, 'organization': str(org.pk)})
        alice = User.objects.get(email='alice@example.test')
        bob = User.objects.get(email='bob@example.test')
        replace_grant(admin, alice.pk, 'organizations', orgs[0].pk, {'task_read': True, 'remark_write': True})
        portal = Project.objects.get(name='Client Portal', organization=orgs[1])
        replace_grant(admin, bob.pk, 'projects', portal.pk, {'task_write': True})

    def handle(self, *args, **options):
        if (settings.APP_ENV != 'test'
            or connection.settings_dict['NAME'] not in {'task_tracker_test', 'test_task_tracker_test'}
            or connection.settings_dict['USER'] != 'task_tracker_test'):
            raise CommandError('Refusing to seed outside the dedicated test environment.')
        self.seed()
        self.stdout.write('Reset 3 synthetic accounts, 2 organizations, 3 projects, and grants (no development data).')
