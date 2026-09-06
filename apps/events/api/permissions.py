from rest_framework.permissions import SAFE_METHODS, BasePermission

from apps.events.services import authorization


class CanAccessEvents(BasePermission):
    """Reads by club membership, writes by per-action capability.

    Each write maps to its own capability, so someone granted only
    ``cancel_event`` can cancel without also being able to edit.
    """

    message = "You do not have access to these events."

    ACTION_CHECKS = {
        "partial_update": (
            authorization.can_edit_event,
            "You cannot edit this event.",
        ),
        "destroy": (
            authorization.can_edit_event,
            "You cannot delete this event.",
        ),
        "publish": (
            authorization.can_publish_event,
            "You cannot publish this event.",
        ),
        "cancel": (
            authorization.can_cancel_event,
            "You cannot cancel this event.",
        ),
    }

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return authorization.can_read_any_event(request.user)
        return authorization.can_write_events(request.user)

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return authorization.can_view_event(request.user, obj)

        check, message = self.ACTION_CHECKS.get(
            view.action,
            (authorization.can_edit_event, self.message),
        )
        if not check(request.user, obj):
            self.message = message
            return False
        return True
