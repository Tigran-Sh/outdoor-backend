from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from apps.clubs.constants import (
    ABOUT_MIN_LENGTH,
    ID_DOCUMENT_ENTITY_TYPES,
    SOCIAL_FIELDS,
    TAX_ID_ENTITY_TYPES,
    TEAM_MEMBER_ROLES,
    YEAR_FOUNDED_MIN,
    ClubStatus,
)
from apps.common.constants import ActivityType, Language
from apps.clubs.models import Club, TeamMember, TeamMemberCertificate
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
            "You cannot grant these permissions: "
            + ", ".join(sorted(not_allowed))
        )


class ClubSerializer(serializers.ModelSerializer):
    """Full club profile.

    ``owner_id_document`` is never exposed as a file URL: it is private
    (see ``apps.common.storage``) and only reachable through the
    download endpoint, so this reports whether one was uploaded.
    """

    owner_email = serializers.EmailField(source="owner.email", read_only=True)
    has_owner_id_document = serializers.SerializerMethodField()
    missing_profile_fields = serializers.SerializerMethodField()

    class Meta:
        model = Club
        fields = (
            "id",
            "name",
            "status",
            "owner",
            "owner_email",
            "logo",
            "cover_image",
            "about",
            "activity_types",
            "base_region",
            "year_founded",
            "email",
            "phone",
            "instagram",
            "facebook",
            "telegram",
            "website",
            "entity_type",
            "tax_id",
            "has_owner_id_document",
            "identity_verified",
            "payment_verified",
            "missing_profile_fields",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_has_owner_id_document(self, obj):
        return bool(obj.owner_id_document)

    def get_missing_profile_fields(self, obj):
        return obj.missing_profile_fields()


class ClubUpdateSerializer(serializers.ModelSerializer):
    """A Club Owner editing their own club.

    Owner, status and the verification flags are absent by design: the
    owner may not reassign their club, approve it or verify themselves.
    """

    activity_types = serializers.ListField(
        child=serializers.ChoiceField(choices=ActivityType.choices),
        required=False,
    )

    class Meta:
        model = Club
        fields = (
            "name",
            "logo",
            "cover_image",
            "about",
            "activity_types",
            "base_region",
            "year_founded",
            "email",
            "phone",
            "instagram",
            "facebook",
            "telegram",
            "website",
            "entity_type",
            "tax_id",
            "owner_id_document",
        )

    def validate_name(self, value):
        if not value.strip():
            raise serializers.ValidationError("Name cannot be empty.")
        return value

    def validate_about(self, value):
        if value and len(value.strip()) < ABOUT_MIN_LENGTH:
            raise serializers.ValidationError(
                f"Tell members at least {ABOUT_MIN_LENGTH} characters "
                "about the club."
            )
        return value

    def validate_activity_types(self, value):
        if not value:
            raise serializers.ValidationError(
                "Choose at least one activity type."
            )
        if len(set(value)) != len(value):
            raise serializers.ValidationError(
                "Duplicate activity types."
            )
        return value

    def validate_year_founded(self, value):
        current_year = timezone.now().year
        if value is not None and not (
            YEAR_FOUNDED_MIN <= value <= current_year
        ):
            raise serializers.ValidationError(
                f"Enter a year between {YEAR_FOUNDED_MIN} and "
                f"{current_year}."
            )
        return value

    def _resulting(self, attrs, field):
        """The value ``field`` will hold once ``attrs`` is applied.

        The profile is filled in over many partial saves, so the rules
        below have to judge the end state rather than this one payload.
        """
        if field in attrs:
            return attrs[field]
        if self.instance is None:
            return None
        return getattr(self.instance, field)

    def validate(self, attrs):
        entity_type = self._resulting(attrs, "entity_type")
        if entity_type in TAX_ID_ENTITY_TYPES and not self._resulting(
            attrs, "tax_id"
        ):
            raise serializers.ValidationError(
                {"tax_id": "Required for this legal entity type."}
            )
        if entity_type in ID_DOCUMENT_ENTITY_TYPES and not self._resulting(
            attrs, "owner_id_document"
        ):
            raise serializers.ValidationError(
                {
                    "owner_id_document": (
                        "Required for this legal entity type."
                    )
                }
            )

        # Only enforced when the owner touches the social fields, so an
        # unrelated edit is never blocked by an incomplete profile.
        if any(field in attrs for field in SOCIAL_FIELDS):
            if not any(
                self._resulting(attrs, field) for field in SOCIAL_FIELDS
            ):
                raise serializers.ValidationError(
                    "Provide at least one of Instagram, Facebook or "
                    "Telegram."
                )
        return attrs


class AdminClubCreateSerializer(ClubUpdateSerializer):
    """Platform Admin creates a club and assigns its owner.

    Accepts the whole profile, not just a name: an admin registering a
    club on someone's behalf types in what the club gave them, and the
    owner edits the rest later through ``/api/v1/club/``.
    """

    owner = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all()
    )
    status = serializers.ChoiceField(
        choices=ClubStatus.choices, default=ClubStatus.APPROVED
    )

    class Meta(ClubUpdateSerializer.Meta):
        fields = ClubUpdateSerializer.Meta.fields + (
            "id",
            "owner",
            "status",
        )
        read_only_fields = ("id",)

    def validate_owner(self, value):
        if Club.objects.filter(owner=value).exists():
            raise serializers.ValidationError(
                "This user already owns a club."
            )
        return value

    def create(self, validated_data):
        # A Platform Admin vets the club before creating it, so there is
        # nothing left to check and it starts verified. The *model*
        # default stays False on purpose: when clubs can register
        # themselves, an unvetted one must never arrive pre-trusted.
        validated_data.setdefault("identity_verified", True)
        validated_data.setdefault("payment_verified", True)

        club = super().create(validated_data)
        owner = club.owner
        if owner.role != Role.CLUB_OWNER:
            owner.role = Role.CLUB_OWNER
            owner.save(update_fields=["role", "updated_at"])
        return club


