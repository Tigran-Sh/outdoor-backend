import tempfile
from io import BytesIO
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image

from apps.clubs.constants import ClubStatus
from apps.clubs.models import Club, TeamMember
from apps.users.constants import Role
from apps.users.tests.base import BaseAPITestCase, make_user

TEAM_URL = "/api/v1/club/team-members/"
MY_CLUB_URL = "/api/v1/club/"
ADMIN_CLUBS_URL = "/api/v1/admin/clubs/"
AVAILABLE_OWNERS_URL = f"{ADMIN_CLUBS_URL}available-owners/"


def detail_url(member_id):
    return f"{TEAM_URL}{member_id}/"


def id_document_url(club_id):
    return f"{MY_CLUB_URL}{club_id}/id-document/"


def upload(name="scan.png", content=b"fake-bytes", content_type=None):
    """An in-memory file for plain FileField uploads."""
    return SimpleUploadedFile(
        name, content, content_type=content_type or "image/png"
    )


def image_upload(name="logo.png", size=(1, 1)):
    """A real (tiny) PNG, since ImageField decodes what it is given."""
    buffer = BytesIO()
    Image.new("RGB", size, color="red").save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), "image/png")


def make_club(owner_email, name="Test Club", **extra):
    """Create a club together with its club-owner account."""
    owner = make_user(owner_email, role=Role.CLUB_OWNER)
    club = Club.objects.create(
        owner=owner,
        name=name,
        status=extra.pop("status", ClubStatus.APPROVED),
    )
    return club, owner


def make_member(club, email, role=Role.GUIDE, **extra):
    """Create a team member (account + membership) directly."""
    user = make_user(
        email,
        role=role,
        custom_capabilities=extra.pop("custom_capabilities", []),
    )
    return TeamMember.objects.create(club=club, user=user, **extra)


class ClubAPITestCase(BaseAPITestCase):
    """Club API tests, with uploads redirected to a temp directory.

    Otherwise every run that touches a file field would litter the real
    MEDIA_ROOT (and, worse, the private document tree).
    """

    @classmethod
    def setUpClass(cls):
        cls._media_dir = tempfile.TemporaryDirectory()
        root = Path(cls._media_dir.name)
        cls._media_override = override_settings(
            MEDIA_ROOT=root / "media",
            PRIVATE_MEDIA_ROOT=root / "private",
        )
        cls._media_override.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._media_override.disable()
        cls._media_dir.cleanup()
