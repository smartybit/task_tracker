from django.db import transaction
from rest_framework.response import Response
from rest_framework.views import APIView

from content.references import resolve_references
from core.models import MutationLock
from access.policies import can_task, can_remark
from content.models import ContentImage
from content.images import FORMATS, image_storage
from core.domain import DomainError, current_user
from django.http import FileResponse
from content.search import search_content


class ResolveView(APIView):
    @transaction.atomic
    def post(self, request):
        MutationLock.objects.select_for_update().get(pk='domain')
        return Response(resolve_references(request.user, request.data))


class SearchView(APIView):
    @transaction.atomic
    def get(self, request):
        MutationLock.objects.select_for_update().get(pk='domain')
        response = Response(search_content(request.user, request.query_params))
        response['Cache-Control'] = 'private, no-store'
        return response


class ImageView(APIView):
    @transaction.atomic
    def get(self, request, pk):
        MutationLock.objects.select_for_update().get(pk='domain')
        actor = current_user(request.user)
        image = ContentImage.objects.filter(pk=pk).select_related('source_task__project', 'source_remark__task__project').first()
        allowed = image and (can_task(actor, image.source_task.project) if image.source_task_id
                             else can_remark(actor, image.source_remark.task.project))
        if not allowed:
            raise DomainError('not_found', 'The requested record is unavailable.', 404)
        try:
            handle = image_storage().open(image.file_name, 'rb')
        except FileNotFoundError as exc:
            raise DomainError('not_found', 'The requested record is unavailable.', 404) from exc
        extension, mime = FORMATS[image.format]
        response = FileResponse(handle, content_type=mime, filename=f'{image.pk}.{extension}')
        response['Cache-Control'] = 'private, no-store'
        response['X-Content-Type-Options'] = 'nosniff'
        return response
