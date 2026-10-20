import os

from django.conf import settings
from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler
from django.core.asgi import get_asgi_application
from django.core.handlers.asgi import ASGIHandler

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")

django_application: ASGIHandler = get_asgi_application()

# runserver serves static files in development; under uvicorn this handler does.
application: ASGIHandler | ASGIStaticFilesHandler = (
    ASGIStaticFilesHandler(django_application) if settings.DEBUG else django_application
)
