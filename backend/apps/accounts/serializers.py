"""Shape only — field mapping and field-level validation.

No queries, no cross-object rules, no side effects. Whether the credentials
are correct is a service decision, not a serializer one.
"""
from rest_framework import serializers


class SignInSerializer(serializers.Serializer):
    """Input for `POST /api/auth/login/`."""

    username = serializers.CharField(max_length=150, trim_whitespace=True)
    password = serializers.CharField(max_length=128, trim_whitespace=False, write_only=True)


class IdentitySerializer(serializers.Serializer):
    """Output for `GET /api/auth/me/`. Mirrors `AccountService.identity()`."""

    id = serializers.IntegerField(read_only=True)
    username = serializers.CharField(read_only=True)
    email = serializers.EmailField(read_only=True, allow_blank=True)
    first_name = serializers.CharField(read_only=True, allow_blank=True)
    last_name = serializers.CharField(read_only=True, allow_blank=True)
    is_staff = serializers.BooleanField(read_only=True)
    is_superuser = serializers.BooleanField(read_only=True)
    groups = serializers.ListField(child=serializers.CharField(), read_only=True)
    permissions = serializers.ListField(child=serializers.CharField(), read_only=True)
