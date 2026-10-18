from django.urls import URLPattern, URLResolver, path

from apps.serving.views import (
    ChatCompletionView,
    ModelListView,
    OllamaChatView,
    OllamaGenerateView,
    OllamaShowView,
    OllamaTagsView,
    OllamaVersionView,
)

# Clients append these paths to a base URL themselves, so they carry no trailing slash.
openai_patterns: list[URLPattern | URLResolver] = [
    path("models", ModelListView.as_view(), name="openai-models"),
    path("chat/completions", ChatCompletionView.as_view(), name="openai-chat"),
]

ollama_patterns: list[URLPattern | URLResolver] = [
    path("api/chat", OllamaChatView.as_view(), name="ollama-chat"),
    path("api/generate", OllamaGenerateView.as_view(), name="ollama-generate"),
    path("api/tags", OllamaTagsView.as_view(), name="ollama-tags"),
    path("api/show", OllamaShowView.as_view(), name="ollama-show"),
    path("api/version", OllamaVersionView.as_view(), name="ollama-version"),
]
