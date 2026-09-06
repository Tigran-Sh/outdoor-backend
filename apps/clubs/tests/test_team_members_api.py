from django.contrib.auth import get_user_model

from apps.clubs.models import TeamMember
from apps.clubs.tests.base import (
    TEAM_URL,
    ClubAPITestCase,
    detail_url,
    make_club,
    make_member,
)
from apps.users.constants import Capability, Role
from apps.users.tests.base import (
    DEFAULT_PASSWORD,
    make_platform_admin,
    make_user,
)

User = get_user_model()


class TeamMemberCreateTests(ClubAPITestCase):
    def setUp(self):
        self.club, self.owner = make_club("owner@example.com")
        self.auth(self.owner)

    def _payload(self, **overrides):
        data = {
            "full_name": "Elina Ghevondyan",
            "email": "elina@example.com",
            "password": DEFAULT_PASSWORD,
        }
        data.update(overrides)
        return data

    def test_minimal_payload_creates_guide_account(self):
        res = self.client.post(TEAM_URL, self._payload(), format="json")
        self.assertEqual(res.status_code, 201, res.json())

        user = User.objects.get(email="elina@example.com")
        self.assertEqual(user.role, Role.GUIDE.value)
        self.assertEqual(user.full_name, "Elina Ghevondyan")
        self.assertTrue(user.check_password(DEFAULT_PASSWORD))
        self.assertEqual(user.created_by, self.owner)

        member = TeamMember.objects.get(user=user)
        self.assertEqual(member.club, self.club)

    def test_password_never_returned(self):
        res = self.client.post(TEAM_URL, self._payload(), format="json")
        self.assertNotIn("password", res.json())

    def test_email_must_be_unique(self):
        make_user("taken@example.com")
        res = self.client.post(
            TEAM_URL, self._payload(email="taken@example.com"), format="json"
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("email", res.json()["error"]["details"])

    def test_missing_required_fields(self):
        res = self.client.post(
            TEAM_URL, {"full_name": "No Email"}, format="json"
        )
        self.assertEqual(res.status_code, 400)
        details = res.json()["error"]["details"]
        self.assertIn("email", details)
        self.assertIn("password", details)

    def test_weak_password_rejected(self):
        res = self.client.post(
            TEAM_URL, self._payload(password="123"), format="json"
        )
        self.assertEqual(res.status_code, 400)

    def test_optional_profile_fields_saved(self):
        res = self.client.post(
            TEAM_URL,
            self._payload(
                activity_types=["hiking", "climbing"],
                languages=["en", "hy"],
                phone="+37400000000",
                experience_years=5,
                bio="Experienced mountain guide.",
            ),
            format="json",
        )
        self.assertEqual(res.status_code, 201, res.json())
        member = TeamMember.objects.get(user__email="elina@example.com")
        self.assertEqual(member.activity_types, ["hiking", "climbing"])
        self.assertEqual(member.languages, ["en", "hy"])
        self.assertEqual(member.experience_years, 5)

    def test_created_member_can_log_in(self):
        self.client.post(TEAM_URL, self._payload(), format="json")
        self.logout()
        res = self.client.post(
            "/api/v1/auth/login/",
            {"email": "elina@example.com", "password": DEFAULT_PASSWORD},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["user"]["role"], Role.GUIDE.value)


class TeamMemberRoleAndPermissionTests(ClubAPITestCase):
    def setUp(self):
        self.club, self.owner = make_club("owner2@example.com")
        self.auth(self.owner)

    def _payload(self, **overrides):
        data = {
            "full_name": "Staff Member",
            "email": "staff@example.com",
            "password": DEFAULT_PASSWORD,
        }
        data.update(overrides)
        return data

    def test_guide_gets_role_defaults_including_gps_and_emergency(self):
        res = self.client.post(TEAM_URL, self._payload(), format="json")
        permissions = res.json()["permissions"]
        self.assertIn(Capability.QR_CHECK_IN.value, permissions)
        self.assertIn(Capability.GPS_TRACKING.value, permissions)
        self.assertIn(Capability.EMERGENCY_BUTTON.value, permissions)

    def test_guide_rejects_custom_permissions(self):
        res = self.client.post(
            TEAM_URL,
            self._payload(permissions=[Capability.QR_CHECK_IN.value]),
            format="json",
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("permissions", res.json()["error"]["details"])

    def test_internal_admin_requires_permissions(self):
        res = self.client.post(
            TEAM_URL,
            self._payload(platform_role=Role.INTERNAL_ADMIN.value),
            format="json",
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("permissions", res.json()["error"]["details"])

    def test_internal_admin_with_permissions(self):
        res = self.client.post(
            TEAM_URL,
            self._payload(
                platform_role=Role.INTERNAL_ADMIN.value,
                permissions=[
                    Capability.VIEW_FINANCES.value,
                    Capability.VIEW_TEAM_MEMBERS.value,
                ],
            ),
            format="json",
        )
        self.assertEqual(res.status_code, 201, res.json())
        user = User.objects.get(email="staff@example.com")
        self.assertEqual(user.role, Role.INTERNAL_ADMIN.value)
        self.assertEqual(
            sorted(user.custom_capabilities),
            [
                Capability.VIEW_FINANCES.value,
                Capability.VIEW_TEAM_MEMBERS.value,
            ],
        )

    def test_cannot_grant_permission_owner_lacks(self):
        res = self.client.post(
            TEAM_URL,
            self._payload(
                platform_role=Role.INTERNAL_ADMIN.value,
                permissions=[Capability.ISSUE_REFUND.value],
            ),
            format="json",
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("issue_refund", str(res.json()))

    def test_cannot_create_platform_admin(self):
        res = self.client.post(
            TEAM_URL,
            self._payload(platform_role=Role.PLATFORM_ADMIN.value),
            format="json",
        )
        self.assertEqual(res.status_code, 400)

    def test_cannot_create_club_owner(self):
        res = self.client.post(
            TEAM_URL,
            self._payload(platform_role=Role.CLUB_OWNER.value),
            format="json",
        )
        self.assertEqual(res.status_code, 400)


class TeamMemberScopingTests(ClubAPITestCase):
    def setUp(self):
        self.club_a, self.owner_a = make_club("a@example.com", name="Club A")
        self.club_b, self.owner_b = make_club("b@example.com", name="Club B")
        self.member_a = make_member(self.club_a, "guide-a@example.com")
        self.member_b = make_member(self.club_b, "guide-b@example.com")

    def test_owner_sees_only_own_team(self):
        self.auth(self.owner_a)
        res = self.client.get(TEAM_URL)
        self.assertEqual(res.status_code, 200)
        emails = {row["email"] for row in res.json()["results"]}
        self.assertEqual(emails, {"guide-a@example.com"})

    def test_owner_cannot_retrieve_other_club_member(self):
        self.auth(self.owner_a)
        res = self.client.get(detail_url(self.member_b.id))
        self.assertEqual(res.status_code, 404)

    def test_club_created_internal_admin_is_confined_to_that_club(self):
        internal = make_member(
            self.club_a,
            "ia-a@example.com",
            role=Role.INTERNAL_ADMIN,
            custom_capabilities=[Capability.VIEW_TEAM_MEMBERS.value],
        )
        self.auth(internal.user)

        res = self.client.get(TEAM_URL)
        self.assertEqual(res.status_code, 200)
        emails = {row["email"] for row in res.json()["results"]}
        self.assertEqual(emails, {"guide-a@example.com", "ia-a@example.com"})

        self.assertEqual(
            self.client.get(detail_url(self.member_b.id)).status_code, 404
        )

    def test_owner_cannot_update_other_club_member(self):
        self.auth(self.owner_a)
        res = self.client.patch(
            detail_url(self.member_b.id),
            {"phone": "+37411111111"},
            format="json",
        )
        self.assertEqual(res.status_code, 404)

    def test_owner_cannot_delete_other_club_member(self):
        self.auth(self.owner_a)
        res = self.client.delete(detail_url(self.member_b.id))
        self.assertEqual(res.status_code, 404)

    def test_platform_admin_sees_all_and_can_filter(self):
        self.auth(make_platform_admin())
        res = self.client.get(TEAM_URL)
        self.assertEqual(len(res.json()["results"]), 2)

        res = self.client.get(TEAM_URL, {"club": str(self.club_b.id)})
        emails = {row["email"] for row in res.json()["results"]}
        self.assertEqual(emails, {"guide-b@example.com"})


class TeamMemberAccessControlTests(ClubAPITestCase):
    def setUp(self):
        self.club, self.owner = make_club("owner3@example.com")
        self.member = make_member(self.club, "guide3@example.com")

    def test_unauthenticated_denied(self):
        self.assertEqual(self.client.get(TEAM_URL).status_code, 401)

    def test_participant_denied(self):
        self.auth(make_user("p@example.com", role=Role.PARTICIPANT))
        self.assertEqual(self.client.get(TEAM_URL).status_code, 403)

    def test_plain_guide_denied(self):
        self.auth(self.member.user)
        self.assertEqual(self.client.get(TEAM_URL).status_code, 403)

    def test_internal_admin_without_capability_denied(self):
        self.auth(make_user("ia@example.com", role=Role.INTERNAL_ADMIN))
        self.assertEqual(self.client.get(TEAM_URL).status_code, 403)

    def test_club_owner_without_a_club_cannot_read_or_create(self):
        self.auth(make_user("clubless@example.com", role=Role.CLUB_OWNER))
        self.assertEqual(self.client.get(TEAM_URL).status_code, 403)
        res = self.client.post(
            TEAM_URL,
            {
                "full_name": "X",
                "email": "x@example.com",
                "password": DEFAULT_PASSWORD,
            },
            format="json",
        )
        self.assertEqual(res.status_code, 403)


class InternalAdminReadOnlyTests(ClubAPITestCase):
    """An internal admin granted view_team_members may read, never write."""

    def setUp(self):
        self.club, self.owner = make_club("owner4@example.com")
        self.member = make_member(self.club, "guide4@example.com")
        self.reader = make_user(
            "reader@example.com",
            role=Role.INTERNAL_ADMIN,
            custom_capabilities=[Capability.VIEW_TEAM_MEMBERS.value],
        )
        self.auth(self.reader)

    def test_can_list(self):
        res = self.client.get(TEAM_URL)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json()["results"]), 1)

    def test_can_retrieve(self):
        res = self.client.get(detail_url(self.member.id))
        self.assertEqual(res.status_code, 200)

    def test_cannot_create(self):
        res = self.client.post(
            TEAM_URL,
            {
                "full_name": "X",
                "email": "x@example.com",
                "password": DEFAULT_PASSWORD,
            },
            format="json",
        )
        self.assertEqual(res.status_code, 403)

    def test_cannot_update(self):
        res = self.client.patch(
            detail_url(self.member.id), {"phone": "+3741"}, format="json"
        )
        self.assertEqual(res.status_code, 403)

    def test_cannot_delete(self):
        res = self.client.delete(detail_url(self.member.id))
        self.assertEqual(res.status_code, 403)

    def test_club_scoped_reader_cannot_see_other_clubs(self):
        other_club, _ = make_club("owner5@example.com", name="Other")
        make_member(other_club, "guide5@example.com")
        # Tie the reader to a club: they are now confined to it.
        make_member(
            self.club,
            "reader2@example.com",
            role=Role.INTERNAL_ADMIN,
            custom_capabilities=[Capability.VIEW_TEAM_MEMBERS.value],
        )
        self.auth(User.objects.get(email="reader2@example.com"))
        res = self.client.get(TEAM_URL)
        emails = {row["email"] for row in res.json()["results"]}
        self.assertNotIn("guide5@example.com", emails)


class TeamMemberUpdateDeleteTests(ClubAPITestCase):
    def setUp(self):
        self.club, self.owner = make_club("owner6@example.com")
        self.member = make_member(self.club, "guide6@example.com")
        self.internal = make_member(
            self.club,
            "ia6@example.com",
            role=Role.INTERNAL_ADMIN,
            custom_capabilities=[Capability.VIEW_TEAM_MEMBERS.value],
        )
        self.auth(self.owner)

    def test_update_profile_fields(self):
        res = self.client.patch(
            detail_url(self.member.id),
            {"phone": "+37400000001", "bio": "Updated"},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.member.refresh_from_db()
        self.assertEqual(self.member.phone, "+37400000001")

    def test_update_full_name_syncs_to_account(self):
        res = self.client.patch(
            detail_url(self.member.id),
            {"full_name": "New Name"},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.member.user.refresh_from_db()
        self.assertEqual(self.member.user.full_name, "New Name")

    def test_update_rejects_duplicate_email(self):
        make_user("dupe@example.com")
        res = self.client.patch(
            detail_url(self.member.id),
            {"email": "dupe@example.com"},
            format="json",
        )
        self.assertEqual(res.status_code, 400)

    def test_update_guide_permissions_rejected(self):
        res = self.client.patch(
            detail_url(self.member.id),
            {"permissions": [Capability.VIEW_FINANCES.value]},
            format="json",
        )
        self.assertEqual(res.status_code, 400)

    def test_update_internal_admin_permissions(self):
        res = self.client.patch(
            detail_url(self.internal.id),
            {"permissions": [Capability.VIEW_FINANCES.value]},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.internal.user.refresh_from_db()
        self.assertEqual(
            self.internal.user.custom_capabilities,
            [Capability.VIEW_FINANCES.value],
        )

    def test_update_cannot_grant_ungrantable_permission(self):
        res = self.client.patch(
            detail_url(self.internal.id),
            {"permissions": [Capability.ISSUE_REFUND.value]},
            format="json",
        )
        self.assertEqual(res.status_code, 400)

    def test_suspending_a_membership_disables_the_account(self):
        res = self.client.patch(
            detail_url(self.member.id),
            {"is_active": False},
            format="json",
        )
        self.assertEqual(res.status_code, 200)

        self.member.user.refresh_from_db()
        self.assertFalse(self.member.user.is_active)

    def test_reactivating_a_membership_restores_the_account(self):
        self.client.delete(detail_url(self.member.id))
        res = self.client.patch(
            detail_url(self.member.id),
            {"is_active": True},
            format="json",
        )
        self.assertEqual(res.status_code, 200)

        self.member.refresh_from_db()
        self.member.user.refresh_from_db()
        self.assertTrue(self.member.is_active)
        self.assertTrue(self.member.user.is_active)

    def test_suspended_internal_admin_loses_read_access(self):
        make_club("owner7@example.com", name="Other Club")

        res = self.client.patch(
            detail_url(self.internal.id),
            {"is_active": False},
            format="json",
        )
        self.assertEqual(res.status_code, 200)

        self.internal.user.refresh_from_db()
        self.auth(self.internal.user)
        self.assertEqual(self.client.get(TEAM_URL).status_code, 403)

    def test_delete_is_soft(self):
        res = self.client.delete(detail_url(self.member.id))
        self.assertEqual(res.status_code, 204)

        self.member.refresh_from_db()
        self.member.user.refresh_from_db()
        self.assertFalse(self.member.is_active)
        self.assertFalse(self.member.user.is_active)
        self.assertTrue(
            TeamMember.objects.filter(pk=self.member.pk).exists()
        )

    def test_deleted_member_cannot_log_in(self):
        self.client.delete(detail_url(self.member.id))
        self.logout()
        res = self.client.post(
            "/api/v1/auth/login/",
            {
                "email": "guide6@example.com",
                "password": DEFAULT_PASSWORD,
            },
            format="json",
        )
        self.assertEqual(res.status_code, 400)
