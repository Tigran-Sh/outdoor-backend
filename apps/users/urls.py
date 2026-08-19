from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.users.api.views import (
    AdminUserViewSet,
    CapabilityListView,
    ChangePasswordView,
    LoginView,
    LogoutView,
    MeView,
    RefreshView,
    RoleCapabilitiesView,
    RoleDetailView,
    RoleListView,
)

auth_patterns = [
    path("login/", LoginView.as_view(), name="auth-login"),
    path("refresh/", RefreshView.as_view(), name="auth-refresh"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    path("me/", MeView.as_view(), name="auth-me"),
    path(
        "change-password/",
        ChangePasswordView.as_view(),
        name="auth-change-password",
    ),
]

router = DefaultRouter()
router.register("users", AdminUserViewSet, basename="admin-user")

admin_patterns = [
    path("", include(router.urls)),
    path("roles/", RoleListView.as_view(), name="admin-role-list"),
    path(
        "roles/<str:role>/",
        RoleDetailView.as_view(),
        name="admin-role-detail",
    ),
    path(
        "roles/<str:role>/capabilities/",
        RoleCapabilitiesView.as_view(),
        name="admin-role-capabilities",
    ),
    path(
        "capabilities/",
        CapabilityListView.as_view(),
        name="admin-capability-list",
    ),
]

urlpatterns = [
    path("auth/", include(auth_patterns)),
    path("admin/", include(admin_patterns)),
]
