from rest_framework.response import Response
from rest_framework.views import APIView

from access.services import grants_data, replace_grant


class GrantsView(APIView):
    def get(self, request, user_id):
        return Response(grants_data(request.user, user_id))


class OrganizationGrantView(APIView):
    def put(self, request, user_id, target_id):
        return Response(replace_grant(request.user, user_id, 'organizations', target_id, request.data))


class ProjectGrantView(APIView):
    def put(self, request, user_id, target_id):
        return Response(replace_grant(request.user, user_id, 'projects', target_id, request.data))
