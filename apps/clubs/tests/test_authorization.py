from django.test import TestCase

from apps.clubs.services import authorization
from apps.clubs.tests.base import make_club, make_member
from apps.users.constants import Capability, Role
from apps.users.tests.base import make_platform_admin, make_user


class ClubScopeTests(TestCase):
    def setUp(self):
        self.club_a, self.owner_a = make_club("a@example.com")
        self.club_b, self.owner_b = make_club("b@example.com")

    def test_owner_resolves_own_club(self):
        self.assertEqual(
            authorization.get_owned_club(self.owner_a), self.club_a
        )

    def test_user_without_club(self):
        user = make_user("none@example.com")
        self.assertIsNone(authorization.get_owned_club(user))

    def test_owner_can_manage_own_club_only(self):
        self.assertTrue(
            authorization.can_manage_team(self.owner_a, self.club_a)
        )
        self.assertFalse(
            authorization.can_manage_team(self.owner_a, self.club_b)
        )

    def test_platform_admin_manages_any_club(self):
        admin = make_platform_admin()
        self.assertTrue(authorization.can_manage_team(admin, self.club_a))
        self.assertTrue(authorization.can_manage_team(admin, self.club_b))

    def test_participant_cannot_manage(self):
        user = make_user("p@example.com", role=Role.PARTICIPANT)
        self.assertFalse(
            authorization.can_manage_team(user, self.club_a)
        )

    def test_plain_guide_cannot_read(self):
        member = make_member(self.club_a, "g@example.com")
        self.assertFalse(
            authorization.can_view_team(member.user, self.club_a)
        )

    def test_reader_confined_to_their_club(self):
        member = make_member(
            self.club_a,
            "reader@example.com",
            role=Role.INTERNAL_ADMIN,
            custom_capabilities=[Capability.VIEW_TEAM_MEMBERS.value],
        )
        self.assertTrue(
            authorization.can_view_team(member.user, self.club_a)
        )
        self.assertFalse(
            authorization.can_view_team(member.user, self.club_b)
        )
        self.assertEqual(
            authorization.readable_club_scope(member.user), self.club_a
        )

    def test_platform_level_reader_not_confined(self):
        reader = make_user(
            "platform-reader@example.com",
            role=Role.INTERNAL_ADMIN,
            custom_capabilities=[Capability.VIEW_TEAM_MEMBERS.value],
        )
        self.assertTrue(authorization.can_view_team(reader, self.club_a))
        self.assertTrue(authorization.can_view_team(reader, self.club_b))
        self.assertIs(
            authorization.readable_club_scope(reader),
            authorization.ALL_CLUBS,
        )

    def test_club_owner_without_a_club_has_no_access(self):
        """The role's default capability must not grant cross-club reads."""
        owner = make_user("clubless@example.com", role=Role.CLUB_OWNER)
        self.assertIsNone(authorization.readable_club_scope(owner))
        self.assertFalse(authorization.can_read_any_team(owner))
        self.assertFalse(authorization.can_view_team(owner, self.club_a))
        self.assertFalse(authorization.can_manage_team(owner, self.club_a))

    def test_inactive_membership_is_not_a_scope(self):
        member = make_member(
            self.club_a,
            "inactive@example.com",
            role=Role.INTERNAL_ADMIN,
            custom_capabilities=[Capability.VIEW_TEAM_MEMBERS.value],
            is_active=False,
        )
        self.assertIsNone(
            authorization.get_membership_club(member.user)
        )

    def test_deactivating_a_membership_does_not_widen_access(self):
        """Losing an active membership must never mean "sees every club"."""
        member = make_member(
            self.club_a,
            "suspended@example.com",
            role=Role.INTERNAL_ADMIN,
            custom_capabilities=[Capability.VIEW_TEAM_MEMBERS.value],
            is_active=False,
        )
        self.assertIsNone(authorization.readable_club_scope(member.user))
        self.assertFalse(authorization.can_read_any_team(member.user))
        self.assertFalse(
            authorization.can_view_team(member.user, self.club_b)
        )

    def test_owner_scope_is_their_club(self):
        self.assertEqual(
            authorization.readable_club_scope(self.owner_a), self.club_a
        )
