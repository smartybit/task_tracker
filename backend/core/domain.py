from functools import wraps

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

from core.models import MutationLock


class DomainError(Exception):
    def __init__(self, code, message, status=400, fields=None):
        super().__init__(message)
        self.code, self.message, self.status, self.fields = code, message, status, fields


def mutation(operation):
    """All domain writers acquire this lock before checking mutable permissions."""
    @wraps(operation)
    def run(*args, **kwargs):
        try:
            with transaction.atomic():
                lock = MutationLock.objects.select_for_update().get(key='domain')
                result = operation(*args, **kwargs)
                lock.revision += 1
                lock.save(update_fields=['revision'])
                return result
        except IntegrityError as exc:
            raise DomainError('conflict', 'The change conflicts with existing records.', 409) from exc
    return run


def current_user(user):
    if user is None or not getattr(user, 'is_authenticated', False):
        raise DomainError('authentication_required', 'Sign in to continue.', 403)
    current = get_user_model().objects.filter(pk=user.pk, is_active=True).first()
    if current is None:
        raise DomainError('authentication_required', 'Sign in to continue.', 403)
    return current


def require_admin(user):
    user = current_user(user)
    if not user.is_admin:
        raise DomainError('permission_denied', 'Administrator access is required.', 403)
    return user


def find(model, pk):
    try:
        return model.objects.get(pk=pk)
    except model.DoesNotExist as exc:
        raise DomainError('not_found', 'The requested record is unavailable.', 404) from exc