class AdminClubUpdateSerializer(ClubUpdateSerializer):
    """Platform Admin editing any club.

    The same profile fields the owner may edit, plus the lifecycle
    status and the verification flags, which are staff-only. ``owner``
    is deliberately absent: reassigning a club to a different person is
    not an edit, and nothing in the product asks for it yet.
    """

    status = serializers.ChoiceField(
        choices=ClubStatus.choices, required=False
    )

    class Meta(ClubUpdateSerializer.Meta):
        fields = ClubUpdateSerializer.Meta.fields + (
            "status",
            "identity_verified",
            "payment_verified",
        )


class AvailableOwnerSerializer(serializers.ModelSerializer):
    """A club owner who does not yet own a club."""

    class Meta:
        model = User
        fields = ("id", "email", "full_name")
        read_only_fields = fields


class TeamMemberCertificateSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeamMemberCertificate
        fields = ("id", "file", "created_at")
        read_only_fields = fields


class TeamMemberSerializer(serializers.ModelSerializer):
    """Read representation of a club team member."""

    email = serializers.EmailField(source="user.email", read_only=True)
    full_name = serializers.CharField(
        source="user.full_name", read_only=True
    )
    platform_role = serializers.CharField(source="user.role", read_only=True)
    # Effective capabilities: role defaults for a guide, the assigned set
    # for an internal admin. Derived, never stored on this row.
    permissions = serializers.SerializerMethodField()
    account_is_active = serializers.BooleanField(
        source="user.is_active", read_only=True
    )
    certificates = TeamMemberCertificateSerializer(many=True, read_only=True)

    class Meta:
        model = TeamMember
        fields = (
            "id",
            "club",
            "user",
            "email",
            "full_name",
            "platform_role",
            "account_is_active",
            "permissions",
            "activity_types",
            "languages",
            "photo",
            "phone",
            "birth_date",
            "experience_years",
            "bio",
            "certificates",
            "is_active",
            "joined_date",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "club",
            "user",
            "joined_date",
            "created_at",
            "updated_at",
        )

    def get_permissions(self, obj):
        return sorted(obj.user.capabilities)


class TeamMemberWriteMixin:
    """Shared validation for team-member create/update payloads."""

    def _validate_permissions(self, value):
        permissions = sorted(set(value))
        _reject_ungrantable(self.context.get("request"), permissions)
        return permissions


