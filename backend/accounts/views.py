from django.contrib.auth import authenticate, login, logout, get_user_model
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.serializers import LoginInput, user_data
from accounts.services import create_account, reset_password, update_account
from core.api import page
from core.domain import DomainError, current_user, find, require_admin


class CSRFView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({'csrf_token': get_token(request._request)})


@method_decorator(csrf_protect, name='dispatch')
class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(request._request, **serializer.validated_data)
        if user is None:
            raise DomainError('invalid_credentials', 'Email or password is incorrect.', 403)
        login(request._request, user)
        return Response({'user': user_data(user), 'csrf_token': get_token(request._request)})


class LogoutView(APIView):
    def post(self, request):
        logout(request._request)
        return Response({'csrf_token': get_token(request._request)})


class MeView(APIView):
    def get(self, request):
        return Response(user_data(current_user(request.user)))


class UsersView(APIView):
    def get(self, request):
        require_admin(request.user)
        return page(get_user_model().objects.order_by('email', 'id'), request, user_data)

    def post(self, request):
        return Response(user_data(create_account(request.user, request.data)), status=201)


class UserView(APIView):
    def get(self, request, pk):
        require_admin(request.user)
        return Response(user_data(find(get_user_model(), pk)))

    def patch(self, request, pk):
        return Response(user_data(update_account(request.user, pk, request.data)))


class ResetPasswordView(APIView):
    def post(self, request, pk):
        reset_password(request.user, pk, request.data)
        return Response({'id': str(pk)})
