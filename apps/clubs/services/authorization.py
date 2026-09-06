"""Club-scoped (object-level) authorization.

This is the "Resource Scope" layer described in
``apps.users.services.authorization``: it combines a coarse capability
check with a club ownership / membership check.

Why it matters: a capability granted to a user (e.g. an internal admin
created by a Club Owner) is stored platform-wide on the account, so on
its own it would apply everywhere. Every function here additionally
requires the user to own or belong to the club being acted upon, which
confines those grants to a single club.
"""

from apps.users.constants import Capability, Role
from apps.users.services import authorization as platform

# Scope sentinel: the reader is not restricted to a single club. Only
# platform staff ever reach it, never a Club Owner.
ALL_CLUBS = object()


def get_owned_club(user):
    """Return the club owned by ``user``, or None."""
    if not (user and user.is_authenticated and user.is_active):
        return None
    return getattr(user, "club", None)


def get_membership(user):
    """Return the user's team membership row, active or not."""
    if not (user and user.is_authenticated and user.is_active):
        return None
    return getattr(user, "team_membership", None)


def get_membership_club(user):
    """Return the club ``user`` is an *active* team member of, or None."""
    membership = get_membership(user)
    if membership is None or not membership.is_active:
        return None
    return membership.club


def _is_platform_level_reader(user):
    """Return True for platform staff who may read every club's team.

    Only an internal admin explicitly granted ``view_team_members`` and
    never attached to a club qualifies. A Club Owner is always confined
    to their own club, even though the capability is a role default.

    This deliberately tests for the *existence* of a membership rather
    than an active one: an internal admin created by a Club Owner stays
    bound to that club, so deactivating them can never promote them to a
    platform-wide reader.
    """
    if not platform.has_role(user, Role.INTERNAL_ADMIN):
        return False
    if not platform.has_capability(user, Capability.VIEW_TEAM_MEMBERS):
        return False
    return get_membership(user) is None


def can_manage_team(user, club):
    """Return True if ``user`` may create/update team members of ``club``."""
    if platform.is_platform_admin(user):
        return True
    if club is None:
        return False
    owned = get_owned_club(user)
    return (
        owned is not None
        and owned.pk == club.pk
        and platform.has_capability(user, Capability.MANAGE_TEAM_MEMBERS)
    )


def can_edit_club(user, club):
    """Return True if ``user`` may edit ``club``'s own profile."""
    if platform.is_platform_admin(user):
        return True
    if club is None:
        return False
    owned = get_owned_club(user)
    return (
        owned is not None
        and owned.pk == club.pk
        and platform.has_capability(user, Capability.EDIT_CLUB_PROFILE)
    )


def can_read_club_documents(user, club):
    """Return True if ``user`` may read ``club``'s identity document.

    Restricted to the owner and to staff who verify clubs. Note that
    ``VERIFY_CLUB`` is not a Club Owner capability, so an owner can
    never grant it to an internal admin they create and thereby read
    another club's documents.
    """
    if platform.is_platform_admin(user):
        return True
    if club is None:
        return False
    owned = get_owned_club(user)
    if owned is not None and owned.pk == club.pk:
        return True
    return platform.has_capability(user, Capability.VERIFY_CLUB)


def can_view_team(user, club):
    """Return True if ``user`` may read team members of ``club``."""
    if can_manage_team(user, club):
        return True
    if club is None:
        return False
    if _is_platform_level_reader(user):
        return True
    if not platform.has_capability(user, Capability.VIEW_TEAM_MEMBERS):
        return False
    membership_club = get_membership_club(user)
    return membership_club is not None and membership_club.pk == club.pk


def readable_club_scope(user):
    """Return the clubs a reader may see.

    ``ALL_CLUBS`` for platform staff, a single ``Club`` for anyone tied
    to one, or ``None`` when the user has no read access at all.
    """
    if platform.is_platform_admin(user):
        return ALL_CLUBS
    if not platform.has_capability(user, Capability.VIEW_TEAM_MEMBERS):
        return None
    owned = get_owned_club(user)
    if owned is not None:
        return owned
    membership = get_membership_club(user)
    if membership is not None:
        return membership
    if _is_platform_level_reader(user):
        return ALL_CLUBS
    # Holding the capability without owning or belonging to a club (e.g.
    # a club_owner account with no club yet) grants nothing.
    return None


def can_read_any_team(user):
    """Return True if ``user`` may reach the team-member read endpoints."""
    return readable_club_scope(user) is not None
