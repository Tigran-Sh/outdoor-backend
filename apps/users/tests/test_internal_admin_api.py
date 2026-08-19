from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory

from apps.users.api.serializers import AdminUserCreateSerializer
from apps.users.constants import Capability, Role
from apps.users.tests.base import (
    DEFAULT_PASSWORD,
    BaseAPITestCase,
    make_platform_admin,
    make_user,
)

User = get_user_model()

USERS_URL = "/api/v1/admin/users/"


def caps_url(user_id):
    return f"{USERS_URL}{user_id}/capabilities/"


def role_url(user_id):
    return f"{USERS_URL}{user_id}/role/"


class InternalAdminCreateTests(BaseAPITestCase):
    def setUp(self):
        self.admin = make_platform_admin()
        self.auth(self.admin)

    def _payload(self, **overrides):
        data = {
            "email": "ia@example.com",
            "full_name": "Internal Admin",
            "role": Role.INTERNAL_ADMIN.value,
            "password": DEFAULT_PASSWORD,
            "capabilities": [Capability.ISSUE_REFUND.value],
        }
        data.update(overrides)
        return data

    def test_requires_capabilities(self):
        res = self.client.post(
            USERS_URL, self._payload(capabilities=[]), format="json"
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("capabilities", res.json()["error"]["details"])

    def test_success_sets_custom_capabilities_and_creator(self):
        res = self.client.post(USERS_URL, self._payload(), format="json")
        self.assertEqual(res.status_code, 201)
        body = res.json()
        self.assertEqual(
            body["custom_capabilities"], [Capability.ISSUE_REFUND.value]
        )
        self.assertEqual(body["capabilities"], [Capability.ISSUE_REFUND.value])
        self.assertEqual(body["created_by"], self.admin.email)

        created = User.objects.get(email="ia@example.com")
        self.assertEqual(created.created_by, self.admin)

    def test_non_internal_role_rejects_capabilities(self):
        res = self.client.post(
            USERS_URL,
            self._payload(
                email="g@example.com",
                role=Role.GUIDE.value,
                capabilities=[Capability.QR_CHECK_IN.value],
            ),
            format="json",
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("capabilities", res.json()["error"]["details"])


class InternalAdminCapabilitiesEndpointTests(BaseAPITestCase):
    def setUp(self):
        self.admin = make_platform_admin()
        self.auth(self.admin)
        self.internal = make_user(
            "ia2@example.com",
            role=Role.INTERNAL_ADMIN,
            custom_capabilities=[Capability.QR_CHECK_IN.value],
        )

    def test_assign_capabilities(self):
        res = self.client.patch(
            caps_url(self.internal.id),
            {"capabilities": [Capability.VIEW_FINANCES.value]},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.internal.refresh_from_db()
        self.assertEqual(
            self.internal.custom_capabilities, [Capability.VIEW_FINANCES.value]
        )

    def test_empty_capabilities_rejected(self):
        res = self.client.patch(
            caps_url(self.internal.id),
            {"capabilities": []},
            format="json",
        )
        self.assertEqual(res.status_code, 400)

    def test_rejected_for_non_internal_role(self):
        guide = make_user("gg@example.com", role=Role.GUIDE)
        res = self.client.patch(
            caps_url(guide.id),
            {"capabilities": [Capability.QR_CHECK_IN.value]},
            format="json",
        )
        self.assertEqual(res.status_code, 400)


class RoleChangeClearsCapabilitiesTests(BaseAPITestCase):
    def setUp(self):
        self.admin = make_platform_admin()
        self.auth(self.admin)
        self.internal = make_user(
            "ia3@example.com",
            role=Role.INTERNAL_ADMIN,
            custom_capabilities=[Capability.ISSUE_REFUND.value],
        )

    def test_switching_to_fixed_role_clears_custom_capabilities(self):
        res = self.client.patch(
            role_url(self.internal.id),
            {"role": Role.GUIDE.value},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.internal.refresh_from_db()
        self.assertEqual(self.internal.role, Role.GUIDE.value)
        self.assertEqual(self.internal.custom_capabilities, [])


class GrantGuardrailSerializerTests(BaseAPITestCase):
    """The grant guardrail is enforced at the serializer layer.

    The create endpoint itself is Platform-Admin only (who can grant
    everything), so we exercise the guardrail directly with a limited
    grantor to prove privilege escalation is blocked.
    """

    def _serializer_for(self, grantor, capabilities):
        factory = APIRequestFactory()
        request = factory.post(USERS_URL)
        request.user = grantor
        return AdminUserCreateSerializer(
            data={
                "email": "x@example.com",
                "full_name": "X",
                "role": Role.INTERNAL_ADMIN.value,
                "password": DEFAULT_PASSWORD,
                "capabilities": capabilities,
            },
            context={"request": request},
        )

    def test_club_owner_cannot_grant_governance_capability(self):
        owner = make_user("owner@example.com", role=Role.CLUB_OWNER)
        serializer = self._serializer_for(
            owner, [Capability.ISSUE_REFUND.value]
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("issue_refund", str(serializer.errors))

    def test_club_owner_can_grant_owned_capability(self):
        owner = make_user("owner2@example.com", role=Role.CLUB_OWNER)
        serializer = self._serializer_for(
            owner, [Capability.QR_CHECK_IN.value]
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
