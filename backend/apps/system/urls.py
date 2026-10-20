from django.urls import URLPattern, URLResolver, path

from apps.system.views import GpuSelectionView, HuggingFaceTokenView, SystemView

app_name: str = "system"

urlpatterns: list[URLPattern | URLResolver] = [
    path("", SystemView.as_view(), name="overview"),
    path("gpus/", GpuSelectionView.as_view(), name="gpus"),
    path("huggingface-token/", HuggingFaceTokenView.as_view(), name="huggingface-token"),
]
