from apps.users.constants import Capability, Role
from apps.users.tests.base import (
    BaseAPITestCase,
    make_platform_admin,
    make_user,
)

ROLES_URL = "/api/v1/admin/roles/"
CAPABILITIES_URL = "/api/v1/admin/capabilities/"


class RolesReadPermissionTests(BaseAPITestCase):
    def setUp(self):
        self.admin = make_platform_admin()

    def test_requires_authentication(self):
        self.assertEqual(self.client.get(ROLES_URL).status_code, 401)

    def test_forbidden_for_non_platform_admin(self):
        for role in [Role.GUIDE, Role.CLUB_OWNER, Role.INTERNAL_ADMIN]:
            self.auth(make_user(f"{role}@example.com", role=role))
            self.assertEqual(
                self.client.get(ROLES_URL).status_code, 403, role
            )


class RolesReadContentTests(BaseAPITestCase):
    def setUp(self):
        self.auth(make_platform_admin())

    def test_roles_list_contains_all_roles(self):
        res = self.client.get(ROLES_URL)
        self.assertEqual(res.status_code, 200)
        keys = {row["key"] for row in res.json()}
        self.assertEqual(keys, set(Role.values))

    def test_role_detail(self):
        res = self.client.get(f"{ROLES_URL}{Role.GUIDE.value}/")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["key"], Role.GUIDE.value)
        self.assertIn(Capability.QR_CHECK_IN.value, body["capabilities"])

    def test_internal_admin_detail_has_no_default_capabilities(self):
        res = self.client.get(f"{ROLES_URL}{Role.INTERNAL_ADMIN.value}/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["capabilities"], [])

    def test_role_detail_unknown_returns_404(self):
        res = self.client.get(f"{ROLES_URL}wizard/")
        self.assertEqual(res.status_code, 404)

    def test_role_capabilities_endpoint(self):
        res = self.client.get(
            f"{ROLES_URL}{Role.GUIDE.value}/capabilities/"
        )
        self.assertEqual(res.status_code, 200)
        keys = {row["key"] for row in res.json()}
        self.assertIn(Capability.QR_CHECK_IN.value, keys)

    def test_capabilities_list(self):
        res = self.client.get(CAPABILITIES_URL)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json()), len(Capability.values))
