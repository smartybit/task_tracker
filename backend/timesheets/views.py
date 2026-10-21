from datetime import date

from django.contrib.auth import get_user_model

from rest_framework.response import Response
from rest_framework.views import APIView

from core.domain import DomainError, current_user
from timesheets.services import command, preview, read_day, sheet_context
from core.api import page


class DirectoryView(APIView):
    def get(self, request):
        user = current_user(request.user)
        users = get_user_model().objects.order_by('display_name', 'id')
        if not (user.read_others_timesheets or user.write_others_timesheets):
            users = users.filter(pk=user.pk)
        return page(users, request, lambda person: {
            'id': str(person.pk), 'display_name': person.display_name or 'Unnamed user'})


class ContextView(APIView):
    def get(self, request, user_id):
        return Response(sheet_context(request.user, user_id))


class DayView(APIView):
    def get(self, request, user_id, day):
        try:
            selected = date.fromisoformat(day)
        except ValueError as exc:
            raise DomainError('invalid_input', 'Select a valid calendar date.') from exc
        return Response(read_day(request.user, user_id, selected))


class CommandView(APIView):
    def post(self, request, user_id):
        return Response(command(request.user, user_id, request.data))


class PreviewView(APIView):
    def post(self, request, user_id):
        return Response(preview(request.user, user_id, request.data))
