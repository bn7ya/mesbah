from django.urls import URLPattern, URLResolver, path

from apps.accounts.views import CsrfView, MeView, SignInView, SignOutView

app_name: str = "accounts"

urlpatterns: list[URLPattern | URLResolver] = [
    path("csrf/", CsrfView.as_view(), name="csrf"),
    path("login/", SignInView.as_view(), name="login"),
    path("logout/", SignOutView.as_view(), name="logout"),
    path("me/", MeView.as_view(), name="me"),
]
