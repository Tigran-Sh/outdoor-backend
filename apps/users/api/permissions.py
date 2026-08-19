"""Reusable DRF permission classes.

These wrap the centralized authorization service so that role checks are
never copy/pasted into individual views.
"""

from rest_framework.permissions import BasePermission

from apps.users.constants import Role
from apps.users.services import authorization


class IsParticipant(BasePermission):
    message = "Participant role required."

    def has_permission(self, request, view):
        return authorization.has_role(request.user, Role.PARTICIPANT)


class IsClubOwner(BasePermission):
    message = "Club Owner role required."

    def has_permission(self, request, view):
        return authorization.has_role(request.user, Role.CLUB_OWNER)


class IsGuide(BasePermission):
    message = "Guide role required."

    def has_permission(self, request, view):
        return authorization.has_role(request.user, Role.GUIDE)


class IsPlatformAdmin(BasePermission):
    message = "Platform Admin role required."

    def has_permission(self, request, view):
        return authorization.is_platform_admin(request.user)


class IsAdminPanelUser(BasePermission):
    """Allows Club Owner, Guide and Platform Admin; denies Participant."""

    message = "Admin Panel access required."

    def has_permission(self, request, view):
        return authorization.is_admin_panel_user(request.user)


class IsClubOwnerOrPlatformAdmin(BasePermission):
    message = "Club Owner or Platform Admin role required."

    def has_permission(self, request, view):
        return authorization.has_any_role(
            request.user, {Role.CLUB_OWNER, Role.PLATFORM_ADMIN}
        )


class HasCapability(BasePermission):
    """Checks a required capability declared on the view.

    Usage::

        class MyView(APIView):
            permission_classes = [HasCapability]
            required_capability = Capability.CREATE_EVENT

    This enforces the *role-level* capability only. Resource-scoped
    checks must be performed additionally in the relevant domain service.
    """

    message = "You do not have the required capability."

    def has_permission(self, request, view):
        capability = getattr(view, "required_capability", None)
        if capability is None:
            return False
        return authorization.has_capability(request.user, capability)
