from django.apps import AppConfig


class ServingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.serving"
    label = "serving"
    verbose_name = "Serving"
