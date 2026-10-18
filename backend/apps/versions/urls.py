from django.urls import URLPattern, URLResolver, path

from apps.versions.views import ActivateVersionView, VersionListView, VersionView

app_name: str = "versions"

urlpatterns: list[URLPattern | URLResolver] = [
    path("", VersionListView.as_view(), name="tree"),
    path("<uuid:version_id>/", VersionView.as_view(), name="detail"),
    path("<uuid:version_id>/activate/", ActivateVersionView.as_view(), name="activate"),
]
