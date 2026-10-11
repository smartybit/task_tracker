from django.http import FileResponse
from rest_framework.response import Response
from rest_framework.views import APIView

from core.domain import DomainError
from reports.services import export_csv, options, report


class OptionsView(APIView):
    def get(self, request):
        if request.query_params:
            raise DomainError('invalid_input', 'Report options do not accept filters.')
        return Response(options(request.user), headers={'Cache-Control': 'no-store'})


class ReportView(APIView):
    def get(self, request, kind):
        return Response(report(request.user, kind, request.query_params), headers={'Cache-Control': 'no-store'})


class CSVView(APIView):
    def get(self, request):
        output, filename = export_csv(request.user, request.query_params)
        response = FileResponse(output, as_attachment=True, filename=filename, content_type='text/csv; charset=utf-8')
        response['Cache-Control'] = 'no-store'
        return response
