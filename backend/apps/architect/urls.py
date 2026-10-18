from django.urls import URLPattern, URLResolver, path

from apps.architect.views import (
    DraftDetailView,
    DraftListView,
    EstimateView,
    PresetView,
    TrainDesignView,
)

app_name: str = "architect"

urlpatterns: list[URLPattern | URLResolver] = [
    path("presets/", PresetView.as_view(), name="presets"),
    path("estimate/", EstimateView.as_view(), name="estimate"),
    path("drafts/", DraftListView.as_view(), name="drafts"),
    path("drafts/<uuid:draft_id>/", DraftDetailView.as_view(), name="draft"),
    path("drafts/<uuid:draft_id>/train/", TrainDesignView.as_view(), name="train"),
]
