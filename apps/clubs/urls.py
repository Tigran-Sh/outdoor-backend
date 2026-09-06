from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.clubs.api.views import (
    AdminClubViewSet,
    ClubIdDocumentView,
    MyClubView,
    TeamMemberViewSet,
)

club_router = DefaultRouter()
club_router.register(
    "team-members", TeamMemberViewSet, basename="team-member"
)

admin_router = DefaultRouter()
admin_router.register("clubs", AdminClubViewSet, basename="admin-club")

club_patterns = [
    path("", MyClubView.as_view(), name="my-club"),
    path(
        "<uuid:pk>/id-document/",
        ClubIdDocumentView.as_view(),
        name="club-id-document",
    ),
    path("", include(club_router.urls)),
]

urlpatterns = [
    path("club/", include(club_patterns)),
    path("admin/", include(admin_router.urls)),
]
