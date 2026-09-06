from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models

from apps.clubs.constants import (
    ID_DOCUMENT_ENTITY_TYPES,
    REQUIRED_PROFILE_FIELDS,
    SOCIAL_FIELDS,
    TAX_ID_ENTITY_TYPES,
    ClubStatus,
    EntityType,
)
from apps.common.constants import ActivityType, Language, Region
from apps.common.models import UUIDTimeStampedModel
from apps.common.storage import private_media_storage
from apps.common.validators import (
    validate_document_upload,
    validate_image_upload,
)


class Club(UUIDTimeStampedModel):
    """A club on the marketplace.

    A user may own at most one club (``owner`` is one-to-one), which is
    what lets team endpoints resolve "my club" from the request user.
    """

    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="club",
    )
    name = models.CharField(max_length=255)
    status = models.CharField(
        max_length=32,
        choices=ClubStatus.choices,
        default=ClubStatus.DRAFT,
    )

    # Profile. A Platform Admin creates the club with little more than a
    # name, so everything below starts empty and the owner fills it in.
    logo = models.ImageField(
        upload_to="clubs/logos/",
        null=True,
        blank=True,
        validators=[validate_image_upload],
    )
    cover_image = models.ImageField(
        upload_to="clubs/covers/",
        null=True,
        blank=True,
        validators=[validate_image_upload],
    )
    about = models.TextField(blank=True)
    activity_types = ArrayField(
        base_field=models.CharField(
            max_length=32, choices=ActivityType.choices
        ),
        default=list,
        blank=True,
    )
    base_region = models.CharField(
        max_length=32,
        choices=Region.choices,
        blank=True,
    )
    year_founded = models.PositiveIntegerField(null=True, blank=True)

    # Contact. Distinct from the owner's account email.
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=32, blank=True)
    instagram = models.CharField(max_length=255, blank=True)
    facebook = models.CharField(max_length=255, blank=True)
    telegram = models.CharField(max_length=255, blank=True)
    website = models.URLField(blank=True)

    # Legal. Which of tax_id / owner_id_document applies depends on
    # entity_type; see apps.clubs.constants.
    entity_type = models.CharField(
        max_length=32,
        choices=EntityType.choices,
        blank=True,
    )
    tax_id = models.CharField(max_length=64, blank=True)
    owner_id_document = models.FileField(
        upload_to="clubs/id_documents/",
        storage=private_media_storage,
        null=True,
        blank=True,
        validators=[validate_document_upload],
    )

    # Set by staff after checking the documents, never by the owner.
    identity_verified = models.BooleanField(default=False)
    payment_verified = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    def missing_profile_fields(self):
        """Required fields still empty, in form order.

        Nothing enforces completeness yet because clubs are created
        approved by a Platform Admin. This drives a progress indicator
        now and becomes the gate for "submit for review" once clubs can
        register themselves.
        """
        missing = [
            field
            for field in REQUIRED_PROFILE_FIELDS
            if not getattr(self, field)
        ]
        if not self.entity_type:
            missing.append("entity_type")
        elif self.entity_type in TAX_ID_ENTITY_TYPES and not self.tax_id:
            missing.append("tax_id")
        elif (
            self.entity_type in ID_DOCUMENT_ENTITY_TYPES
            and not self.owner_id_document
        ):
            missing.append("owner_id_document")
        if not any(getattr(self, field) for field in SOCIAL_FIELDS):
            missing.append("social_links")
        return missing


class TeamMember(UUIDTimeStampedModel):
    """A club staff member (guide, manager, ...).

    Identity, platform role and capabilities live on the linked ``User``;
    everything here is club profile data. Capabilities are never stored
    twice: a guide uses its role defaults and an internal admin uses
    ``User.custom_capabilities``. Club confinement is enforced by the
    membership checks in ``apps.clubs.services.authorization``.
    """

    club = models.ForeignKey(
        Club,
        on_delete=models.CASCADE,
        related_name="team_members",
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="team_membership",
    )

    activity_types = ArrayField(
        base_field=models.CharField(
            max_length=32, choices=ActivityType.choices
        ),
        default=list,
        blank=True,
    )
    languages = ArrayField(
        base_field=models.CharField(
            max_length=8, choices=Language.choices
        ),
        default=list,
        blank=True,
    )

    photo = models.ImageField(
        upload_to="team_members/photos/",
        null=True,
        blank=True,
        validators=[validate_image_upload],
    )
    phone = models.CharField(max_length=32, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    experience_years = models.PositiveIntegerField(null=True, blank=True)
    bio = models.TextField(blank=True)

    # Membership status. Independent from ``user.is_active`` (account).
    is_active = models.BooleanField(default=True)
    joined_date = models.DateField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.email} @ {self.club.name}"


class TeamMemberCertificate(UUIDTimeStampedModel):
    """An uploaded certificate belonging to a team member."""

    team_member = models.ForeignKey(
        TeamMember,
        on_delete=models.CASCADE,
        related_name="certificates",
    )
    file = models.FileField(
        upload_to="team_members/certificates/",
        validators=[validate_document_upload],
    )

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return self.file.name
