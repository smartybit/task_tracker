from rest_framework import serializers

from core.api import StrictSerializer


class LoginInput(StrictSerializer):
    email = serializers.CharField(max_length=254)
    password = serializers.CharField(trim_whitespace=False, write_only=True)


class UserInput(StrictSerializer):
    email = serializers.EmailField(max_length=254)
    display_name = serializers.CharField(max_length=200, allow_blank=True, required=False)
    password = serializers.CharField(trim_whitespace=False, write_only=True)
    is_admin = serializers.BooleanField(required=False)
    is_active = serializers.BooleanField(required=False)
    read_others_timesheets = serializers.BooleanField(required=False)
    write_others_timesheets = serializers.BooleanField(required=False)


class UserUpdate(StrictSerializer):
    email = serializers.EmailField(max_length=254, required=False)
    display_name = serializers.CharField(max_length=200, allow_blank=True, required=False)
    is_admin = serializers.BooleanField(required=False)
    is_active = serializers.BooleanField(required=False)
    read_others_timesheets = serializers.BooleanField(required=False)
    write_others_timesheets = serializers.BooleanField(required=False)


class PasswordInput(StrictSerializer):
    password = serializers.CharField(trim_whitespace=False, write_only=True)


def user_data(user):
    return {field: str(user.pk) if field == 'id' else getattr(user, field) for field in
            ('id', 'email', 'display_name', 'is_admin', 'is_active', 'read_others_timesheets', 'write_others_timesheets')}
