from .engines import EngineDetailView, EngineListView, UnloadEngineView
from .keys import ApiKeyDetailView, ApiKeyListView
from .ollama import (
    OllamaChatView,
    OllamaGenerateView,
    OllamaShowView,
    OllamaTagsView,
    OllamaVersionView,
)
from .openai import ChatCompletionView, ModelListView

__all__: list[str] = [
    "ApiKeyDetailView",
    "ApiKeyListView",
    "ChatCompletionView",
    "EngineDetailView",
    "EngineListView",
    "ModelListView",
    "OllamaChatView",
    "OllamaGenerateView",
    "OllamaShowView",
    "OllamaTagsView",
    "OllamaVersionView",
    "UnloadEngineView",
]
