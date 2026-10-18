from django.urls import URLPattern, URLResolver, path

from apps.datasets.views import (
    CancelImportView,
    DatasetView,
    HubInspectView,
    HubSearchView,
    LibraryView,
    RetryImportView,
    RowsView,
    UploadView,
)

app_name: str = "datasets"

urlpatterns: list[URLPattern | URLResolver] = [
    path("", LibraryView.as_view(), name="library"),
    path("hub/", HubSearchView.as_view(), name="hub-search"),
    path("hub/inspect/", HubInspectView.as_view(), name="hub-inspect"),
    path("upload/", UploadView.as_view(), name="upload"),
    path("<uuid:dataset_id>/", DatasetView.as_view(), name="detail"),
    path("<uuid:dataset_id>/rows/", RowsView.as_view(), name="rows"),
    path("<uuid:dataset_id>/cancel/", CancelImportView.as_view(), name="cancel"),
    path("<uuid:dataset_id>/retry/", RetryImportView.as_view(), name="retry"),
]
