from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError

from accounts.serializers import PasswordInput, UserInput, UserUpdate
from core.domain import DomainError, find, mutation, require_admin

User = get_user_model()


def validate(serializer_type, data):
    serializer = serializer_type(data=data)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def checked_password(user, password):
    try:
        password_validation.validate_password(password, user)
    except ValidationError as exc:
        raise DomainError('invalid_input', 'Choose a stronger password.', fields={'password': exc.messages}) from exc
    user.set_password(password)


def new_user(data):
    values = validate(UserInput, data)
    password = values.pop('password')
    values['email'] = User.objects.normalize_email(values['email'])
    user = User(**values)
    checked_password(user, password)
    user.save()
    from timesheets.models import Timesheet
    Timesheet.objects.create(user=user)
    return user


@mutation
def bootstrap_admin(data):
    if User.objects.filter(is_admin=True).exists():
        raise DomainError('bootstrap_unavailable', 'An administrator already exists.', 409)
    return new_user({**data, 'is_admin': True})


@mutation
def create_account(actor, data):
    require_admin(actor)
    return new_user(data)


@mutation
def update_account(actor, user_id, data):
    require_admin(actor)
    user = find(User, user_id)
    values = validate(UserUpdate, data)
    if user.is_active and values.get('is_active') is False:
        user.session_version += 1
    for field, value in values.items():
        setattr(user, field, User.objects.normalize_email(value) if field == 'email' else value)
    user.save()
    return user


@mutation
def reset_password(actor, user_id, data):
    require_admin(actor)
    user = find(User, user_id)
    checked_password(user, validate(PasswordInput, data)['password'])
    user.save(update_fields=['password'])
    return user
