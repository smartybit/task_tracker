from django.http import JsonResponse
from rest_framework import serializers
from rest_framework.exceptions import NotAuthenticated, PermissionDenied
from rest_framework.response import Response
from rest_framework.views import exception_handler

from core.domain import DomainError


class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if not isinstance(data, dict):
            raise serializers.ValidationError({'non_field_errors': ['Expected a JSON object.']})
        unknown = set(data) - set(self.fields)
        if unknown:
            raise serializers.ValidationError({key: ['Unknown field.'] for key in sorted(unknown)})
        return super().to_internal_value(data)


def api_exception_handler(exc, context):
    if isinstance(exc, DomainError):
        body = {'code': exc.code, 'message': exc.message}
        if exc.fields:
            body['fields'] = exc.fields
        return Response(body, status=exc.status)
    response = exception_handler(exc, context)
    if response is not None:
        code = 'invalid_input'
        message = 'Check the submitted values.'
        if isinstance(exc, NotAuthenticated):
            code, message = 'authentication_required', 'Sign in to continue.'
        elif isinstance(exc, PermissionDenied):
            code, message = 'permission_denied', 'You do not have access to this action.'
        elif response.status_code == 404:
            code, message = 'not_found', 'The requested record is unavailable.'
        elif response.status_code == 405:
            code, message = 'method_not_allowed', 'This request method is unavailable.'
        response.data = {'code': code, 'message': message, 'fields': response.data}
    return response


def csrf_failure(request, reason=''):
    return JsonResponse({'code': 'csrf_failed', 'message': 'Refresh the page and try again.'}, status=403)


def page(queryset, request, serialize):
    try:
        number = int(request.query_params.get('page', '1'))
    except ValueError as exc:
        raise DomainError('invalid_input', 'Page must be a positive integer.') from exc
    if number < 1:
        raise DomainError('invalid_input', 'Page must be a positive integer.')
    size = 50
    count = queryset.count()
    return Response({'count': count, 'next': number + 1 if number * size < count else None,
                     'results': [serialize(item) for item in queryset[(number-1)*size:number*size]]})
