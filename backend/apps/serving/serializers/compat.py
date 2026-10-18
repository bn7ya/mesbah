from typing import Any

from rest_framework import serializers

ROLES: tuple[str, ...] = ("system", "user", "assistant")


def text_of(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if not isinstance(part, dict) or part.get("type") != "text":
                raise serializers.ValidationError(
                    "Only text content is supported.", code="text_only"
                )
            parts.append(str(part.get("text", "")))
        return "".join(parts)
    if content is None:
        return ""
    raise serializers.ValidationError("`content` must be text.", code="text_only")


class CompatMessageSerializer(serializers.Serializer[dict[str, Any]]):
    role = serializers.ChoiceField(choices=list(ROLES))
    content = serializers.JSONField(required=False, allow_null=True)
    reasoning_content = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    thinking = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        message: dict[str, Any] = {"role": attrs["role"], "content": text_of(attrs.get("content"))}
        reasoning: str | None = attrs.get("reasoning_content") or attrs.get("thinking")
        if reasoning and attrs["role"] == "assistant":
            message["reasoning_content"] = reasoning
        return message


class ChatCompletionSerializer(serializers.Serializer[dict[str, Any]]):
    model = serializers.CharField()
    messages = CompatMessageSerializer(many=True, allow_empty=False)
    stream = serializers.BooleanField(required=False, default=False)
    temperature = serializers.FloatField(required=False, allow_null=True, min_value=0, max_value=2)
    top_p = serializers.FloatField(required=False, allow_null=True, min_value=0, max_value=1)
    max_tokens = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    max_completion_tokens = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    chat_template_kwargs = serializers.DictField(required=False)
    stream_options = serializers.DictField(required=False)


class OllamaOptionsSerializer(serializers.Serializer[dict[str, Any]]):
    temperature = serializers.FloatField(required=False, min_value=0, max_value=2)
    top_p = serializers.FloatField(required=False, min_value=0, max_value=1)
    num_predict = serializers.IntegerField(required=False, min_value=-2)


class OllamaChatSerializer(serializers.Serializer[dict[str, Any]]):
    model = serializers.CharField()
    messages = CompatMessageSerializer(many=True, allow_empty=False)
    stream = serializers.BooleanField(required=False, default=True)
    think = serializers.BooleanField(required=False, allow_null=True)
    options = OllamaOptionsSerializer(required=False)


class OllamaGenerateSerializer(serializers.Serializer[dict[str, Any]]):
    model = serializers.CharField()
    prompt = serializers.CharField(allow_blank=True, trim_whitespace=False)
    system = serializers.CharField(required=False, allow_blank=True, trim_whitespace=False)
    stream = serializers.BooleanField(required=False, default=True)
    think = serializers.BooleanField(required=False, allow_null=True)
    options = OllamaOptionsSerializer(required=False)


class OllamaShowSerializer(serializers.Serializer[dict[str, Any]]):
    model = serializers.CharField(required=False)
    name = serializers.CharField(required=False)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        name: str | None = attrs.get("model") or attrs.get("name")
        if not name:
            raise serializers.ValidationError("Name the model.", code="required")
        return {"model": name}
