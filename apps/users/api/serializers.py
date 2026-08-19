from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from apps.users.constants import (
    CUSTOM_CAPABILITY_ROLES,
    Capability,
    Role,
)
from apps.users.services import authorization

User = get_user_model()


def _reject_ungrantable(request, capabilities):
    """Raise if the request user cannot grant one of ``capabilities``."""
    user = getattr(request, "user", None)
    not_allowed = authorization.can_grant_capabilities(user, capabilities)
    if not_allowed:
        raise serializers.ValidationError(
            "You cannot grant these capabilities: "
            + ", ".join(sorted(not_allowed))
        )


class UserPublicSerializer(serializers.ModelSerializer):
    """Minimal user representation returned by auth endpoints."""

    capabilities = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "email", "full_name", "role", "capabilities")
        read_only_fields = ("id", "email", "full_name", "role")

    def get_capabilities(self, obj):
        return sorted(obj.capabilities)


class LoginSerializer(serializers.Serializer):
    """Validates email + password and issues JWT tokens."""

    email = serializers.EmailField(write_only=True)
    password = serializers.CharField(
        write_only=True, style={"input_type": "password"}
    )

    access = serializers.CharField(read_only=True)
    refresh = serializers.CharField(read_only=True)
    user = UserPublicSerializer(read_only=True)

    default_error_messages = {
        "invalid_credentials": "Unable to log in with provided credentials.",
    }

    def validate(self, attrs):
        request = self.context.get("request")
        # ``authenticate`` returns None for wrong credentials AND for
        # inactive users, avoiding user enumeration.
        user = authenticate(
            request=request,
            username=attrs["email"],
            password=attrs["password"],
        )
        if user is None:
            self.fail("invalid_credentials")

        refresh = RefreshToken.for_user(user)
        return {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": user,
        }


class LogoutSerializer(serializers.Serializer):
    """Blacklists a refresh token."""

    refresh = serializers.CharField(write_only=True)

    default_error_messages = {
        "invalid_token": "Token is invalid or already blacklisted.",
    }

    def save(self, **kwargs):
        try:
            token = RefreshToken(self.validated_data["refresh"])
            token.blacklist()
        except Exception:
            # Covers invalid, expired or already-blacklisted tokens.
            self.fail("invalid_token")


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(
        write_only=True, style={"input_type": "password"}
    )
    new_password = serializers.CharField(
        write_only=True, style={"input_type": "password"}
    )

    default_error_messages = {
        "wrong_password": "Current password is incorrect.",
    }

    def validate_current_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            self.fail("wrong_password")
        return value

    def validate_new_password(self, value):
        user = self.context["request"].user
        validate_password(value, user=user)
        return value

    def save(self, **kwargs):
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.save(update_fields=["password", "updated_at"])
        return user


class AdminUserSerializer(serializers.ModelSerializer):
    """Read representation for admin user-management APIs."""

    capabilities = serializers.SerializerMethodField()
    created_by = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "full_name",
            "role",
            "is_active",
            "capabilities",
            "custom_capabilities",
            "created_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "email",
            "full_name",
            "role",
            "is_active",
            "custom_capabilities",
            "created_at",
            "updated_at",
        )

    def get_capabilities(self, obj):
        return sorted(obj.capabilities)

    def get_created_by(self, obj):
        return obj.created_by.email if obj.created_by else None


class AdminUserCreateSerializer(serializers.ModelSerializer):
    """Create a user (Platform Admin only). Password is hashed.

    When ``role`` is ``internal_admin`` a non-empty ``capabilities`` list
    must be supplied; for every other role ``capabilities`` must be empty.
    Capabilities are bounded by what the requesting user may grant.
    """

    password = serializers.CharField(
        write_only=True, style={"input_type": "password"}
    )
    role = serializers.ChoiceField(choices=Role.choices)
    capabilities = serializers.ListField(
        child=serializers.ChoiceField(choices=Capability.choices),
        required=False,
        default=list,
    )

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "full_name",
            "role",
            "password",
            "capabilities",
        )
        read_only_fields = ("id",)

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate(self, attrs):
        role = attrs["role"]
        capabilities = sorted(set(attrs.get("capabilities") or []))
        requires_custom = role in CUSTOM_CAPABILITY_ROLES

        if requires_custom and not capabilities:
            raise serializers.ValidationError(
                {"capabilities": "This role requires at least one capability."}
            )
        if not requires_custom and capabilities:
            raise serializers.ValidationError(
                {"capabilities": "This role does not accept custom capabilities."}
            )
        if capabilities:
            _reject_ungrantable(self.context.get("request"), capabilities)

        attrs["capabilities"] = capabilities
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        capabilities = validated_data.pop("capabilities", [])
        request = self.context.get("request")
        creator = getattr(request, "user", None)
        return User.objects.create_user(
            password=password,
            custom_capabilities=capabilities,
            created_by=creator if creator and creator.is_authenticated else None,
            **validated_data,
        )


class AdminUserUpdateSerializer(serializers.ModelSerializer):
    """Restricted update. Security-sensitive fields are NOT accepted.

    ``role``, ``is_staff``, ``is_superuser``, ``is_active`` and
    ``password`` are intentionally excluded to prevent privilege
    escalation / mass assignment. They have dedicated endpoints.
    """

    class Meta:
        model = User
        fields = ("id", "email", "full_name")
        read_only_fields = ("id",)


class RoleChangeSerializer(serializers.Serializer):
    """Dedicated, explicit role mutation endpoint payload."""

    role = serializers.ChoiceField(choices=Role.choices)


class CapabilitiesChangeSerializer(serializers.Serializer):
    """Dedicated capability assignment for INTERNAL_ADMIN users."""

    capabilities = serializers.ListField(
        child=serializers.ChoiceField(choices=Capability.choices),
        allow_empty=False,
    )

    def validate_capabilities(self, value):
        capabilities = sorted(set(value))
        _reject_ungrantable(self.context.get("request"), capabilities)
        return capabilities


class RoleSerializer(serializers.Serializer):
    """Read representation of a code-defined role."""

    key = serializers.CharField()
    name = serializers.CharField()
    capabilities = serializers.ListField(child=serializers.CharField())


class CapabilitySerializer(serializers.Serializer):
    """Read representation of a code-defined capability."""

    key = serializers.CharField()
    name = serializers.CharField()
