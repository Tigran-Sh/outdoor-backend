"""drf-yasg schema definitions for the users API.

Each constant is a ready-to-spread mapping of ``swagger_auto_schema``
keyword arguments, keeping the view classes free of large inline
documentation blocks. Use them as::

    @swagger_auto_schema(**AUTH_LOGIN_SCHEMA)
    def post(self, request):
        ...
"""

from drf_yasg import openapi
from drf_yasg.utils import no_body

from apps.users.api.serializers import (
    AdminUserCreateSerializer,
    AdminUserSerializer,
    AdminUserUpdateSerializer,
    CapabilitiesChangeSerializer,
    CapabilitySerializer,
    ChangePasswordSerializer,
    LoginSerializer,
    LogoutSerializer,
    RoleChangeSerializer,
    RoleSerializer,
    UserPublicSerializer,
)

AUTH_TAG = "Authentication"
ADMIN_USERS_TAG = "Admin · Users"
ADMIN_ROLES_TAG = "Admin · Roles"
ADMIN_CAPABILITIES_TAG = "Admin · Capabilities"


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
AUTH_LOGIN_SCHEMA = dict(
    tags=[AUTH_TAG],
    operation_summary="Log in",
    operation_description=(
        "Authenticate with email + password. Returns JWT access and "
        "refresh tokens plus the authenticated user. Inactive users "
        "cannot log in."
    ),
    request_body=LoginSerializer,
    security=[],
    responses={
        200: LoginSerializer,
        400: openapi.Response(description="Invalid credentials"),
    },
)

AUTH_REFRESH_SCHEMA = dict(
    tags=[AUTH_TAG],
    operation_summary="Refresh access token",
    security=[],
    responses={
        200: openapi.Response(description="New access token"),
        401: openapi.Response(description="Invalid refresh token"),
    },
)

AUTH_LOGOUT_SCHEMA = dict(
    tags=[AUTH_TAG],
    operation_summary="Log out",
    operation_description="Blacklist the provided refresh token.",
    request_body=LogoutSerializer,
    responses={
        205: openapi.Response(description="Logged out"),
        400: openapi.Response(description="Invalid token"),
    },
)

AUTH_ME_SCHEMA = dict(
    tags=[AUTH_TAG],
    operation_summary="Current user",
    responses={200: UserPublicSerializer},
)

AUTH_CHANGE_PASSWORD_SCHEMA = dict(
    tags=[AUTH_TAG],
    operation_summary="Change password",
    operation_description=(
        "Verify the current password and set a new one (validated by "
        "Django password validators)."
    ),
    request_body=ChangePasswordSerializer,
    responses={
        200: openapi.Response(description="Password changed"),
        400: openapi.Response(description="Validation error"),
    },
)


# ---------------------------------------------------------------------------
# Admin: users
# ---------------------------------------------------------------------------
USER_LIST_SCHEMA = dict(
    tags=[ADMIN_USERS_TAG],
    operation_summary="List users",
    manual_parameters=[
        openapi.Parameter(
            "role",
            openapi.IN_QUERY,
            type=openapi.TYPE_STRING,
            description="Filter by role.",
        ),
        openapi.Parameter(
            "is_active",
            openapi.IN_QUERY,
            type=openapi.TYPE_BOOLEAN,
            description="Filter by active status.",
        ),
        openapi.Parameter(
            "search",
            openapi.IN_QUERY,
            type=openapi.TYPE_STRING,
            description="Search email / full name.",
        ),
    ],
    responses={200: AdminUserSerializer(many=True)},
)

USER_RETRIEVE_SCHEMA = dict(
    tags=[ADMIN_USERS_TAG],
    operation_summary="Retrieve user",
    responses={200: AdminUserSerializer},
)

USER_CREATE_SCHEMA = dict(
    tags=[ADMIN_USERS_TAG],
    operation_summary="Create user",
    operation_description=(
        "Create a user with a role. When role is 'internal_admin', a "
        "non-empty 'capabilities' list is required and becomes that user's "
        "permissions; other roles must omit 'capabilities'. You may only "
        "grant capabilities you hold."
    ),
    request_body=AdminUserCreateSerializer,
    responses={201: AdminUserSerializer},
)

USER_UPDATE_SCHEMA = dict(
    tags=[ADMIN_USERS_TAG],
    operation_summary="Update user (name/email only)",
    request_body=AdminUserUpdateSerializer,
    responses={200: AdminUserSerializer},
)

USER_ACTIVATE_SCHEMA = dict(
    method="post",
    tags=[ADMIN_USERS_TAG],
    operation_summary="Activate user",
    request_body=no_body,
    responses={200: AdminUserSerializer},
)

USER_DEACTIVATE_SCHEMA = dict(
    method="post",
    tags=[ADMIN_USERS_TAG],
    operation_summary="Deactivate user",
    request_body=no_body,
    responses={200: AdminUserSerializer},
)

USER_CHANGE_ROLE_SCHEMA = dict(
    method="patch",
    tags=[ADMIN_USERS_TAG],
    operation_summary="Change user role",
    operation_description=(
        "Dedicated, explicit role mutation. Role cannot be changed "
        "through the generic update endpoint. Assigned capabilities are "
        "cleared when moving to a role with fixed capabilities."
    ),
    request_body=RoleChangeSerializer,
    responses={200: AdminUserSerializer},
)

USER_CHANGE_CAPABILITIES_SCHEMA = dict(
    method="patch",
    tags=[ADMIN_USERS_TAG],
    operation_summary="Assign capabilities (internal_admin only)",
    operation_description=(
        "Assign the exact capability set for an internal_admin user. Only "
        "capabilities the requester holds may be granted."
    ),
    request_body=CapabilitiesChangeSerializer,
    responses={200: AdminUserSerializer},
)


# ---------------------------------------------------------------------------
# Admin: roles
# ---------------------------------------------------------------------------
ROLE_LIST_SCHEMA = dict(
    tags=[ADMIN_ROLES_TAG],
    operation_summary="List roles",
    responses={200: RoleSerializer(many=True)},
)

ROLE_DETAIL_SCHEMA = dict(
    tags=[ADMIN_ROLES_TAG],
    operation_summary="Retrieve role",
    responses={
        200: RoleSerializer,
        404: openapi.Response(description="Role not found"),
    },
)

ROLE_CAPABILITIES_SCHEMA = dict(
    tags=[ADMIN_ROLES_TAG],
    operation_summary="List a role's capabilities",
    responses={
        200: CapabilitySerializer(many=True),
        404: openapi.Response(description="Role not found"),
    },
)


# ---------------------------------------------------------------------------
# Admin: capabilities
# ---------------------------------------------------------------------------
CAPABILITY_LIST_SCHEMA = dict(
    tags=[ADMIN_CAPABILITIES_TAG],
    operation_summary="List capabilities",
    responses={200: CapabilitySerializer(many=True)},
)
