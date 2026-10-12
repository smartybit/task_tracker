from django.db import transaction
from rest_framework.response import Response
from rest_framework.views import APIView

from content.references import resolve_references
from core.models import MutationLock


class ResolveView(APIView):
    @transaction.atomic
    def post(self, request):
        MutationLock.objects.select_for_update().get(pk='domain')
        return Response(resolve_references(request.user, request.data))
