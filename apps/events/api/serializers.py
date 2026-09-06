from django.utils import timezone
from rest_framework import serializers

from apps.clubs.models import TeamMember
from apps.common.constants import ActivityType, Language
from apps.events.constants import (
    CancellationReason,
    DurationType,
    PriceType,
)
from apps.events.models import Event, EventGalleryImage


class EventGalleryImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventGalleryImage
        fields = ("id", "image", "order")
        read_only_fields = ("id",)


class EventSerializer(serializers.ModelSerializer):
    """Read representation of an event."""

    club_name = serializers.CharField(source="club.name", read_only=True)
    guide_name = serializers.CharField(
        source="guide.user.full_name", read_only=True, default=None
    )
    gallery_images = EventGalleryImageSerializer(many=True, read_only=True)
    is_sold_out = serializers.BooleanField(read_only=True)
    missing_to_publish = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = (
            "id",
            "club",
            "club_name",
            "status",
            "title",
            "category",
            "cover_image",
            "gallery_images",
            "start_at",
            "duration_type",
            "end_at",
            "languages",
            "region",
            "difficulty",
            "distance_km",
            "elevation_gain_m",
            "meeting_point_lat",
            "meeting_point_lng",
            "meeting_point_url",
            "meeting_point_note",
            "guide",
            "guide_name",
            "required_items",
            "price_type",
            "price",
            "max_participants",
            "sold_count",
            "is_sold_out",
            "included",
            "not_included",
            "cancellation_terms",
            "other_info",
            "cancellation_reason",
            "cancellation_reason_other",
            "cancelled_at",
            "missing_to_publish",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_missing_to_publish(self, obj):
        return obj.missing_to_publish()


class EventWriteSerializer(serializers.ModelSerializer):
    """Create / update an event.

    ``status`` and ``sold_count`` are absent by design: an event is
    published through its own endpoint and cancelled through another,
    so neither can be set by editing a field.
    """

    category = serializers.ChoiceField(
        choices=ActivityType.choices, required=False
    )
    languages = serializers.ListField(
        child=serializers.ChoiceField(choices=Language.choices),
        required=False,
    )
    required_items = serializers.ListField(
        child=serializers.CharField(max_length=255),
        required=False,
    )
    gallery_images = serializers.ListField(
        child=serializers.ImageField(), required=False, write_only=True
    )

    class Meta:
        model = Event
        fields = (
            "title",
            "category",
            "cover_image",
            "gallery_images",
            "start_at",
            "duration_type",
            "end_at",
            "languages",
            "region",
            "difficulty",
            "distance_km",
            "elevation_gain_m",
            "meeting_point_lat",
            "meeting_point_lng",
            "meeting_point_url",
            "meeting_point_note",
            "guide",
            "required_items",
            "price_type",
            "price",
            "max_participants",
            "included",
            "not_included",
            "cancellation_terms",
            "other_info",
        )

    def _club(self):
        """The club this event belongs to (or will)."""
        if self.instance is not None:
            return self.instance.club
        return self.context.get("club")

    def validate_languages(self, value):
        if not value:
            raise serializers.ValidationError(
                "Choose at least one language."
            )
        if len(set(value)) != len(value):
            raise serializers.ValidationError("Duplicate languages.")
        return value

    def validate_guide(self, value):
        """A guide must be active staff of the club running the event."""
        if value is None:
            return value
        club = self._club()
        if club is not None and value.club_id != club.pk:
            raise serializers.ValidationError(
                "That person is not a member of this club's team."
            )
        if not value.is_active:
            raise serializers.ValidationError(
                "That team member is no longer active."
            )
        return value

    def validate_price(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("Price cannot be negative.")
        return value

    def _resulting(self, attrs, field):
        """The value ``field`` holds once ``attrs`` is applied.

        Events are drafted over several partial saves, so the rules
        below judge the end state rather than one payload.
        """
        if field in attrs:
            return attrs[field]
        if self.instance is not None:
            return getattr(self.instance, field)
        return None

    def validate(self, attrs):
        duration_type = self._resulting(attrs, "duration_type")
        start_at = self._resulting(attrs, "start_at")
        end_at = self._resulting(attrs, "end_at")

        if duration_type == DurationType.MULTI:
            if not end_at:
                raise serializers.ValidationError(
                    {"end_at": "Required for a multi-day event."}
                )
        elif "end_at" in attrs and end_at:
            raise serializers.ValidationError(
                {"end_at": "Only multi-day events have an end date."}
            )

        if start_at and end_at and end_at <= start_at:
            raise serializers.ValidationError(
                {"end_at": "Must be after the start."}
            )

        price_type = self._resulting(attrs, "price_type")
        price = self._resulting(attrs, "price")
        if price_type == PriceType.PAID:
            if price is None:
                raise serializers.ValidationError(
                    {"price": "Required for a paid event."}
                )
        elif price is not None:
            raise serializers.ValidationError(
                {"price": "A free event cannot have a price."}
            )

        return attrs

    def create(self, validated_data):
        gallery = validated_data.pop("gallery_images", [])
        validated_data["club"] = self.context["club"]
        event = super().create(validated_data)
        self._save_gallery(event, gallery)
        return event

    def update(self, instance, validated_data):
        gallery = validated_data.pop("gallery_images", [])
        event = super().update(instance, validated_data)
        self._save_gallery(event, gallery)
        return event

    @staticmethod
    def _save_gallery(event, images):
        start = event.gallery_images.count()
        for offset, image in enumerate(images):
            EventGalleryImage.objects.create(
                event=event, image=image, order=start + offset
            )


class EventCancelSerializer(serializers.Serializer):
    """Reason for cancelling an event."""

    reason = serializers.ChoiceField(choices=CancellationReason.choices)
    reason_other = serializers.CharField(
        required=False, allow_blank=True, max_length=2000
    )

    def validate(self, attrs):
        if attrs["reason"] == CancellationReason.OTHER:
            if not attrs.get("reason_other", "").strip():
                raise serializers.ValidationError(
                    {"reason_other": "Describe the reason."}
                )
        else:
            # Only meaningful alongside "other"; drop it otherwise so a
            # stale note cannot linger against a specific reason.
            attrs["reason_other"] = ""
        return attrs

    def save(self, **kwargs):
        event = self.context["event"]
        event.status = self.context["cancelled_status"]
        event.cancellation_reason = self.validated_data["reason"]
        event.cancellation_reason_other = self.validated_data.get(
            "reason_other", ""
        )
        event.cancelled_at = timezone.now()
        event.save(
            update_fields=[
                "status",
                "cancellation_reason",
                "cancellation_reason_other",
                "cancelled_at",
                "updated_at",
            ]
        )
        return event


class EventGuideChoiceSerializer(serializers.ModelSerializer):
    """Team members assignable as an event's guide."""

    full_name = serializers.CharField(
        source="user.full_name", read_only=True
    )
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = TeamMember
        fields = ("id", "full_name", "email")
