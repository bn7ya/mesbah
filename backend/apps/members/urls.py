from django.urls import URLPattern, URLResolver, path

from apps.members.views import MemberDetailView, MemberListView

app_name: str = "members"

urlpatterns: list[URLPattern | URLResolver] = [
    path("", MemberListView.as_view(), name="list"),
    path("<int:member_id>/", MemberDetailView.as_view(), name="detail"),
]
