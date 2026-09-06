from django.contrib.postgres.fields import ArrayField
from django.db import models

from apps.common.constants import ActivityType, Language, Region
from apps.common.models import UUIDTimeStampedModel
from apps.common.validators import validate_image_upload
from apps.events.constants import (
    REQUIRED_TO_PUBLISH,
    CancellationReason,
    Difficulty,
    DurationType,
    EventStatus,
    PriceType,
)


class Event(UUIDTimeStampedModel):
    """An outdoor experience run by a club.

    Every event belongs to exactly one club, which is what scopes who
    may see and manage it (see ``apps.events.services.authorization``).
    Events are built up as drafts, so nearly everything is optional at
    the model level and completeness is enforced when publishing.
    """

    club = models.ForeignKey(
        "clubs.Club",
        on_delete=models.CASCADE,
        related_name="events",
    )
    status = models.CharField(
        max_length=32,
        choices=EventStatus.choices,
        default=EventStatus.DRAFT,
    )

    # Block 1 — general
    title = models.CharField(max_length=255)
    category = models.CharField(
        max_length=32,
        choices=ActivityType.choices,
        blank=True,
    )
    cover_image = models.ImageField(
        upload_to="events/covers/",
        null=True,
        blank=True,
        validators=[validate_image_upload],
    )
    start_at = models.DateTimeField(null=True, blank=True)
    duration_type = models.CharField(
        max_length=16,
        choices=DurationType.choices,
        default=DurationType.SINGLE,
    )
    end_at = models.DateTimeField(null=True, blank=True)
    languages = ArrayField(
        base_field=models.CharField(
            max_length=8, choices=Language.choices
        ),
        default=list,
        blank=True,
    )

    # Block 2 — route and difficulty
    region = models.CharField(
        max_length=32,
        choices=Region.choices,
        blank=True,
    )
    difficulty = models.CharField(
        max_length=16,
        choices=Difficulty.choices,
        blank=True,
    )
    distance_km = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )
    elevation_gain_m = models.PositiveIntegerField(null=True, blank=True)
    # Coordinates rather than only the pasted maps link: a link cannot be
    # measured against, and GPS tracking will need real numbers.
    meeting_point_lat = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    meeting_point_lng = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    meeting_point_url = models.URLField(blank=True)
    meeting_point_note = models.CharField(max_length=255, blank=True)

    # Block 3 — team and equipment
    guide = models.ForeignKey(
        "clubs.TeamMember",
        on_delete=models.PROTECT,
        related_name="guided_events",
        null=True,
        blank=True,
    )
    required_items = ArrayField(
        base_field=models.CharField(max_length=255),
        default=list,
        blank=True,
    )

    # Block 4 — sales and terms
    price_type = models.CharField(
        max_length=16,
        choices=PriceType.choices,
        default=PriceType.FREE,
    )
    # AMD. Null while the event is free.
    price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    max_participants = models.PositiveIntegerField(null=True, blank=True)
    # Server-managed. Stays 0 until bookings exist.
    sold_count = models.PositiveIntegerField(default=0)
    included = models.TextField(blank=True)
    not_included = models.TextField(blank=True)
    cancellation_terms = models.TextField(blank=True)
    other_info = models.TextField(blank=True)

    # Set by the cancel action only.
    cancellation_reason = models.CharField(
        max_length=32,
        choices=CancellationReason.choices,
        blank=True,
    )
    cancellation_reason_other = models.TextField(blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-start_at", "-created_at"]

    def __str__(self):
        return self.title

    @property
    def is_sold_out(self):
        if self.max_participants is None:
            return False
        return self.sold_count >= self.max_participants

    def missing_to_publish(self):
        """Required fields still empty, plus conditional gaps."""
        missing = [
            field
            for field in REQUIRED_TO_PUBLISH
            if not getattr(self, field)
        ]
        if self.duration_type == DurationType.MULTI and not self.end_at:
            missing.append("end_at")
        if self.price_type == PriceType.PAID and self.price is None:
            missing.append("price")
        return missing


class EventGalleryImage(UUIDTimeStampedModel):
    """An extra image shown alongside the cover."""

    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="gallery_images",
    )
    image = models.ImageField(
        upload_to="events/gallery/",
        validators=[validate_image_upload],
    )
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "created_at"]

    def __str__(self):
        return f"{self.event.title} #{self.order}"
