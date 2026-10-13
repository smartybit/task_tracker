from django.conf import settings


class InstanceHeadersMiddleware:
    """Public mount metadata for the frontend's startup consistency check."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response['X-Task-Tracker-Base-Path'] = settings.APP_BASE_PATH
        response['X-Task-Tracker-Instance'] = settings.INSTANCE_ID
        return response
