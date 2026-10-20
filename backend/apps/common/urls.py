from django.urls import URLPattern, URLResolver, path

from apps.common.views import HealthView

app_name: str = "common"

urlpatterns: list[URLPattern | URLResolver] = [
    path("", HealthView.as_view(), name="health"),
]
