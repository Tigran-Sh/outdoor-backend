"""Shared file-upload validators.

Django validates that an ``ImageField`` contains a decodable image, but
nothing caps its size or restricts the format. These validators are the
project-wide limits; use them on every user-supplied file field.
"""

from django.core.exceptions import ValidationError

MAX_UPLOAD_SIZE_MB = 5
MAX_UPLOAD_SIZE = MAX_UPLOAD_SIZE_MB * 1024 * 1024

IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp"})
DOCUMENT_EXTENSIONS = IMAGE_EXTENSIONS | {".pdf"}


def _extension(name):
    _, _, ext = str(name).rpartition(".")
    return f".{ext.lower()}" if ext else ""


def _validate(value, allowed):
    if value.size > MAX_UPLOAD_SIZE:
        raise ValidationError(
            f"File is too large (max {MAX_UPLOAD_SIZE_MB} MB)."
        )
    extension = _extension(value.name)
    if extension not in allowed:
        raise ValidationError(
            "Unsupported file type. Allowed: "
            + ", ".join(sorted(allowed))
            + "."
        )


def validate_image_upload(value):
    """Cap size and restrict to the formats browsers render reliably."""
    _validate(value, IMAGE_EXTENSIONS)


def validate_document_upload(value):
    """As above, but scans are commonly submitted as PDF."""
    _validate(value, DOCUMENT_EXTENSIONS)