class TeamMemberCreateSerializer(
    TeamMemberWriteMixin, serializers.ModelSerializer
):
    """Create a team member and provision their login account.

    Only ``full_name``, ``email`` and ``password`` are required. The
    account's platform role is limited to ``guide`` or ``internal_admin``
    and its permissions are capped at what the requester already holds.
    """

    full_name = serializers.CharField(max_length=255)
    email = serializers.EmailField()
    password = serializers.CharField(
        write_only=True, style={"input_type": "password"}
    )
    platform_role = serializers.ChoiceField(
        choices=sorted((r.value, r.label) for r in TEAM_MEMBER_ROLES),
        default=Role.GUIDE,
    )
    permissions = serializers.ListField(
        child=serializers.ChoiceField(choices=Capability.choices),
        required=False,
        default=list,
    )
    activity_types = serializers.ListField(
        child=serializers.ChoiceField(choices=ActivityType.choices),
        required=False,
        default=list,
    )
    languages = serializers.ListField(
        child=serializers.ChoiceField(choices=Language.choices),
        required=False,
        default=list,
    )
    certificates = serializers.ListField(
        child=serializers.FileField(), required=False, write_only=True
    )

    class Meta:
        model = TeamMember
        fields = (
            "id",
            "full_name",
            "email",
            "password",
            "platform_role",
            "permissions",
            "activity_types",
            "languages",
            "photo",
            "phone",
            "birth_date",
            "experience_years",
            "bio",
            "certificates",
            "is_active",
        )
        read_only_fields = ("id",)

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                "A user with this email already exists."
            )
        return value

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate_permissions(self, value):
        return self._validate_permissions(value)

    def validate(self, attrs):
        role = attrs.get("platform_role", Role.GUIDE)
        permissions = sorted(set(attrs.get("permissions") or []))
        requires_custom = role in CUSTOM_CAPABILITY_ROLES

        # internal_admin has no default capabilities, so it is unusable
        # without an explicit grant. Every other role (guide) uses its
        # fixed role defaults instead.
        if requires_custom and not permissions:
            raise serializers.ValidationError(
                {
                    "permissions": (
                        "This role requires at least one permission."
                    )
                }
            )
        if not requires_custom and permissions:
            raise serializers.ValidationError(
                {
                    "permissions": (
                        "This role does not accept custom permissions; "
                        "it uses its role defaults."
                    )
                }
            )

        attrs["permissions"] = permissions
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        request = self.context.get("request")
        creator = getattr(request, "user", None)

        full_name = validated_data.pop("full_name")
        email = validated_data.pop("email")
        password = validated_data.pop("password")
        role = validated_data.pop("platform_role", Role.GUIDE)
        certificates = validated_data.pop("certificates", [])
        permissions = validated_data.pop("permissions", [])

        user = User.objects.create_user(
            email=email,
            password=password,
            full_name=full_name,
            role=role,
            custom_capabilities=(
                permissions if role in CUSTOM_CAPABILITY_ROLES else []
            ),
            created_by=(
                creator if creator and creator.is_authenticated else None
            ),
        )

        member = TeamMember.objects.create(
            club=self.context["club"], user=user, **validated_data
        )
        for uploaded in certificates:
            TeamMemberCertificate.objects.create(
                team_member=member, file=uploaded
            )
        return member


class TeamMemberUpdateSerializer(
    TeamMemberWriteMixin, serializers.ModelSerializer
):
    """Update a team member's profile. Password is out of scope here."""

    full_name = serializers.CharField(max_length=255, required=False)
    email = serializers.EmailField(required=False)
    permissions = serializers.ListField(
        child=serializers.ChoiceField(choices=Capability.choices),
        required=False,
    )
    activity_types = serializers.ListField(
        child=serializers.ChoiceField(choices=ActivityType.choices),
        required=False,
    )
    languages = serializers.ListField(
        child=serializers.ChoiceField(choices=Language.choices),
        required=False,
    )
    certificates = serializers.ListField(
        child=serializers.FileField(), required=False, write_only=True
    )

    class Meta:
        model = TeamMember
        fields = (
            "id",
            "full_name",
            "email",
            "permissions",
            "activity_types",
            "languages",
            "photo",
            "phone",
            "birth_date",
            "experience_years",
            "bio",
            "certificates",
            "is_active",
        )
        read_only_fields = ("id",)

    def validate_email(self, value):
        exists = (
            User.objects.filter(email__iexact=value)
            .exclude(pk=self.instance.user_id)
            .exists()
        )
        if exists:
            raise serializers.ValidationError(
                "A user with this email already exists."
            )
        return value

    def validate_permissions(self, value):
        permissions = self._validate_permissions(value)
        role = self.instance.user.role
        if role not in CUSTOM_CAPABILITY_ROLES:
            raise serializers.ValidationError(
                "This role does not accept custom permissions; it uses "
                "its role defaults."
            )
        if not permissions:
            raise serializers.ValidationError(
                "This role requires at least one permission."
            )
        return permissions

    @transaction.atomic
    def update(self, instance, validated_data):
        full_name = validated_data.pop("full_name", None)
        email = validated_data.pop("email", None)
        certificates = validated_data.pop("certificates", [])
        permissions = validated_data.pop("permissions", None)

        user_fields = []
        if full_name is not None:
            instance.user.full_name = full_name
            user_fields.append("full_name")
        if email is not None:
            instance.user.email = email
            user_fields.append("email")

        if permissions is not None:
            instance.user.custom_capabilities = permissions
            user_fields.append("custom_capabilities")

        # "Active" has a single meaning: suspending a membership also
        # suspends the login, exactly like the soft delete does.
        is_active = validated_data.get("is_active")
        if is_active is not None and instance.user.is_active != is_active:
            instance.user.is_active = is_active
            user_fields.append("is_active")

        if user_fields:
            instance.user.save(update_fields=user_fields + ["updated_at"])

        member = super().update(instance, validated_data)
        for uploaded in certificates:
            TeamMemberCertificate.objects.create(
                team_member=member, file=uploaded
            )
        return member
