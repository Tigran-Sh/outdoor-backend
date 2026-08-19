import uuid

from django.db import models


class UUIDTimeStampedModel(models.Model):
    """Abstract base model with a UUID primary key and timestamps.

    Provides:
    - ``id``         : UUID primary key (non-editable).
    - ``created_at`` : set once on creation.
    - ``updated_at`` : updated on every save.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
