from django.urls import URLPattern, URLResolver, path

from apps.projects.views import ProjectDetailView, ProjectListView

app_name: str = "projects"

urlpatterns: list[URLPattern | URLResolver] = [
    path("", ProjectListView.as_view(), name="list"),
    path("<uuid:project_id>/", ProjectDetailView.as_view(), name="detail"),
]
