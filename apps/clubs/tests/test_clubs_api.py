from apps.clubs.models import Club
from apps.clubs.tests.base import (
    ADMIN_CLUBS_URL,
    MY_CLUB_URL,
    ClubAPITestCase,
    make_club,
)
from apps.users.constants import Role
from apps.users.tests.base import make_platform_admin, make_user


class MyClubTests(ClubAPITestCase):
    def setUp(self):
        self.club, self.owner = make_club("owner@example.com", name="Peaks")

    def test_owner_gets_their_club(self):
        self.auth(self.owner)
        res = self.client.get(MY_CLUB_URL)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["name"], "Peaks")

    def test_user_without_club_gets_404(self):
        self.auth(make_user("nobody@example.com"))
        self.assertEqual(self.client.get(MY_CLUB_URL).status_code, 404)

    def test_requires_authentication(self):
        self.assertEqual(self.client.get(MY_CLUB_URL).status_code, 401)


class AdminClubTests(ClubAPITestCase):
    def setUp(self):
        self.admin = make_platform_admin()

    def test_only_platform_admin_may_list(self):
        self.auth(make_user("p@example.com", role=Role.CLUB_OWNER))
        self.assertEqual(self.client.get(ADMIN_CLUBS_URL).status_code, 403)

        self.auth(self.admin)
        self.assertEqual(self.client.get(ADMIN_CLUBS_URL).status_code, 200)

    def test_create_club_assigns_and_promotes_owner(self):
        owner = make_user("newowner@example.com", role=Role.PARTICIPANT)
        self.auth(self.admin)
        res = self.client.post(
            ADMIN_CLUBS_URL,
            {"name": "New Club", "owner": str(owner.id)},
            format="json",
        )
        self.assertEqual(res.status_code, 201, res.json())

        owner.refresh_from_db()
        self.assertEqual(owner.role, Role.CLUB_OWNER.value)
        self.assertTrue(Club.objects.filter(owner=owner).exists())

    def test_admin_created_club_starts_verified(self):
        owner = make_user("verified@example.com")
        self.auth(self.admin)
        res = self.client.post(
            ADMIN_CLUBS_URL,
            {"name": "Vetted Club", "owner": str(owner.id)},
            format="json",
        )
        self.assertEqual(res.status_code, 201, res.json())
        self.assertTrue(res.json()["identity_verified"])
        self.assertTrue(res.json()["payment_verified"])

    def test_club_is_not_verified_by_default_at_the_model_level(self):
        """Guards the day clubs can register themselves."""
        club = Club.objects.create(
            owner=make_user("selfmade@example.com"), name="Self Made"
        )
        self.assertFalse(club.identity_verified)
        self.assertFalse(club.payment_verified)

    def test_owner_can_have_only_one_club(self):
        _, owner = make_club("taken@example.com")
        self.auth(self.admin)
        res = self.client.post(
            ADMIN_CLUBS_URL,
            {"name": "Second Club", "owner": str(owner.id)},
            format="json",
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("owner", res.json()["error"]["details"])
