from django.urls import path

from core.views import HealthView

urlpatterns = [path("api/v1/health/", HealthView.as_view(), name="health")]
