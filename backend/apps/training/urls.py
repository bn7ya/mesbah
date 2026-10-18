from django.urls import URLPattern, URLResolver, path

from apps.training.views import (
    CancelRunView,
    ExampleListView,
    MetricListView,
    PlanView,
    RunDetailView,
    RunListView,
)

app_name: str = "training"

urlpatterns: list[URLPattern | URLResolver] = [
    path("", RunListView.as_view(), name="runs"),
    path("plan/", PlanView.as_view(), name="plan"),
    path("examples/", ExampleListView.as_view(), name="examples"),
    path("<uuid:run_id>/", RunDetailView.as_view(), name="run"),
    path("<uuid:run_id>/cancel/", CancelRunView.as_view(), name="cancel"),
    path("<uuid:run_id>/metrics/", MetricListView.as_view(), name="metrics"),
]
