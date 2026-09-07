from django.utils import timezone

from apps.clubs.tests.base import ClubAPITestCase, make_club, make_member
from apps.common.constants import ActivityType, Language, Region
from apps.events.constants import Difficulty, EventStatus
from apps.events.models import Event

EVENTS_URL = "/api/v1/events/"


def detail_url(event_id):
    return f"{EVENTS_URL}{event_id}/"


def publish_url(event_id):
    return f"{detail_url(event_id)}publish/"


def cancel_url(event_id):
    return f"{detail_url(event_id)}cancel/"


def make_event(club, **extra):
    """A draft event with everything needed to publish already set."""
    guide = extra.pop("guide", None)
    defaults = {
        "title": "Aragats North Summit",
        "description": "A long day on the north ridge, above the clouds.",
        "category": ActivityType.HIKING.value,
        "start_at": timezone.now() + timezone.timedelta(days=14),
        "region": Region.ARAGATSOTN.value,
        "difficulty": Difficulty.MEDIUM.value,
        "languages": [Language.HY.value, Language.EN.value],
        "status": EventStatus.DRAFT,
    }
    defaults.update(extra)
    event = Event.objects.create(club=club, guide=guide, **defaults)
    if "cover_image" not in extra:
        # Publishing requires a cover; set the field without a real file
        # so tests that publish do not need an upload each time.
        event.cover_image = "events/covers/test.png"
        event.save(update_fields=["cover_image"])
    return event


class EventAPITestCase(ClubAPITestCase):
    """Club test case (temp media roots) plus an events fixture."""

    def make_club_with_guide(self, owner_email, guide_email):
        club, owner = make_club(owner_email)
        guide = make_member(club, guide_email)
        return club, owner, guide
