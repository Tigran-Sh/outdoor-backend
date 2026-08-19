from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.contrib.postgres.fields import ArrayField
from django.db import models

from apps.common.models import UUIDTimeStampedModel
from apps.users.constants import Capability, Role, effective_capabilities
from apps.users.managers import UserManager


class User(UUIDTimeStampedModel, AbstractBaseUser, PermissionsMixin):
    """Custom user authenticated by email.

    ``role`` is the marketplace *business* role and is intentionally
    independent from Django's ``is_staff`` / ``is_superuser`` admin flags.
    """

    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=255, blank=True)

    role = models.CharField(
        max_length=32,
        choices=Role.choices,
        default=Role.PARTICIPANT,
    )

    # Per-user capability assignment. Only meaningful for roles whose
    # capabilities are not fixed (currently INTERNAL_ADMIN).
    custom_capabilities = ArrayField(
        base_field=models.CharField(
            max_length=32, choices=Capability.choices
        ),
        default=list,
        blank=True,
    )

    # Which user (Platform Admin / Club Owner) created this account, if any.
    created_by = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_users",
    )

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(
        default=False,
        help_text="Designates access to the Django admin site.",
    )

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.email

    @property
    def capabilities(self):
        """Effective capability values granted to this user.

        Role defaults combined with any per-user assigned capabilities.
        """
        return effective_capabilities(self.role, self.custom_capabilities)
