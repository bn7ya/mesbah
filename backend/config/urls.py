"""Root URL configuration (Django side).

Every API path lives under `/api/`. One app per Angular feature (see the
root migration plan), mounted at its own prefix as it's ported off FastAPI.
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

api_patterns = [
    path("health/", include("apps.common.urls")),
    path("auth/", include("apps.accounts.urls")),
    # New slices are mounted here, one line each, as they're ported off
    # backend/app/features/* — e.g.:
    # path("projects/", include("apps.projects.urls")),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "schema/swagger-ui/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path("schema/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(api_patterns)),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += [path("__debug__/", include("debug_toolbar.urls"))]
