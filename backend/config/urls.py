from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import URLPattern, URLResolver, include, path, re_path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from config import spa

api_patterns: list[URLPattern | URLResolver] = [
    path("health/", include("apps.common.urls")),
    path("auth/", include("apps.accounts.urls")),
    path("members/", include("apps.members.urls")),
    path("system/", include("apps.system.urls")),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "schema/swagger-ui/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path("schema/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]

urlpatterns: list[URLPattern | URLResolver] = [
    path("admin/", admin.site.urls),
    path("api/", include(api_patterns)),
]

if settings.MESBAH_SPA_DIR is not None:
    # Without nginx in front, Django serves the Angular app: any path that is not the API,
    # the admin or a file gets index.html, and the Angular router takes it from there.
    urlpatterns += [re_path(r"^(?!api/|admin/|static/|media/).*$", spa.index, name="spa")]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += [path("__debug__/", include("debug_toolbar.urls"))]
