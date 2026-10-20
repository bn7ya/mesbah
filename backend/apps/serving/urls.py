from django.urls import URLPattern, URLResolver, path

from apps.serving.views import (
    ApiKeyDetailView,
    ApiKeyListView,
    EngineDetailView,
    EngineListView,
    UnloadEngineView,
)

app_name: str = "serving"

urlpatterns: list[URLPattern | URLResolver] = [
    path("engines/", EngineListView.as_view(), name="engines"),
    path("engines/<uuid:engine_id>/", EngineDetailView.as_view(), name="engine"),
    path("engines/<uuid:engine_id>/unload/", UnloadEngineView.as_view(), name="unload"),
    path("keys/", ApiKeyListView.as_view(), name="keys"),
    path("keys/<uuid:key_id>/", ApiKeyDetailView.as_view(), name="key"),
]
