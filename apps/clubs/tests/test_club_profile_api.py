from datetime import date

from apps.clubs.constants import ActivityType, EntityType, Region
from apps.clubs.tests.base import (
    MY_CLUB_URL,
    ClubAPITestCase,
    id_document_url,
    image_upload,
    make_club,
    make_member,
    upload,
)
from apps.users.constants import Capability, Role
from apps.users.tests.base import make_platform_admin, make_user

ABOUT = "We run guided hikes across Armenia for every level of walker."


class ClubProfileUpdateTests(ClubAPITestCase):
    def setUp(self):
        self.club, self.owner = make_club("owner@example.com", name="Peaks")
        self.auth(self.owner)

    def patch(self, payload, **kwargs):
        return self.client.patch(MY_CLUB_URL, payload, **kwargs)

    def test_owner_updates_profile_fields(self):
        res = self.patch(
            {
                "about": ABOUT,
                "base_region": Region.SYUNIK.value,
                "activity_types": [ActivityType.HIKING.value],
                "email": "hello@peaks.am",
                "phone": "+37411223344",
            },
            format="json",
        )
        self.assertEqual(res.status_code, 200, res.json())

        self.club.refresh_from_db()
        self.assertEqual(self.club.about, ABOUT)
        self.assertEqual(self.club.base_region, Region.SYUNIK.value)

    def test_about_has_a_minimum_length(self):
        res = self.patch({"about": "Too short."}, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertIn("about", res.json()["error"]["details"])

    def test_activity_types_cannot_be_emptied(self):
        res = self.patch({"activity_types": []}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_unknown_activity_type_rejected(self):
        res = self.patch({"activity_types": ["quidditch"]}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_year_founded_bounds(self):
        current_year = date.today().year
        for year in (1899, current_year + 1):
            res = self.patch({"year_founded": year}, format="json")
            self.assertEqual(res.status_code, 400, year)

        res = self.patch({"year_founded": 2010}, format="json")
        self.assertEqual(res.status_code, 200, res.json())

    def test_website_must_be_a_url(self):
        res = self.patch({"website": "not a url"}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_owner_and_status_are_not_editable(self):
        other = make_user("other@example.com")
        res = self.patch(
            {"owner": str(other.id), "status": "suspended"},
            format="json",
        )
        self.assertEqual(res.status_code, 200)

        self.club.refresh_from_db()
        self.assertEqual(self.club.owner_id, self.owner.id)
        self.assertNotEqual(self.club.status, "suspended")

    def test_verification_flags_are_not_editable(self):
        res = self.patch(
            {"identity_verified": True, "payment_verified": True},
            format="json",
        )
        self.assertEqual(res.status_code, 200)

        self.club.refresh_from_db()
        self.assertFalse(self.club.identity_verified)
        self.assertFalse(self.club.payment_verified)

    def test_missing_profile_fields_reported(self):
        res = self.client.get(MY_CLUB_URL)
        missing = res.json()["missing_profile_fields"]
        self.assertIn("logo", missing)
        self.assertIn("about", missing)
        self.assertIn("social_links", missing)
        self.assertNotIn("name", missing)


class ClubSocialLinkTests(ClubAPITestCase):
    def setUp(self):
        self.club, self.owner = make_club("social@example.com")
        self.auth(self.owner)

    def test_one_social_link_is_enough(self):
        res = self.client.patch(
            MY_CLUB_URL, {"instagram": "@peaks"}, format="json"
        )
        self.assertEqual(res.status_code, 200, res.json())

    def test_cannot_clear_every_social_link(self):
        self.club.instagram = "@peaks"
        self.club.save(update_fields=["instagram"])

        res = self.client.patch(
            MY_CLUB_URL, {"instagram": ""}, format="json"
        )
        self.assertEqual(res.status_code, 400)

    def test_unrelated_edit_is_not_blocked_by_missing_socials(self):
        res = self.client.patch(
            MY_CLUB_URL, {"phone": "+37411223344"}, format="json"
        )
        self.assertEqual(res.status_code, 200, res.json())


class ClubLegalFieldTests(ClubAPITestCase):
    def setUp(self):
        self.club, self.owner = make_club("legal@example.com")
        self.auth(self.owner)

    def test_tax_id_required_for_sole_trader(self):
        res = self.client.patch(
            MY_CLUB_URL,
            {"entity_type": EntityType.SOLE_TRADER.value},
            format="json",
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("tax_id", res.json()["error"]["details"])

    def test_tax_id_accepted_with_entity_type(self):
        res = self.client.patch(
            MY_CLUB_URL,
            {
                "entity_type": EntityType.LLC.value,
                "tax_id": "12345678",
            },
            format="json",
        )
        self.assertEqual(res.status_code, 200, res.json())

    def test_id_document_required_for_individual(self):
        res = self.client.patch(
            MY_CLUB_URL,
            {"entity_type": EntityType.INDIVIDUAL.value},
            format="json",
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("owner_id_document", res.json()["error"]["details"])

    def test_id_document_accepted_with_entity_type(self):
        res = self.client.patch(
            MY_CLUB_URL,
            {
                "entity_type": EntityType.INFORMAL.value,
                "owner_id_document": upload("passport.png"),
            },
            format="multipart",
        )
        self.assertEqual(res.status_code, 200, res.json())

        self.club.refresh_from_db()
        self.assertTrue(self.club.owner_id_document)

    def test_tax_id_not_required_for_individual(self):
        res = self.client.patch(
            MY_CLUB_URL,
            {
                "entity_type": EntityType.INDIVIDUAL.value,
                "owner_id_document": upload("passport.png"),
            },
            format="multipart",
        )
        self.assertEqual(res.status_code, 200, res.json())


class ClubUploadTests(ClubAPITestCase):
    def setUp(self):
        self.club, self.owner = make_club("upload@example.com")
        self.auth(self.owner)

    def test_logo_upload_is_stored(self):
        res = self.client.patch(
            MY_CLUB_URL,
            {"logo": image_upload()},
            format="multipart",
        )
        self.assertEqual(res.status_code, 200, res.json())

        self.club.refresh_from_db()
        self.assertTrue(self.club.logo)
        self.assertIn("clubs/logos/", self.club.logo.name)

    def test_pdf_allowed_for_the_id_document(self):
        res = self.client.patch(
            MY_CLUB_URL,
            {
                "entity_type": EntityType.INDIVIDUAL.value,
                "owner_id_document": upload(
                    "scan.pdf", content_type="application/pdf"
                ),
            },
            format="multipart",
        )
        self.assertEqual(res.status_code, 200, res.json())


class ClubProfileAccessTests(ClubAPITestCase):
    def setUp(self):
        self.club_a, self.owner_a = make_club("a@example.com", name="A")
        self.club_b, self.owner_b = make_club("b@example.com", name="B")

    def test_owner_only_ever_edits_their_own_club(self):
        """There is no path to another club: the URL has no id."""
        self.auth(self.owner_a)
        self.client.patch(MY_CLUB_URL, {"name": "Renamed"}, format="json")

        self.club_b.refresh_from_db()
        self.assertEqual(self.club_b.name, "B")

    def test_user_without_club_cannot_patch(self):
        self.auth(make_user("nobody@example.com"))
        res = self.client.patch(
            MY_CLUB_URL, {"name": "Mine now"}, format="json"
        )
        self.assertEqual(res.status_code, 404)

    def test_requires_authentication(self):
        res = self.client.patch(
            MY_CLUB_URL, {"name": "Anonymous"}, format="json"
        )
        self.assertEqual(res.status_code, 401)


class ClubIdDocumentAccessTests(ClubAPITestCase):
    def setUp(self):
        self.club, self.owner = make_club("doc@example.com")
        self.club.owner_id_document = upload("passport.png")
        self.club.save(update_fields=["owner_id_document"])
        self.other_club, self.other_owner = make_club("other@example.com")

    def test_document_url_is_never_exposed_in_the_profile(self):
        self.auth(self.owner)
        body = self.client.get(MY_CLUB_URL).json()
        self.assertNotIn("owner_id_document", body)
        self.assertTrue(body["has_owner_id_document"])

    def test_owner_can_download_their_own(self):
        self.auth(self.owner)
        res = self.client.get(id_document_url(self.club.id))
        self.assertEqual(res.status_code, 200)

    def test_another_owner_cannot_download(self):
        self.auth(self.other_owner)
        res = self.client.get(id_document_url(self.club.id))
        self.assertEqual(res.status_code, 403)

    def test_platform_admin_can_download(self):
        self.auth(make_platform_admin())
        res = self.client.get(id_document_url(self.club.id))
        self.assertEqual(res.status_code, 200)

    def test_internal_admin_without_verify_club_cannot_download(self):
        reader = make_member(
            self.other_club,
            "reader@example.com",
            role=Role.INTERNAL_ADMIN,
            custom_capabilities=[Capability.VIEW_TEAM_MEMBERS.value],
        )
        self.auth(reader.user)
        res = self.client.get(id_document_url(self.club.id))
        self.assertEqual(res.status_code, 403)

    def test_staff_with_verify_club_can_download(self):
        verifier = make_user(
            "verifier@example.com",
            role=Role.INTERNAL_ADMIN,
            custom_capabilities=[Capability.VERIFY_CLUB.value],
        )
        self.auth(verifier)
        res = self.client.get(id_document_url(self.club.id))
        self.assertEqual(res.status_code, 200)

    def test_requires_authentication(self):
        res = self.client.get(id_document_url(self.club.id))
        self.assertEqual(res.status_code, 401)

    def test_404_when_no_document_uploaded(self):
        self.auth(self.other_owner)
        res = self.client.get(id_document_url(self.other_club.id))
        self.assertEqual(res.status_code, 404)


class AdminClubFilterTests(ClubAPITestCase):
    def setUp(self):
        self.admin = make_platform_admin()
        self.club_a, _ = make_club("fa@example.com", name="Verified")
        self.club_a.identity_verified = True
        self.club_a.entity_type = EntityType.LLC.value
        self.club_a.base_region = Region.YEREVAN.value
        self.club_a.save()
        self.club_b, _ = make_club("fb@example.com", name="Unverified")
        self.auth(self.admin)

    def names(self, query):
        res = self.client.get(f"/api/v1/admin/clubs/?{query}")
        self.assertEqual(res.status_code, 200)
        return {row["name"] for row in res.json()["results"]}

    def test_filter_by_identity_verified(self):
        self.assertEqual(self.names("identity_verified=true"), {"Verified"})
        self.assertEqual(
            self.names("identity_verified=false"), {"Unverified"}
        )

    def test_filter_by_entity_type_and_region(self):
        self.assertEqual(
            self.names(f"entity_type={EntityType.LLC.value}"), {"Verified"}
        )
        self.assertEqual(
            self.names(f"base_region={Region.YEREVAN.value}"), {"Verified"}
        )

    def test_no_filter_returns_all(self):
        self.assertEqual(self.names(""), {"Verified", "Unverified"})
