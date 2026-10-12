from django.urls import path

from accounts.views import CSRFView, LoginView, LogoutView, MeView, UsersView, UserView, ResetPasswordView
from access.views import GrantsView, OrganizationGrantView, ProjectGrantView
from core.views import HealthView
from projects.views import OrganizationsView, OrganizationView, ProjectsView, ProjectView

from tasks.views import StatusesView, StatusView, OwnersView, TasksView, TaskView, HistoryView, CommandView, PreviewView
from timesheets import views as timesheet_views
from reports import views as report_views
from remarks import views as remark_views
from content import views as content_views

urlpatterns = [
    path('api/v1/images/<uuid:pk>/', content_views.ImageView.as_view()),
    path('api/v1/references/resolve/', content_views.ResolveView.as_view()),
    path('api/v1/tasks/<uuid:task_id>/remarks/', remark_views.RemarksView.as_view()),
    path('api/v1/remarks/<uuid:pk>/', remark_views.RemarkView.as_view()),
    path('api/v1/remarks/<uuid:pk>/star/', remark_views.StarView.as_view()),
    path('api/v1/reports/options/', report_views.OptionsView.as_view()),
    path('api/v1/reports/records.csv', report_views.CSVView.as_view()),
    path('api/v1/timesheets/', timesheet_views.DirectoryView.as_view()),
    path('api/v1/timesheets/<uuid:user_id>/context/', timesheet_views.ContextView.as_view()),
    path('api/v1/timesheets/<uuid:user_id>/days/<str:day>/', timesheet_views.DayView.as_view()),
    path('api/v1/timesheets/<uuid:user_id>/commands/', timesheet_views.CommandView.as_view()),
    path('api/v1/timesheets/<uuid:user_id>/commands/preview/', timesheet_views.PreviewView.as_view()),
    path('api/v1/statuses/', StatusesView.as_view()),
    path('api/v1/statuses/<uuid:pk>/', StatusView.as_view()),
    path('api/v1/projects/<uuid:pk>/eligible-owners/', OwnersView.as_view()),
    path('api/v1/tasks/', TasksView.as_view()),
    path('api/v1/tasks/preview/', PreviewView.as_view(), {'kind': 'create'}),
    path('api/v1/tasks/<uuid:pk>/', TaskView.as_view()),
    path('api/v1/tasks/<uuid:pk>/history/', HistoryView.as_view()),
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

for report in ('projects', 'people-days', 'tasks'):
    urlpatterns.append(path(f'api/v1/reports/{report}/', report_views.ReportView.as_view(), {'kind': report}))

for command in ('owner', 'status', 'move'):
    urlpatterns.append(path(f'api/v1/tasks/<uuid:pk>/{command}/', CommandView.as_view(), {'kind': command}))
for command in ('status', 'move', 'delete'):
    urlpatterns.append(path(f'api/v1/tasks/<uuid:pk>/{command}/preview/', PreviewView.as_view(), {'kind': command}))
