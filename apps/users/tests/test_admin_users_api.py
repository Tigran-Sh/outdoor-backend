from django.contrib.auth import get_user_model

from apps.users.constants import Role
from apps.users.tests.base import (
    DEFAULT_PASSWORD,
    BaseAPITestCase,
    make_platform_admin,
    make_user,
)

User = get_user_model()

USERS_URL = "/api/v1/admin/users/"


def detail_url(user_id):
    return f"{USERS_URL}{user_id}/"


class AdminUsersPermissionTests(BaseAPITestCase):
    def setUp(self):
        self.admin = make_platform_admin()

    def test_unauthenticated_denied(self):
        self.assertEqual(self.client.get(USERS_URL).status_code, 401)

    def test_only_platform_admin_may_list(self):
        for role in [
            Role.PARTICIPANT,
            Role.CLUB_OWNER,
            Role.GUIDE,
            Role.INTERNAL_ADMIN,
        ]:
            user = make_user(f"{role}@example.com", role=role)
            self.auth(user)
            self.assertEqual(
                self.client.get(USERS_URL).status_code, 403, role
            )

        self.auth(self.admin)
        self.assertEqual(self.client.get(USERS_URL).status_code, 200)


class AdminUsersCrudTests(BaseAPITestCase):
    def setUp(self):
        self.admin = make_platform_admin()
        self.auth(self.admin)

    def test_create_user_hashes_password(self):
        res = self.client.post(
            USERS_URL,
            {
                "email": "new@example.com",
                "full_name": "New User",
                "role": Role.GUIDE.value,
                "password": DEFAULT_PASSWORD,
            },
            format="json",
        )
        self.assertEqual(res.status_code, 201)
        user = User.objects.get(email="new@example.com")
        self.assertNotEqual(user.password, DEFAULT_PASSWORD)
        self.assertTrue(user.check_password(DEFAULT_PASSWORD))

    def test_create_rejects_invalid_role(self):
        res = self.client.post(
            USERS_URL,
            {
                "email": "bad@example.com",
                "full_name": "Bad",
                "role": "wizard",
                "password": DEFAULT_PASSWORD,
            },
            format="json",
        )
        self.assertEqual(res.status_code, 400)

    def test_generic_update_cannot_change_role(self):
        target = make_user("t@example.com", role=Role.GUIDE)
        res = self.client.patch(
            detail_url(target.id),
            {"full_name": "Renamed", "role": Role.PLATFORM_ADMIN.value},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        target.refresh_from_db()
        self.assertEqual(target.role, Role.GUIDE.value)
        self.assertEqual(target.full_name, "Renamed")

    def test_generic_update_cannot_escalate_staff_flags(self):
        target = make_user("t2@example.com", role=Role.GUIDE)
        self.client.patch(
            detail_url(target.id),
            {"is_staff": True, "is_superuser": True},
            format="json",
        )
        target.refresh_from_db()
        self.assertFalse(target.is_staff)
        self.assertFalse(target.is_superuser)

    def test_retrieve_excludes_password(self):
        target = make_user("t3@example.com", role=Role.GUIDE)
        res = self.client.get(detail_url(target.id))
        self.assertEqual(res.status_code, 200)
        self.assertNotIn("password", res.json())


class RoleChangeTests(BaseAPITestCase):
    def setUp(self):
        self.admin = make_platform_admin()
        self.auth(self.admin)
        self.target = make_user("rc@example.com", role=Role.GUIDE)

    def test_role_change_endpoint(self):
        res = self.client.patch(
            f"{detail_url(self.target.id)}role/",
            {"role": Role.CLUB_OWNER.value},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.target.refresh_from_db()
        self.assertEqual(self.target.role, Role.CLUB_OWNER.value)

    def test_role_change_invalid(self):
        res = self.client.patch(
            f"{detail_url(self.target.id)}role/",
            {"role": "wizard"},
            format="json",
        )
        self.assertEqual(res.status_code, 400)


class ActivateDeactivateTests(BaseAPITestCase):
    def setUp(self):
        self.admin = make_platform_admin()
        self.auth(self.admin)
        self.target = make_user("ad@example.com", role=Role.GUIDE)

    def test_deactivate_then_activate(self):
        res = self.client.post(f"{detail_url(self.target.id)}deactivate/")
        self.assertEqual(res.status_code, 200)
        self.target.refresh_from_db()
        self.assertFalse(self.target.is_active)

        res = self.client.post(f"{detail_url(self.target.id)}activate/")
        self.assertEqual(res.status_code, 200)
        self.target.refresh_from_db()
        self.assertTrue(self.target.is_active)

    def test_deactivated_user_cannot_login(self):
        self.client.post(f"{detail_url(self.target.id)}deactivate/")
        self.logout()
        res = self.client.post(
            "/api/v1/auth/login/",
            {"email": "ad@example.com", "password": DEFAULT_PASSWORD},
            format="json",
        )
        self.assertEqual(res.status_code, 400)


class FilterSearchTests(BaseAPITestCase):
    def setUp(self):
        self.admin = make_platform_admin()
        self.auth(self.admin)
        make_user("alice@example.com", role=Role.GUIDE, full_name="Alice A")
        make_user("bob@example.com", role=Role.CLUB_OWNER, full_name="Bob B")
        inactive = make_user("carol@example.com", role=Role.GUIDE)
        inactive.is_active = False
        inactive.save(update_fields=["is_active"])

    def _emails(self, res):
        return {row["email"] for row in res.json()["results"]}

    def test_filter_by_role(self):
        res = self.client.get(USERS_URL, {"role": Role.CLUB_OWNER.value})
        self.assertEqual(self._emails(res), {"bob@example.com"})

    def test_filter_by_is_active(self):
        res = self.client.get(USERS_URL, {"is_active": "false"})
        self.assertEqual(self._emails(res), {"carol@example.com"})

    def test_search_by_full_name(self):
        res = self.client.get(USERS_URL, {"search": "Alice"})
        self.assertEqual(self._emails(res), {"alice@example.com"})
