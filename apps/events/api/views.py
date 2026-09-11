from collections import defaultdict
from datetime import datetime, time, timedelta

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.dateparse import parse_date
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from apps.clubs.models import Club, TeamMember
from apps.clubs.services import authorization as clubs_authorization
from apps.events.api.permissions import CanAccessEvents
from apps.events.api.schema import (
    EVENT_CANCEL_SCHEMA,
    EVENT_CREATE_SCHEMA,
    EVENT_DELETE_SCHEMA,
    EVENT_GUIDE_AVAILABILITY_SCHEMA,
    EVENT_LIST_SCHEMA,
    EVENT_PUBLISH_SCHEMA,
    EVENT_RETRIEVE_SCHEMA,
    EVENT_UPDATE_SCHEMA,
)
from apps.events.api.serializers import (
    EventCancelSerializer,
    EventSerializer,
    EventWriteSerializer,
    GuideAvailabilitySerializer,
)
from apps.events.constants import EventStatus
from apps.events.models import Event
from apps.events.services import authorization
from apps.users.constants import Role

# A calendar asks for a month at a time; the cap keeps a hand-written
# query string from pulling a club's entire history.
DEFAULT_CALENDAR_DAYS = 30
MAX_CALENDAR_DAYS = 186


def _club_by_id(club_id):
    """Look a club up, tolerating a malformed id."""
    if not club_id:
        return None
    try:
        return Club.objects.filter(pk=club_id).first()
    except (ValueError, TypeError, DjangoValidationError):
        return None


def _parse_date(value, field):
    if not value:
        return None
    try:
        parsed = parse_date(value)
    except ValueError:
        parsed = None
    if parsed is None:
        raise ValidationError({field: "Use the format YYYY-MM-DD."})
    return parsed


def _start_of_day(day):
    return timezone.make_aware(datetime.combine(day, time.min))


