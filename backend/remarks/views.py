from django.db import transaction
from rest_framework.response import Response
from rest_framework.views import APIView

from core.api import page
from core.domain import find
from core.models import MutationLock
from remarks.models import Remark
from remarks.services import change_remark, remark_data, require_remark
from tasks.models import Task


class RemarksView(APIView):
    @transaction.atomic
    def get(self, request, task_id):
        MutationLock.objects.select_for_update().get(pk='domain')
        task = find(Task, task_id)
        require_remark(request.user, task)
        rows = task.remarks.select_related('author')
        # Shared stars have a separate chronological stream, not a reordering
        # of the conversation; pagination applies independently to each stream.
        if request.query_params.get('starred') == 'true':
            rows = rows.filter(starred=True)
        return page(rows, request, remark_data)

    def post(self, request, task_id):
        return Response(change_remark(request.user, 'create', request.data, task_id), status=201)


class RemarkView(APIView):
    @transaction.atomic
    def get(self, request, pk):
        MutationLock.objects.select_for_update().get(pk='domain')
        remark = find(Remark, pk)
        require_remark(request.user, remark.task)
        return Response(remark_data(remark))

    def patch(self, request, pk):
        return Response(change_remark(request.user, 'edit', request.data, pk))

    def delete(self, request, pk):
        return Response(change_remark(request.user, 'delete', request.data, pk))


class StarView(APIView):
    def post(self, request, pk):
        return Response(change_remark(request.user, 'star', request.data, pk))
