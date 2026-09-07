"""Event enumerations.

Activities, languages and regions are shared with clubs and live in
``apps.common.constants``; only event-specific taxonomies belong here.

NOTE: the frontend's `EVENTS_API_SPEC.md` was never supplied, so the
values below are derived from the event-creation wireframe. Reconcile
them with that spec before the frontend integrates.
"""

from django.db import models


class EventStatus(models.TextChoices):
    """Lifecycle. Server-managed; never writable through a serializer."""

    DRAFT = "draft", "Draft"
    PUBLISHED = "published", "Published"
    CANCELLED = "cancelled", "Cancelled"
    COMPLETED = "completed", "Completed"


class DurationType(models.TextChoices):
    SINGLE = "single", "Single day"
    MULTI = "multi", "Multi-day"


class Difficulty(models.TextChoices):
    EASY = "easy", "Easy"
    MEDIUM = "medium", "Medium"
    HARD = "hard", "Hard"
    EXTREME = "extreme", "Extreme"


class PriceType(models.TextChoices):
    FREE = "free", "Free"
    PAID = "paid", "Paid"


class CancellationReason(models.TextChoices):
    WEATHER = "weather", "Weather conditions"
    NOT_ENOUGH_PARTICIPANTS = (
        "not_enough_participants",
        "Not enough participants",
    )
    GUIDE_UNAVAILABLE = "guide_unavailable", "Guide unavailable"
    SAFETY = "safety", "Safety concerns"
    OTHER = "other", "Other"


# Fields that must be filled in before an event may be published. A
# draft deliberately allows almost anything to be missing.
REQUIRED_TO_PUBLISH = (
    "title",
    "description",
    "category",
    "cover_image",
    "start_at",
    "region",
    "difficulty",
    "guide",
    "languages",
)
