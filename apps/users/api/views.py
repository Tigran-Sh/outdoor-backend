from django.contrib.auth import get_user_model
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenRefreshView

from apps.users.api.permissions import IsPlatformAdmin
from apps.users.api.schema import (
    AUTH_CHANGE_PASSWORD_SCHEMA,
    AUTH_LOGIN_SCHEMA,
    AUTH_LOGOUT_SCHEMA,
    AUTH_ME_SCHEMA,
    AUTH_REFRESH_SCHEMA,
    CAPABILITY_LIST_SCHEMA,
    ROLE_CAPABILITIES_SCHEMA,
    ROLE_DETAIL_SCHEMA,
    ROLE_LIST_SCHEMA,
    USER_ACTIVATE_SCHEMA,
    USER_CHANGE_CAPABILITIES_SCHEMA,
    USER_CHANGE_ROLE_SCHEMA,
    USER_CREATE_SCHEMA,
    USER_DEACTIVATE_SCHEMA,
    USER_LIST_SCHEMA,
    USER_RETRIEVE_SCHEMA,
    USER_UPDATE_SCHEMA,
)
from apps.users.api.serializers import (
    AdminUserCreateSerializer,
    AdminUserSerializer,
    AdminUserUpdateSerializer,
    CapabilitiesChangeSerializer,
    ChangePasswordSerializer,
    LoginSerializer,
    LogoutSerializer,
    RoleChangeSerializer,
    UserPublicSerializer,
)
from apps.users.constants import CUSTOM_CAPABILITY_ROLES, Role
from apps.users.services.catalog import CapabilityCatalog, RoleCatalog

User = get_user_model()


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = LoginSerializer

    @swagger_auto_schema(**AUTH_LOGIN_SCHEMA)
    def post(self, request):
        serializer = self.serializer_class(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class RefreshView(TokenRefreshView):
    """Exchange a valid refresh token for a new access token."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @swagger_auto_schema(**AUTH_REFRESH_SCHEMA)
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = LogoutSerializer

    @swagger_auto_schema(**AUTH_LOGOUT_SCHEMA)
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(status=status.HTTP_205_RESET_CONTENT)


class MeView(RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserPublicSerializer

    def get_object(self):
        return self.request.user

    @swagger_auto_schema(**AUTH_ME_SCHEMA)
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ChangePasswordSerializer

    @swagger_auto_schema(**AUTH_CHANGE_PASSWORD_SCHEMA)
    def post(self, request):
        serializer = self.serializer_class(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {"status": "password_changed"}, status=status.HTTP_200_OK
        )


class AdminUserViewSet(viewsets.ModelViewSet):
    """Platform-wide user management. Restricted to Platform Admin."""

    queryset = User.objects.all()
    permission_classes = [IsPlatformAdmin]
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["email", "full_name"]
    ordering_fields = ["created_at", "email", "full_name"]
    ordering = ["-created_at"]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_serializer_class(self):
        if self.action == "create":
            return AdminUserCreateSerializer
        if self.action == "partial_update":
            return AdminUserUpdateSerializer
        if self.action == "change_role":
            return RoleChangeSerializer
        if self.action == "change_capabilities":
            return CapabilitiesChangeSerializer
        return AdminUserSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        role = self.request.query_params.get("role")
        if role in Role.values:
            qs = qs.filter(role=role)
        is_active = self.request.query_params.get("is_active")
        if is_active is not None:
            truthy = is_active.lower() in {"true", "1", "yes"}
            qs = qs.filter(is_active=truthy)
        return qs

    @swagger_auto_schema(**USER_LIST_SCHEMA)
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(**USER_RETRIEVE_SCHEMA)
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @swagger_auto_schema(**USER_CREATE_SCHEMA)
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        output = AdminUserSerializer(user)
        return Response(output.data, status=status.HTTP_201_CREATED)

    @swagger_auto_schema(**USER_UPDATE_SCHEMA)
    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(
            instance, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(AdminUserSerializer(instance).data)

    @swagger_auto_schema(**USER_ACTIVATE_SCHEMA)
    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        user = self.get_object()
        if not user.is_active:
            user.is_active = True
            user.save(update_fields=["is_active", "updated_at"])
        return Response(AdminUserSerializer(user).data)

    @swagger_auto_schema(**USER_DEACTIVATE_SCHEMA)
    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        user = self.get_object()
        if user.is_active:
            user.is_active = False
            user.save(update_fields=["is_active", "updated_at"])
        return Response(AdminUserSerializer(user).data)

    @swagger_auto_schema(**USER_CHANGE_ROLE_SCHEMA)
    @action(detail=True, methods=["patch"], url_path="role")
    def change_role(self, request, pk=None):
        user = self.get_object()
        serializer = RoleChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_role = serializer.validated_data["role"]
        user.role = new_role
        update_fields = ["role", "updated_at"]
        # Assigned capabilities only apply to custom-capability roles;
        # drop them when moving to a role with fixed capabilities.
        if new_role not in CUSTOM_CAPABILITY_ROLES and user.custom_capabilities:
            user.custom_capabilities = []
            update_fields.append("custom_capabilities")
        user.save(update_fields=update_fields)
        return Response(AdminUserSerializer(user).data)

    @swagger_auto_schema(**USER_CHANGE_CAPABILITIES_SCHEMA)
    @action(detail=True, methods=["patch"], url_path="capabilities")
    def change_capabilities(self, request, pk=None):
        user = self.get_object()
        if user.role not in CUSTOM_CAPABILITY_ROLES:
            raise ValidationError(
                "Capabilities can only be assigned to internal_admin users."
            )
        serializer = CapabilitiesChangeSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        user.custom_capabilities = serializer.validated_data["capabilities"]
        user.save(update_fields=["custom_capabilities", "updated_at"])
        return Response(AdminUserSerializer(user).data)


class RoleListView(APIView):
    permission_classes = [IsPlatformAdmin]

    @swagger_auto_schema(**ROLE_LIST_SCHEMA)
    def get(self, request):
        return Response(RoleCatalog.list())


class RoleDetailView(APIView):
    permission_classes = [IsPlatformAdmin]

    @swagger_auto_schema(**ROLE_DETAIL_SCHEMA)
    def get(self, request, role):
        role_obj = RoleCatalog.get(role)
        if role_obj is None:
            raise NotFound("Role not found.")
        return Response(RoleCatalog.serialize(role_obj))


class RoleCapabilitiesView(APIView):
    permission_classes = [IsPlatformAdmin]

    @swagger_auto_schema(**ROLE_CAPABILITIES_SCHEMA)
    def get(self, request, role):
        role_obj = RoleCatalog.get(role)
        if role_obj is None:
            raise NotFound("Role not found.")
        return Response(RoleCatalog.serialize_capabilities(role_obj))


class CapabilityListView(APIView):
    permission_classes = [IsPlatformAdmin]

    @swagger_auto_schema(**CAPABILITY_LIST_SCHEMA)
    def get(self, request):
        return Response(CapabilityCatalog.list())
