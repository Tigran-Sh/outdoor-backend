"""DRF permission classes for club-scoped endpoints."""

from rest_framework.permissions import SAFE_METHODS, BasePermission

from apps.clubs.services import authorization


class CanAccessTeamMembers(BasePermission):
    """Reads for club readers, writes for the owning Club Owner only.

    Object-level checks pin every action to the team member's own club,
    so a Club Owner can never touch another club's staff.
    """

    message = "You do not have access to these team members."

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return authorization.can_read_any_team(request.user)
        # Platform admins short-circuit inside can_manage_team, so passing
        # the (possibly None) owned club covers both cases.
        owned = authorization.get_owned_club(request.user)
        return authorization.can_manage_team(request.user, owned)

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return authorization.can_view_team(request.user, obj.club)
        return authorization.can_manage_team(request.user, obj.club)
