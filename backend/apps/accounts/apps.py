from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"
    # Not "auth" — django.contrib.auth already owns that label.
    label = "accounts"
    verbose_name = "Accounts"
