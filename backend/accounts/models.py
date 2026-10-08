import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models, transaction
from django.db.models.functions import Lower
from django.utils import timezone
from django.utils.crypto import salted_hmac


class UserManager(BaseUserManager):
    use_in_migrations = True

    @classmethod
    def normalize_email(cls, email):
        return (email or "").strip().lower()

    def get_by_natural_key(self, email):
        return self.get(email__iexact=self.normalize_email(email))

    def create_user(self, email, password=None, **extra_fields):
        email = self.normalize_email(email)
        if not email:
            raise ValueError("Email is required.")
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        from timesheets.models import Timesheet
        with transaction.atomic(using=self._db):
            user.save(using=self._db)
            Timesheet.objects.using(self._db).create(user=user)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        # Low-level compatibility helper; the application bootstrap command uses
        # the guarded service. There is no permission-bypassing superuser role.
        extra_fields.setdefault("is_admin", True)
        if extra_fields["is_admin"] is not True:
            raise ValueError("An administrator must have is_admin=True.")
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    display_name = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)
    is_admin = models.BooleanField(default=False)
    read_others_timesheets = models.BooleanField(default=False)
    write_others_timesheets = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    session_version = models.PositiveBigIntegerField(default=0)

    objects = UserManager()
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower("email"), name="user_email_case_insensitive_unique")
        ]

    def _get_session_auth_hash(self, secret=None):
        # Deactivation permanently revokes existing sessions even if an account
        # is later reactivated. Password resets remain invalidating as usual.
        return salted_hmac(
            'accounts.User.get_session_auth_hash',
            f'{self.password}:{self.session_version}',
            secret=secret, algorithm='sha256',
        ).hexdigest()

    def __str__(self):
        return self.display_name or self.email
