from typing import Any

from rest_framework import serializers

from apps.datasets.models import Dataset
from apps.datasets.services.formats import MESSAGE_ROLES


class RowTurnSerializer(serializers.Serializer[dict[str, Any]]):
    role = serializers.ChoiceField(choices=MESSAGE_ROLES, read_only=True)
    content = serializers.CharField(read_only=True, allow_blank=True)
    thinking = serializers.CharField(read_only=True, allow_blank=True)


class RowSerializer(serializers.Serializer[dict[str, Any]]):
    index = serializers.IntegerField(read_only=True)
    messages = RowTurnSerializer(many=True, read_only=True)
    text = serializers.CharField(read_only=True, allow_blank=True)

    def to_representation(self, instance: dict[str, Any]) -> dict[str, Any]:
        turns: object = instance.get("messages")
        text: object = instance.get("text")
        return {
            "index": instance.get("index", 0),
            "messages": [
                {
                    "role": str(turn.get("role", "")),
                    "content": str(turn.get("content", "")),
                    "thinking": str(turn.get("thinking", "")),
                }
                for turn in (turns if isinstance(turns, list) else [])
                if isinstance(turn, dict)
            ],
            "text": text if isinstance(text, str) else "",
        }


class MappingSerializer(serializers.Serializer[dict[str, Any]]):
    format = serializers.ChoiceField(choices=Dataset.Format.choices)
    conversation = serializers.CharField(
        required=False, allow_blank=True, max_length=200, default=""
    )
    system = serializers.CharField(required=False, allow_blank=True, max_length=200, default="")
    prompt = serializers.CharField(required=False, allow_blank=True, max_length=200, default="")
    input = serializers.CharField(required=False, allow_blank=True, max_length=200, default="")
    reply = serializers.CharField(required=False, allow_blank=True, max_length=200, default="")
    thinking = serializers.CharField(required=False, allow_blank=True, max_length=200, default="")
    text = serializers.CharField(required=False, allow_blank=True, max_length=200, default="")
