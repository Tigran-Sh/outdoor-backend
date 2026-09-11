"""drf-yasg schema definitions for the events API.

Each constant is a ready-to-spread mapping of ``swagger_auto_schema``
keyword arguments, mirroring ``apps.users.api.schema``.
"""

from drf_yasg import openapi

from apps.events.api.serializers import (
    EventCancelSerializer,
    EventSerializer,
    EventWriteSerializer,
)

EVENTS_TAG = "Events"

_FILTERS = [
    openapi.Parameter(
        name,
        openapi.IN_QUERY,
        description=description,
        type=openapi.TYPE_STRING,
    )
    for name, description in (
        ("status", "`draft`, `published`, `cancelled`, `completed`"),
        ("category", "Activity type"),
        ("region", "Region of Armenia"),
        ("difficulty", "`easy`, `medium`, `hard`, `extreme`"),
        ("club", "Club id. Only meaningful for platform staff."),
        ("club_name", "Partial club name, case-insensitive."),
        ("search", "Matches title, description, other info and club name"),
        (
            "ordering",
            "`start_at`, `created_at`, `title`, `club__name`; "
            "prefix with `-` to reverse",
        ),
    )
]

EVENT_LIST_SCHEMA = dict(
    tags=[EVENTS_TAG],
    operation_summary="List events",
    operation_description=(
        "Paginated. Everyone on a club's team sees that club's events, "
        "drafts included; a plain guide sees only the events assigned "
        "to them. Platform Admins see every club's events and can "
        "narrow by `?club=<id>` or `?club_name=<text>`."
    ),
    manual_parameters=_FILTERS,
    responses={200: EventSerializer(many=True)},
)

EVENT_RETRIEVE_SCHEMA = dict(
    tags=[EVENTS_TAG],
    operation_summary="Get an event",
    responses={
        200: EventSerializer,
        404: openapi.Response(description="Not found"),
    },
)

EVENT_CREATE_SCHEMA = dict(
    tags=[EVENTS_TAG],
    operation_summary="Create an event",
    operation_description=(
        "Requires the `create_event` capability. The club is taken from "
        "the requester; Platform Admins must pass `club`. Events start "
        "as drafts, so only `title` is really required — everything "
        "else can be filled in later and is checked when publishing. "
        "Accepts multipart/form-data for `cover_image` and "
        "`gallery_images`.\n\n"
        "Conditional rules, judged against the resulting event: "
        "`end_at` is required when `duration_type` is `multi` and "
        "rejected otherwise; `price` is required when `price_type` is "
        "`paid` and rejected when `free`; `guide` must be active staff "
        "of the same club."
    ),
    request_body=EventWriteSerializer,
    responses={
        201: EventSerializer,
        400: openapi.Response(description="Validation error"),
        403: openapi.Response(description="Not allowed"),
    },
)

EVENT_UPDATE_SCHEMA = dict(
    tags=[EVENTS_TAG],
    operation_summary="Update an event",
    operation_description=(
        "Requires the `edit_event` capability. `status` and "
        "`sold_count` are not editable here; use publish / cancel. A "
        "cancelled event is read-only."
    ),
    request_body=EventWriteSerializer,
    responses={
        200: EventSerializer,
        400: openapi.Response(description="Validation error"),
    },
)

EVENT_DELETE_SCHEMA = dict(
    tags=[EVENTS_TAG],
    operation_summary="Delete a draft event",
    operation_description=(
        "Only a draft can be deleted. Once published, an event is "
        "cancelled rather than removed, so its history survives."
    ),
    responses={
        204: openapi.Response(description="Deleted"),
        400: openapi.Response(description="Not a draft"),
    },
)

EVENT_PUBLISH_SCHEMA = dict(
    tags=[EVENTS_TAG],
    operation_summary="Publish an event",
    operation_description=(
        "Requires the `publish_event` capability. Fails with 400 and a "
        "`missing_to_publish` list when the event is incomplete."
    ),
    request_body=None,
    responses={
        200: EventSerializer,
        400: openapi.Response(description="Incomplete or cancelled"),
        403: openapi.Response(description="Not allowed"),
    },
)

EVENT_CANCEL_SCHEMA = dict(
    tags=[EVENTS_TAG],
    operation_summary="Cancel an event",
    operation_description=(
        "Requires the `cancel_event` capability. `reason_other` is "
        "required when `reason` is `other`, and ignored otherwise."
    ),
    request_body=EventCancelSerializer,
    responses={
        200: EventSerializer,
        400: openapi.Response(description="Validation error"),
        403: openapi.Response(description="Not allowed"),
    },
)
