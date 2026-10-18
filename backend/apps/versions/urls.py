from django.urls import URLPattern, URLResolver, path

from apps.versions.views import (
    ActivateVersionView,
    ChangesView,
    ExportDetailView,
    ExportDownloadView,
    ExportListView,
    VersionListView,
    VersionView,
)

app_name: str = "versions"

urlpatterns: list[URLPattern | URLResolver] = [
    path("", VersionListView.as_view(), name="tree"),
    path("<uuid:version_id>/", VersionView.as_view(), name="detail"),
    path("<uuid:version_id>/activate/", ActivateVersionView.as_view(), name="activate"),
    path("<uuid:version_id>/changes/", ChangesView.as_view(), name="changes"),
    path("<uuid:version_id>/exports/", ExportListView.as_view(), name="exports"),
    path("exports/<uuid:export_id>/", ExportDetailView.as_view(), name="export"),
    path("exports/<uuid:export_id>/download/", ExportDownloadView.as_view(), name="download"),
]
