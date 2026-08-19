from django.contrib.auth.models import AnonymousUser
from django.test import TestCase

from apps.users.constants import (
    ALL_CAPABILITIES,
    ROLE_CAPABILITIES,
    Capability,
    Role,
    effective_capabilities,
)
from apps.users.services import authorization
from apps.users.services.catalog import CapabilityCatalog, RoleCatalog
from apps.users.tests.base import make_user


class EffectiveCapabilitiesTests(TestCase):
    def test_participant_has_no_capabilities(self):
        self.assertEqual(effective_capabilities(Role.PARTICIPANT), frozenset())

    def test_guide_defaults(self):
        self.assertEqual(
            effective_capabilities(Role.GUIDE),
            {
                Capability.VIEW_PARTICIPANTS.value,
                Capability.EXPORT_PARTICIPANTS.value,
                Capability.QR_CHECK_IN.value,
                Capability.CONFIRM_COMPLETION.value,
            },
        )

    def test_platform_admin_has_all(self):
        self.assertEqual(
            effective_capabilities(Role.PLATFORM_ADMIN),
            {c.value for c in ALL_CAPABILITIES},
        )

    def test_internal_admin_defaults_empty(self):
        self.assertEqual(
            effective_capabilities(Role.INTERNAL_ADMIN), frozenset()
        )

    def test_internal_admin_uses_custom(self):
        caps = [Capability.QR_CHECK_IN.value, Capability.VIEW_FINANCES.value]
        self.assertEqual(
            effective_capabilities(Role.INTERNAL_ADMIN, caps), set(caps)
        )

    def test_custom_is_additive_to_role_defaults(self):
        result = effective_capabilities(
            Role.GUIDE, [Capability.VIEW_FINANCES.value]
        )
        self.assertIn(Capability.VIEW_FINANCES.value, result)
        self.assertIn(Capability.QR_CHECK_IN.value, result)

    def test_invalid_custom_values_ignored(self):
        result = effective_capabilities(Role.INTERNAL_ADMIN, ["nonsense"])
        self.assertEqual(result, frozenset())


class RoleHelpersTests(TestCase):
    def test_has_role(self):
        owner = make_user("o@example.com", role=Role.CLUB_OWNER)
        self.assertTrue(authorization.has_role(owner, Role.CLUB_OWNER))
        self.assertFalse(authorization.has_role(owner, Role.GUIDE))

    def test_has_any_role(self):
        guide = make_user("g@example.com", role=Role.GUIDE)
        self.assertTrue(
            authorization.has_any_role(guide, {Role.GUIDE, Role.CLUB_OWNER})
        )

    def test_anonymous_and_inactive_denied(self):
        self.assertFalse(authorization.has_role(AnonymousUser(), Role.GUIDE))
        self.assertFalse(authorization.has_role(None, Role.GUIDE))
        inactive = make_user(
            "i@example.com", role=Role.PLATFORM_ADMIN, is_active=False
        )
        self.assertFalse(
            authorization.is_platform_admin(inactive)
        )
        self.assertEqual(authorization.get_capabilities(inactive), frozenset())

    def test_is_admin_panel_user_matrix(self):
        cases = {
            Role.PARTICIPANT: False,
            Role.CLUB_OWNER: True,
            Role.GUIDE: True,
            Role.INTERNAL_ADMIN: True,
            Role.PLATFORM_ADMIN: True,
        }
        for role, expected in cases.items():
            user = make_user(f"{role}@example.com", role=role)
            self.assertEqual(
                authorization.is_admin_panel_user(user), expected, role
            )

    def test_has_capability_respects_role(self):
        guide = make_user("g2@example.com", role=Role.GUIDE)
        self.assertTrue(
            authorization.has_capability(guide, Capability.QR_CHECK_IN)
        )
        self.assertFalse(
            authorization.has_capability(guide, Capability.VIEW_FINANCES)
        )

    def test_internal_admin_capability_from_assignment(self):
        ia = make_user(
            "ia@example.com",
            role=Role.INTERNAL_ADMIN,
            custom_capabilities=[Capability.ISSUE_REFUND.value],
        )
        self.assertTrue(
            authorization.has_capability(ia, Capability.ISSUE_REFUND)
        )
        self.assertFalse(
            authorization.has_capability(ia, Capability.QR_CHECK_IN)
        )


class GrantGuardrailTests(TestCase):
    def test_platform_admin_can_grant_anything(self):
        admin = make_user("pa@example.com", role=Role.PLATFORM_ADMIN)
        self.assertEqual(
            authorization.can_grant_capabilities(
                admin, [Capability.ISSUE_REFUND.value]
            ),
            [],
        )

    def test_club_owner_cannot_grant_governance_caps(self):
        owner = make_user("own@example.com", role=Role.CLUB_OWNER)
        self.assertEqual(
            authorization.can_grant_capabilities(
                owner, [Capability.ISSUE_REFUND.value]
            ),
            [Capability.ISSUE_REFUND.value],
        )

    def test_club_owner_can_grant_owned_caps(self):
        owner = make_user("own2@example.com", role=Role.CLUB_OWNER)
        self.assertEqual(
            authorization.can_grant_capabilities(
                owner, [Capability.QR_CHECK_IN.value]
            ),
            [],
        )

    def test_participant_cannot_grant(self):
        part = make_user("p@example.com", role=Role.PARTICIPANT)
        self.assertEqual(
            authorization.can_grant_capabilities(
                part, [Capability.QR_CHECK_IN.value]
            ),
            [Capability.QR_CHECK_IN.value],
        )


class CatalogTests(TestCase):
    def test_role_catalog_lists_all_roles(self):
        keys = {r["key"] for r in RoleCatalog.list()}
        self.assertEqual(keys, set(Role.values))

    def test_role_catalog_get_unknown_returns_none(self):
        self.assertIsNone(RoleCatalog.get("nope"))

    def test_internal_admin_serialized_with_empty_caps(self):
        data = RoleCatalog.serialize(Role.INTERNAL_ADMIN)
        self.assertEqual(data["capabilities"], [])

    def test_capability_catalog_lists_all(self):
        self.assertEqual(
            len(CapabilityCatalog.list()), len(ROLE_CAPABILITIES[Role.PLATFORM_ADMIN])
        )
