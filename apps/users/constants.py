"""Centralized role and capability definitions.

This module is the single source of truth for the platform's role /
capability matrix. Roles are stored on the ``User`` model; capabilities
and the role -> capability mapping are defined here in Python (no dynamic
database-backed RBAC at this stage).

IMPORTANT: capability presence is a *coarse* role-level check. Some
capabilities (e.g. a Guide's ``QR_CHECK_IN``) are additionally scoped to
specific resources (assigned events). Object-level authorization lives in
the relevant domain apps once those models exist.
"""

from django.db import models


class Role(models.TextChoices):
    """Business roles on the marketplace platform."""

    PARTICIPANT = "participant", "Participant"
    CLUB_OWNER = "club_owner", "Club Owner"
    GUIDE = "guide", "Guide"
    INTERNAL_ADMIN = "internal_admin", "Internal Admin"
    PLATFORM_ADMIN = "platform_admin", "Platform Admin"


class Capability(models.TextChoices):
    """Fine-grained platform capabilities.

    Values are API-friendly, stable string keys.
    """

    EDIT_CLUB_PROFILE = "edit_club_profile", "Edit club profile"
    CREATE_EVENT = "create_event", "Create event"
    EDIT_EVENT = "edit_event", "Edit event"
    PUBLISH_EVENT = "publish_event", "Publish event"
    VIEW_PARTICIPANTS = "view_participants", "View participants"
    EXPORT_PARTICIPANTS = "export_participants", "Export participants"
    QR_CHECK_IN = "qr_check_in", "QR check-in"
    CONFIRM_COMPLETION = "confirm_completion", "Confirm completion"
    VIEW_FINANCES = "view_finances", "View finances"
    MANAGE_TEAM_MEMBERS = "manage_team_members", "Manage team members"
    CANCEL_EVENT = "cancel_event", "Cancel event"
    REQUEST_REFUND = "request_refund", "Request refund"
    VERIFY_CLUB = "verify_club", "Verify club"
    SUSPEND_CLUB = "suspend_club", "Suspend club"
    ISSUE_REFUND = "issue_refund", "Issue refund"


# All capabilities available on the platform (Platform Admin scope).
ALL_CAPABILITIES = frozenset(Capability)


# Central role -> capability mapping. Do not duplicate this elsewhere.
#
# INTERNAL_ADMIN intentionally has NO default capabilities: it is a
# "custom permissions" role whose effective capabilities are assigned
# per user (see ``effective_capabilities`` and ``User.custom_capabilities``).
ROLE_CAPABILITIES = {
    Role.PARTICIPANT: frozenset(),
    Role.CLUB_OWNER: frozenset(
        {
            Capability.EDIT_CLUB_PROFILE,
            Capability.CREATE_EVENT,
            Capability.EDIT_EVENT,
            Capability.PUBLISH_EVENT,
            Capability.VIEW_PARTICIPANTS,
            Capability.EXPORT_PARTICIPANTS,
            Capability.QR_CHECK_IN,
            Capability.CONFIRM_COMPLETION,
            Capability.VIEW_FINANCES,
            Capability.MANAGE_TEAM_MEMBERS,
            Capability.CANCEL_EVENT,
            Capability.REQUEST_REFUND,
        }
    ),
    Role.GUIDE: frozenset(
        {
            Capability.VIEW_PARTICIPANTS,
            Capability.EXPORT_PARTICIPANTS,
            Capability.QR_CHECK_IN,
            Capability.CONFIRM_COMPLETION,
        }
    ),
    Role.INTERNAL_ADMIN: frozenset(),
    Role.PLATFORM_ADMIN: ALL_CAPABILITIES,
}


# Roles whose capabilities are assigned per user rather than fixed by role.
CUSTOM_CAPABILITY_ROLES = frozenset({Role.INTERNAL_ADMIN})


# Roles that may access the Admin Panel (i.e. not participants).
ADMIN_PANEL_ROLES = frozenset(
    {
        Role.CLUB_OWNER,
        Role.GUIDE,
        Role.INTERNAL_ADMIN,
        Role.PLATFORM_ADMIN,
    }
)


def effective_capabilities(role, custom_capabilities=None):
    """Return the effective capability value set for a user.

    Combines the role's default capabilities with any per-user assigned
    capabilities (used by INTERNAL_ADMIN). Always returns a frozenset of
    capability *string values*.
    """
    base = {c.value for c in ROLE_CAPABILITIES.get(role, frozenset())}
    if custom_capabilities:
        valid = set(Capability.values)
        base |= {c for c in custom_capabilities if c in valid}
    return frozenset(base)
