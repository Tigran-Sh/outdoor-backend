from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.users.constants import Role

User = get_user_model()

DEFAULT_PASSWORD = "StrongPass123!"


def make_user(email, role=Role.PARTICIPANT, password=DEFAULT_PASSWORD, **extra):
    """Create a user with sensible test defaults."""
    extra.setdefault("full_name", email.split("@")[0].title())
    return User.objects.create_user(
        email=email, password=password, role=role, **extra
    )


def make_platform_admin(email="admin@example.com", **extra):
    return User.objects.create_superuser(
        email=email,
        full_name=extra.pop("full_name", "Platform Admin"),
        password=extra.pop("password", DEFAULT_PASSWORD),
        **extra,
    )


class BaseAPITestCase(APITestCase):
    """APITestCase with a small authentication helper."""

    def auth(self, user):
        self.client.force_authenticate(user=user)
        return user

    def logout(self):
        self.client.force_authenticate(user=None)
