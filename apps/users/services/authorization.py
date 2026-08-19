"""Centralized authorization helpers.

These functions implement the *role* and *capability* layers of the
authorization pipeline:

    Authentication -> Role -> Capability -> Resource Scope -> ALLOW/DENY

The first three layers are handled here (and by the DRF permission
classes). The final *resource scope* layer is domain-specific and will
be implemented close to its domain (e.g. ``apps.events``) once Club and
Event models exist. Placeholder extension points are documented at the
bottom of this module.

Keeping this logic here (rather than inside views) ensures the role
matrix is defined in exactly one place.
"""

from apps.users.constants import ADMIN_PANEL_ROLES, Role


def _is_authenticated(user):
    return bool(user and user.is_authenticated and user.is_active)


def has_role(user, role):
    """Return True if ``user`` is authenticated and has the given role."""
    return _is_authenticated(user) and user.role == role


def has_any_role(user, roles):
    """Return True if ``user`` has any of the given roles."""
    return _is_authenticated(user) and user.role in set(roles)


def get_capabilities(user):
    """Return the set of effective capabilities for ``user``.

    Combines role defaults with any per-user assigned capabilities.
    """
    if not _is_authenticated(user):
        return frozenset()
    return user.capabilities


def has_capability(user, capability):
    """Return True if the user's effective capabilities grant it.

    NOTE: This is the coarse (role + assigned) check only. Resource-scoped
    capabilities (e.g. a Guide checking in participants for an *assigned*
    event) must additionally pass a domain-level object check.
    """
    return capability in get_capabilities(user)


def grantable_capabilities(user):
    """Capabilities ``user`` is allowed to assign to another account.

    A grantor may only delegate capabilities they themselves hold, which
    prevents privilege escalation (e.g. a Club Owner can never grant
    platform-governance capabilities they do not possess).
    """
    return get_capabilities(user)


def can_grant_capabilities(user, capabilities):
    """Return the requested capabilities the user is NOT allowed to grant."""
    grantable = grantable_capabilities(user)
    return [c for c in capabilities if c not in grantable]


def is_admin_panel_user(user):
    """Return True if the user may access Admin Panel APIs.

    Allows CLUB_OWNER, GUIDE and PLATFORM_ADMIN; denies PARTICIPANT.
    """
    return has_any_role(user, ADMIN_PANEL_ROLES)


def is_platform_admin(user):
    """Return True if the user is a platform-wide administrator."""
    return has_role(user, Role.PLATFORM_ADMIN)


# Resource-scope extension points (implemented later, in domain apps).
#
# The functions below intentionally do not exist yet. They document the
# intended object-level authorization surface so future domain code can
# implement them close to their models, for example::
#
#     # apps/clubs/services/authorization.py
#     def can_access_club(user, club): ...
#     def can_manage_event(user, event): ...
#
#     # apps/events/services/authorization.py
#     def can_view_event_participants(user, event): ...
#     def can_check_in_participant(user, event): ...
#     def can_confirm_event_completion(user, event): ...
#
# A typical implementation combines this module's capability check with a
# domain ownership / assignment check, and always allows PLATFORM_ADMIN
# platform-wide. For example::
#
#     def can_check_in_participant(user, event):
#         if is_platform_admin(user):
#             return True
#         if not has_capability(user, Capability.QR_CHECK_IN):
#             return False
#         return event.is_assigned_to(user) or event.club.is_managed_by(user)
#
# ``Capability`` (see apps.users.constants) enumerates the values these
# extension points will check.