class EventViewSet(viewsets.ModelViewSet):
    """Club events, scoped to the requester's club."""

    queryset = Event.objects.select_related(
        "club", "guide", "guide__user"
    ).prefetch_related("gallery_images")
    permission_classes = [CanAccessEvents]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["title", "description", "other_info", "club__name"]
    ordering_fields = ["start_at", "created_at", "title", "club__name"]
    ordering = ["-start_at", "-created_at"]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    FILTER_FIELDS = ("status", "category", "region", "difficulty")

    def get_serializer_class(self):
        if self.action in ("create", "partial_update"):
            return EventWriteSerializer
        if self.action == "cancel":
            return EventCancelSerializer
        return EventSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if self.action == "create":
            context["club"] = self._club_for_write()
        return context

    def _club_for_write(self):
        """The club a create acts on."""
        club = authorization.club_for_user(self.request.user)
        if club is None:
            # Platform admins belong to no club; they must say which one.
            club_id = self.request.data.get("club")
            club = Club.objects.filter(pk=club_id).first() if club_id else None
            if club is None:
                raise PermissionDenied(
                    "Specify a club to create this event for."
                )
        if not authorization.can_create_event(self.request.user, club):
            raise PermissionDenied("You cannot create events for this club.")
        return club

    def get_queryset(self):
        qs = authorization.visible_events(
            self.request.user, super().get_queryset()
        )
        params = self.request.query_params
        club_id = params.get("club")
        if club_id and authorization.readable_club_scope(
            self.request.user
        ) is authorization.ALL_CLUBS:
            qs = qs.filter(club_id=club_id)

        for field in self.FILTER_FIELDS:
            value = params.get(field)
            if value:
                qs = qs.filter(**{field: value})

        # Staff browsing every club know the club by name, not by id.
        club_name = params.get("club_name")
        if club_name:
            qs = qs.filter(club__name__icontains=club_name)
        return qs

    @swagger_auto_schema(**EVENT_LIST_SCHEMA)
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(**EVENT_RETRIEVE_SCHEMA)
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @swagger_auto_schema(**EVENT_CREATE_SCHEMA)
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        event = serializer.save()
        return Response(
            EventSerializer(event).data, status=status.HTTP_201_CREATED
        )

    @swagger_auto_schema(**EVENT_UPDATE_SCHEMA)
    def partial_update(self, request, *args, **kwargs):
        event = self.get_object()
        if event.status == EventStatus.CANCELLED:
            raise ValidationError("A cancelled event cannot be edited.")
        serializer = self.get_serializer(
            event, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        event.refresh_from_db()
        return Response(EventSerializer(event).data)

    @swagger_auto_schema(**EVENT_DELETE_SCHEMA)
    def destroy(self, request, *args, **kwargs):
        event = self.get_object()
        if event.status != EventStatus.DRAFT:
            raise ValidationError(
                "Only a draft can be deleted; cancel the event instead."
            )
        return super().destroy(request, *args, **kwargs)

    @swagger_auto_schema(**EVENT_PUBLISH_SCHEMA)
    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        event = self.get_object()
        if event.status == EventStatus.CANCELLED:
            raise ValidationError("A cancelled event cannot be published.")

        missing = event.missing_to_publish()
        if missing:
            raise ValidationError(
                {
                    "missing_to_publish": missing,
                    "detail": "Complete the event before publishing.",
                }
            )

        if event.status != EventStatus.PUBLISHED:
            event.status = EventStatus.PUBLISHED
            event.save(update_fields=["status", "updated_at"])
        return Response(EventSerializer(event).data)

    @swagger_auto_schema(**EVENT_GUIDE_AVAILABILITY_SCHEMA)
    @action(
        detail=False,
        url_path="guide-availability",
        pagination_class=None,
    )
    def guide_availability(self, request):
        """The club's guides and what each is booked for in a window.

        Availability is not stored anywhere: a guide is busy when an
        event they are assigned to overlaps the window, which is what
        the club's calendar draws.
        """
        club = self._club_for_calendar()
        window_start, window_end = self._calendar_window()
        guides = (
            TeamMember.objects.filter(
                club=club,
                is_active=True,
                user__is_active=True,
                user__role=Role.GUIDE,
            )
            .select_related("user")
            .order_by("user__full_name", "user__email")
        )
        serializer = GuideAvailabilitySerializer(
            guides,
            many=True,
            context={
                **self.get_serializer_context(),
                "assignments": self._assignments(
                    club, window_start, window_end
                ),
            },
        )
        return Response(serializer.data)

    def _club_for_calendar(self):
        """The club whose guides the requester may see."""
        scope = clubs_authorization.readable_club_scope(self.request.user)
        if scope is None:
            raise PermissionDenied("You cannot view this club's team.")
        if scope is not clubs_authorization.ALL_CLUBS:
            return scope
        # Platform staff belong to no club; they must say which one.
        club = _club_by_id(self.request.query_params.get("club"))
        if club is None:
            raise ValidationError(
                {"club": "Specify a club to see its guides."}
            )
        return club

    def _calendar_window(self):
        """The asked date range, as aware datetimes [start, end)."""
        params = self.request.query_params
        start_date = _parse_date(params.get("from"), "from")
        end_date = _parse_date(params.get("to"), "to")
        if start_date is None:
            start_date = timezone.localdate()
        if end_date is None:
            end_date = start_date + timedelta(days=DEFAULT_CALENDAR_DAYS)
        if end_date < start_date:
            raise ValidationError({"to": "Must be on or after `from`."})
        if (end_date - start_date).days > MAX_CALENDAR_DAYS:
            raise ValidationError(
                {"to": f"Ask for at most {MAX_CALENDAR_DAYS} days at once."}
            )
        return (
            _start_of_day(start_date),
            # Exclusive: the day after the last one asked for.
            _start_of_day(end_date + timedelta(days=1)),
        )

    @staticmethod
    def _assignments(club, window_start, window_end):
        """Map of team member id -> events overlapping the window.

        A cancelled event frees its guide; a dateless draft cannot be
        placed on a calendar at all.
        """
        events = (
            Event.objects.filter(
                club=club,
                guide__isnull=False,
                start_at__isnull=False,
            )
            .exclude(status=EventStatus.CANCELLED)
            .annotate(finish=Coalesce("end_at", "start_at"))
            .filter(start_at__lt=window_end, finish__gte=window_start)
            .order_by("start_at")
        )
        grouped = defaultdict(list)
        for event in events:
            grouped[event.guide_id].append(event)
        return grouped

    @swagger_auto_schema(**EVENT_CANCEL_SCHEMA)
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        event = self.get_object()
        if event.status == EventStatus.CANCELLED:
            raise ValidationError("This event is already cancelled.")

        serializer = self.get_serializer(
            data=request.data,
            context={
                **self.get_serializer_context(),
                "event": event,
                "cancelled_status": EventStatus.CANCELLED,
            },
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        event.refresh_from_db()
        return Response(EventSerializer(event).data)
