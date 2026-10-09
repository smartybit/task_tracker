from datetime import date

from rest_framework.response import Response
from rest_framework.views import APIView

from core.domain import DomainError
from timesheets.services import command, preview, read_day


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
