from drf_yasg.utils import swagger_auto_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from apps.clubs.models import Club
from apps.events.api.permissions import CanAccessEvents
from apps.events.api.schema import (
    EVENT_CANCEL_SCHEMA,
    EVENT_CREATE_SCHEMA,
    EVENT_DELETE_SCHEMA,
    EVENT_LIST_SCHEMA,
    EVENT_PUBLISH_SCHEMA,
    EVENT_RETRIEVE_SCHEMA,
    EVENT_UPDATE_SCHEMA,
)
from apps.events.api.serializers import (
    EventCancelSerializer,
    EventSerializer,
    EventWriteSerializer,
)
from apps.events.constants import EventStatus
from apps.events.models import Event
from apps.events.services import authorization


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
