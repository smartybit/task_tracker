from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import PermissionDenied

from core.domain import DomainError


class BrowserSessionAuthentication(SessionAuthentication):
    def enforce_csrf(self, request):
        try:
            super().enforce_csrf(request)
        except PermissionDenied as exc:
            raise DomainError('csrf_failed', 'Refresh the page and try again.', 403) from exc
