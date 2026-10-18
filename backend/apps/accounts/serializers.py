from typing import Any

from rest_framework import serializers


class SignInSerializer(serializers.Serializer[dict[str, Any]]):
    username = serializers.CharField(max_length=150, trim_whitespace=True)
    password = serializers.CharField(max_length=128, trim_whitespace=False, write_only=True)


class IdentitySerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.IntegerField(read_only=True)
    username = serializers.CharField(read_only=True)
    email = serializers.EmailField(read_only=True, allow_blank=True)
    first_name = serializers.CharField(read_only=True, allow_blank=True)
    last_name = serializers.CharField(read_only=True, allow_blank=True)
    is_staff = serializers.BooleanField(read_only=True)
    is_superuser = serializers.BooleanField(read_only=True)
    groups = serializers.ListField(child=serializers.CharField(), read_only=True)
    permissions = serializers.ListField(child=serializers.CharField(), read_only=True)
