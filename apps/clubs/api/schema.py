"""drf-yasg schema definitions for the clubs / team API.

Each constant is a ready-to-spread mapping of ``swagger_auto_schema``
keyword arguments, mirroring ``apps.users.api.schema``.
"""

from drf_yasg import openapi

from apps.clubs.api.serializers import (
    AdminClubCreateSerializer,
    ClubSerializer,
    ClubUpdateSerializer,
    TeamMemberCreateSerializer,
    TeamMemberSerializer,
    TeamMemberUpdateSerializer,
)

CLUB_TAG = "Club"
TEAM_TAG = "Club · Team members"
ADMIN_CLUBS_TAG = "Admin · Clubs"

_CLUB_QUERY_PARAM = openapi.Parameter(
    "club",
    openapi.IN_QUERY,
    description=(
        "Narrow results to a club id. Only meaningful for readers who "
        "are not restricted to a single club."
    ),
    type=openapi.TYPE_STRING,
)


MY_CLUB_SCHEMA = dict(
    tags=[CLUB_TAG],
    operation_summary="Get my club",
    operation_description=(
        "Returns the club owned by the authenticated user. Responds 404 "
        "when the user does not own a club."
    ),
    responses={
        200: ClubSerializer,
        404: openapi.Response(description="No club owned by this user"),
    },
)

MY_CLUB_UPDATE_SCHEMA = dict(
    tags=[CLUB_TAG],
    operation_summary="Update my club",
    operation_description=(
        "Club Owner edits their own club. Accepts multipart/form-data "
        "for `logo`, `cover_image` and `owner_id_document`. The owner, "
        "status and the verification flags are not editable here. The "
        "profile is filled in over several partial saves, so rules are "
        "checked against the resulting state: `tax_id` is required once "
        "`entity_type` is `sole_trader`/`llc`, `owner_id_document` once "
        "it is `individual`/`informal`, and the social links cannot all "
        "be cleared at once. `missing_profile_fields` on the response "
        "reports what is still outstanding."
    ),
    request_body=ClubUpdateSerializer,
    responses={
        200: ClubSerializer,
        400: openapi.Response(description="Validation error"),
        404: openapi.Response(description="No club owned by this user"),
    },
)

CLUB_ID_DOCUMENT_SCHEMA = dict(
    tags=[CLUB_TAG],
    operation_summary="Download a club's identity document",
    operation_description=(
        "Identity documents are stored outside the public media tree "
        "and are only served here, to the club's owner and to staff "
        "holding `verify_club`."
    ),
    responses={
        200: openapi.Response(description="The file"),
        403: openapi.Response(description="Not allowed"),
        404: openapi.Response(description="No document uploaded"),
    },
)

TEAM_LIST_SCHEMA = dict(
    tags=[TEAM_TAG],
    operation_summary="List team members",
    operation_description=(
        "Club Owners see their own club's team. Platform Admins (and "
        "platform-level holders of `view_team_members`) see all clubs; "
        "readers tied to a club see only that club."
    ),
    manual_parameters=[_CLUB_QUERY_PARAM],
    responses={200: TeamMemberSerializer(many=True)},
)

TEAM_RETRIEVE_SCHEMA = dict(
    tags=[TEAM_TAG],
    operation_summary="Get a team member",
    responses={
        200: TeamMemberSerializer,
        404: openapi.Response(description="Not found"),
    },
)

TEAM_CREATE_SCHEMA = dict(
    tags=[TEAM_TAG],
    operation_summary="Create a team member",
    operation_description=(
        "Creates the team member together with their login account. "
        "Only `full_name`, `email` and `password` are required. "
        "`platform_role` is limited to `guide` or `internal_admin`, and "
        "`internal_admin` requires at least one permission. Permissions "
        "are capped at what the requester already holds and apply only "
        "inside this club. Accepts multipart/form-data for `photo` and "
        "`certificates`."
    ),
    request_body=TeamMemberCreateSerializer,
    responses={
        201: TeamMemberSerializer,
        400: openapi.Response(description="Validation error"),
        403: openapi.Response(description="Not allowed"),
    },
)

TEAM_UPDATE_SCHEMA = dict(
    tags=[TEAM_TAG],
    operation_summary="Update a team member",
    operation_description=(
        "Updates profile fields. Passwords are not changed here; the "
        "member uses the standard change-password endpoint."
    ),
    request_body=TeamMemberUpdateSerializer,
    responses={
        200: TeamMemberSerializer,
        400: openapi.Response(description="Validation error"),
    },
)

TEAM_DELETE_SCHEMA = dict(
    tags=[TEAM_TAG],
    operation_summary="Deactivate a team member",
    operation_description=(
        "Soft delete: deactivates the membership and their login "
        "account. The records are never removed."
    ),
    responses={204: openapi.Response(description="Deactivated")},
)

_CLUB_FILTERS = [
    openapi.Parameter(
        name,
        openapi.IN_QUERY,
        description=description,
        type=openapi.TYPE_STRING,
    )
    for name, description in (
        ("identity_verified", "`true` / `false`"),
        ("payment_verified", "`true` / `false`"),
        ("entity_type", "Legal entity type"),
        ("base_region", "Region of Armenia"),
        ("status", "Club lifecycle status"),
    )
]

ADMIN_CLUB_LIST_SCHEMA = dict(
    tags=[ADMIN_CLUBS_TAG],
    operation_summary="List clubs",
    manual_parameters=_CLUB_FILTERS,
    responses={200: ClubSerializer(many=True)},
)

ADMIN_CLUB_RETRIEVE_SCHEMA = dict(
    tags=[ADMIN_CLUBS_TAG],
    operation_summary="Get a club",
    responses={200: ClubSerializer},
)

ADMIN_CLUB_CREATE_SCHEMA = dict(
    tags=[ADMIN_CLUBS_TAG],
    operation_summary="Create a club and assign its owner",
    operation_description=(
        "Platform Admin only. The assigned owner is promoted to the "
        "`club_owner` role. A user may own at most one club."
    ),
    request_body=AdminClubCreateSerializer,
    responses={
        201: ClubSerializer,
        400: openapi.Response(description="Validation error"),
    },
)
