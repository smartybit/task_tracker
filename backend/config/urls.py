from django.urls import path

from accounts.views import CSRFView, LoginView, LogoutView, MeView, UsersView, UserView, ResetPasswordView
from access.views import GrantsView, OrganizationGrantView, ProjectGrantView
from core.views import HealthView
from projects.views import OrganizationsView, OrganizationView, ProjectsView, ProjectView

urlpatterns = [
    path('api/v1/health/', HealthView.as_view(), name='health'),
    path('api/v1/auth/csrf/', CSRFView.as_view()),
    path('api/v1/auth/login/', LoginView.as_view()),
    path('api/v1/auth/logout/', LogoutView.as_view()),
    path('api/v1/auth/me/', MeView.as_view()),
    path('api/v1/users/', UsersView.as_view()),
    path('api/v1/users/<uuid:pk>/', UserView.as_view()),
    path('api/v1/users/<uuid:pk>/password-reset/', ResetPasswordView.as_view()),
    path('api/v1/users/<uuid:user_id>/grants/', GrantsView.as_view()),
    path('api/v1/users/<uuid:user_id>/grants/organizations/<uuid:target_id>/', OrganizationGrantView.as_view()),
    path('api/v1/users/<uuid:user_id>/grants/projects/<uuid:target_id>/', ProjectGrantView.as_view()),
    path('api/v1/organizations/', OrganizationsView.as_view()),
    path('api/v1/organizations/<uuid:pk>/', OrganizationView.as_view()),
    path('api/v1/projects/', ProjectsView.as_view()),
    path('api/v1/projects/<uuid:pk>/', ProjectView.as_view()),
]
