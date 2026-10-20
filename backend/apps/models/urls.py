from django.urls import URLPattern, URLResolver, path

from apps.models.views import (
    CancelDownloadView,
    HubInspectView,
    HubSearchView,
    LibraryModelView,
    LibraryView,
    RetryDownloadView,
)

app_name: str = "models"

urlpatterns: list[URLPattern | URLResolver] = [
    path("", LibraryView.as_view(), name="library"),
    path("hub/", HubSearchView.as_view(), name="hub-search"),
    path("hub/inspect/", HubInspectView.as_view(), name="hub-inspect"),
    path("<uuid:model_id>/", LibraryModelView.as_view(), name="detail"),
    path("<uuid:model_id>/cancel/", CancelDownloadView.as_view(), name="cancel"),
    path("<uuid:model_id>/retry/", RetryDownloadView.as_view(), name="retry"),
]
