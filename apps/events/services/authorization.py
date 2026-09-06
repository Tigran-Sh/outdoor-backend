"""Club-scoped authorization for events.

Same shape as ``apps.clubs.services.authorization``: a capability alone
is never enough, because capabilities are stored platform-wide on the
account. Each check also requires the user to own or belong to the club
the event belongs to, which confines an internal admin's grants to the
club that granted them.

Reading is deliberately looser than writing: everyone on a club's team
needs to see its events (a guide has to know what they are guiding),
while creating, editing, publishing and cancelling each need their own
capability.
"""

from apps.clubs.services import authorization as clubs
from apps.users.constants import Capability
from apps.users.services import authorization as platform

# Scope sentinel: the reader is not restricted to a single club.
ALL_CLUBS = clubs.ALL_CLUBS


# Holding any of these means the user helps run the club's programme and
# therefore sees all of its events. Someone with none of them (a plain
# guide) only ever sees the events assigned to them.
EVENT_CAPABILITIES = (
    Capability.CREATE_EVENT,
    Capability.EDIT_EVENT,
    Capability.PUBLISH_EVENT,
    Capability.CANCEL_EVENT,
)


def club_for_user(user):
    """The club a user acts within: the one they own, or belong to."""
    owned = clubs.get_owned_club(user)
    if owned is not None:
        return owned
    return clubs.get_membership_club(user)


def active_membership(user):
    """The user's active team membership, or None."""
    membership = clubs.get_membership(user)
    if membership is None or not membership.is_active:
        return None
    return membership


def manages_events(user):
    """Return True if the user sees the club's whole programme."""
    if platform.is_platform_admin(user):
        return True
    if clubs.get_owned_club(user) is not None:
        return True
    return any(
        platform.has_capability(user, capability)
        for capability in EVENT_CAPABILITIES
    )


def readable_club_scope(user):
    """``ALL_CLUBS``, a single club, or None when there is no access."""
    if platform.is_platform_admin(user):
        return ALL_CLUBS
    return club_for_user(user)


def can_read_any_event(user):
    return readable_club_scope(user) is not None


def visible_events(user, queryset):
    """Narrow ``queryset`` to the events ``user`` may see.

    A club owner, a Platform Admin and anyone holding an event
    capability see the club's whole programme. A plain guide sees only
    the events they are assigned to guide — they have no business
    reading the rest of the club's calendar.
    """
    scope = readable_club_scope(user)
    if scope is None:
        return queryset.none()
    if scope is not ALL_CLUBS:
        queryset = queryset.filter(club=scope)
    if manages_events(user):
        return queryset
    membership = active_membership(user)
    if membership is None:
        return queryset.none()
    return queryset.filter(guide=membership)


def can_view_event(user, event):
    """Object-level counterpart of ``visible_events``."""
    scope = readable_club_scope(user)
    if scope is None:
        return False
    if scope is not ALL_CLUBS and scope.pk != event.club_id:
        return False
    if manages_events(user):
        return True
    membership = active_membership(user)
    return membership is not None and event.guide_id == membership.pk


def _can(user, club, capability):
    if platform.is_platform_admin(user):
        return True
    if club is None:
        return False
    acting_club = club_for_user(user)
    return (
        acting_club is not None
        and acting_club.pk == club.pk
        and platform.has_capability(user, capability)
    )


def can_create_event(user, club):
    return _can(user, club, Capability.CREATE_EVENT)


def can_edit_event(user, event):
    return _can(user, event.club, Capability.EDIT_EVENT)


def can_publish_event(user, event):
    return _can(user, event.club, Capability.PUBLISH_EVENT)


def can_cancel_event(user, event):
    return _can(user, event.club, Capability.CANCEL_EVENT)


def can_write_events(user):
    """Coarse gate for the write endpoints, before an object exists."""
    if platform.is_platform_admin(user):
        return True
    if club_for_user(user) is None:
        return False
    return any(
        platform.has_capability(user, capability)
        for capability in (
            Capability.CREATE_EVENT,
            Capability.EDIT_EVENT,
            Capability.PUBLISH_EVENT,
            Capability.CANCEL_EVENT,
        )
    )
