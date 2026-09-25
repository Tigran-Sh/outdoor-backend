from django.contrib.auth import get_user_model

from apps.clubs.models import TeamMember
from apps.clubs.tests.base import make_club, make_member
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


class UserClubsTests(BaseAPITestCase):
    """The admin user list/detail shows where a person belongs."""

    def setUp(self):
        self.admin = make_platform_admin()
        self.club, self.owner = make_club("owner@example.com", name="Peaks")
        self.guide = make_member(self.club, "guide@example.com")
        self.auth(self.admin)

    def clubs_of(self, user):
        res = self.client.get(detail_url(user.id))
        self.assertEqual(res.status_code, 200, res.json())
        return res.json()["clubs"]

    def test_owner_is_reported_as_owner(self):
        self.assertEqual(
            self.clubs_of(self.owner),
            [
                {
                    "id": str(self.club.id),
                    "name": "Peaks",
                    "relation": "owner",
                    "is_active": True,
                }
            ],
        )

    def test_team_member_is_reported_as_member(self):
        self.assertEqual(
            self.clubs_of(self.guide.user),
            [
                {
                    "id": str(self.club.id),
                    "name": "Peaks",
                    "relation": "team_member",
                    "is_active": True,
                }
            ],
        )

    def test_suspended_membership_is_flagged_not_hidden(self):
        self.guide.is_active = False
        self.guide.save(update_fields=["is_active"])

        entry = self.clubs_of(self.guide.user)[0]
        self.assertEqual(entry["relation"], "team_member")
        self.assertFalse(entry["is_active"])

    def test_unattached_user_has_no_clubs(self):
        participant = make_user("nobody@example.com")
        self.assertEqual(self.clubs_of(participant), [])

    def test_clubs_appear_in_the_list_too(self):
        res = self.client.get(USERS_URL)
        rows = {row["email"]: row["clubs"] for row in res.json()["results"]}

        self.assertEqual(rows["owner@example.com"][0]["name"], "Peaks")
        self.assertEqual(
            rows["guide@example.com"][0]["relation"], "team_member"
        )
        self.assertEqual(rows[self.admin.email], [])

    def test_owning_and_guiding_elsewhere_reports_both(self):
        other_club, _ = make_club("other@example.com", name="Valley")
        TeamMember.objects.create(club=other_club, user=self.owner)

        entries = self.clubs_of(self.owner)
        self.assertEqual(
            {(row["name"], row["relation"]) for row in entries},
            {("Peaks", "owner"), ("Valley", "team_member")},
        )

    def test_listing_users_does_not_scale_queries_with_rows(self):
        with self.assertNumQueries(2):
            self.client.get(USERS_URL)

        make_club("owner2@example.com", name="Ridge")
        make_member(self.club, "guide2@example.com")
        with self.assertNumQueries(2):
            self.client.get(USERS_URL)
