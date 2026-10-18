from typing import Any

from rest_framework import serializers

from apps.members.roles import LADDER


class MemberSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.IntegerField(read_only=True)
    username = serializers.CharField(read_only=True)
    first_name = serializers.CharField(read_only=True, allow_blank=True)
    last_name = serializers.CharField(read_only=True, allow_blank=True)
    email = serializers.EmailField(read_only=True, allow_blank=True)
    role = serializers.ChoiceField(choices=list(LADDER), read_only=True, allow_null=True)
    owner = serializers.BooleanField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    is_self = serializers.BooleanField(read_only=True)
    last_login = serializers.DateTimeField(read_only=True, allow_null=True)
    date_joined = serializers.DateTimeField(read_only=True)


class NewMemberSerializer(serializers.Serializer[dict[str, Any]]):
    username = serializers.RegexField(r"^[\w.@+-]+$", max_length=150)
    password = serializers.CharField(max_length=128, trim_whitespace=False, write_only=True)
    role = serializers.ChoiceField(choices=list(LADDER))
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)


class MemberChangeSerializer(serializers.Serializer[dict[str, Any]]):
    role = serializers.ChoiceField(choices=list(LADDER), required=False)
    is_active = serializers.BooleanField(required=False)
