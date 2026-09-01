from django.urls import path

from apps.common.views import HealthView

app_name = "common"

urlpatterns = [
    path("", HealthView.as_view(), name="health"),
]
