from django.utils import timezone

from apps.clubs.tests.base import make_club, make_member
from apps.common.constants import ActivityType, Language, Region
from apps.events.constants import (
    CancellationReason,
    Difficulty,
    DurationType,
    EventStatus,
    PriceType,
)
from apps.events.models import Event
from apps.events.tests.base import (
    EVENTS_URL,
    EventAPITestCase,
    cancel_url,
    detail_url,
    make_event,
    publish_url,
)
from apps.users.constants import Capability, Role
from apps.users.tests.base import make_platform_admin, make_user


def in_days(days):
    return (timezone.now() + timezone.timedelta(days=days)).isoformat()


class EventCreateTests(EventAPITestCase):
    def setUp(self):
        self.club, self.owner, self.guide = self.make_club_with_guide(
            "owner@example.com", "guide@example.com"
        )
        self.auth(self.owner)

    def payload(self, **overrides):
        data = {
            "title": "Aragats North Summit",
            "category": ActivityType.HIKING.value,
            "start_at": in_days(14),
            "region": Region.ARAGATSOTN.value,
            "difficulty": Difficulty.MEDIUM.value,
            "languages": [Language.HY.value],
        }
        data.update(overrides)
        return data

    def test_minimal_create_makes_a_draft(self):
        res = self.client.post(EVENTS_URL, self.payload(), format="json")
        self.assertEqual(res.status_code, 201, res.json())

        body = res.json()
        self.assertEqual(body["status"], EventStatus.DRAFT.value)
        self.assertEqual(body["club"], str(self.club.id))
        self.assertEqual(body["sold_count"], 0)

    def test_description_is_saved_and_returned(self):
        description = "A long day on the north ridge, above the cloud line."
        res = self.client.post(
            EVENTS_URL,
            self.payload(description=description),
            format="json",
        )
        self.assertEqual(res.status_code, 201, res.json())
        self.assertEqual(res.json()["description"], description)

        event = Event.objects.get(pk=res.json()["id"])
        self.assertEqual(event.description, description)

    def test_description_is_optional(self):
        res = self.client.post(EVENTS_URL, self.payload(), format="json")
        self.assertEqual(res.status_code, 201, res.json())
        self.assertEqual(res.json()["description"], "")

    def test_title_is_required(self):
        res = self.client.post(
            EVENTS_URL, self.payload(title=""), format="json"
        )
        self.assertEqual(res.status_code, 400)

    def test_languages_cannot_be_empty(self):
        res = self.client.post(
            EVENTS_URL, self.payload(languages=[]), format="json"
        )
        self.assertEqual(res.status_code, 400)

    def test_unknown_category_rejected(self):
        res = self.client.post(
            EVENTS_URL, self.payload(category="quidditch"), format="json"
        )
        self.assertEqual(res.status_code, 400)

    def test_club_is_taken_from_the_requester(self):
        other_club, _ = make_club("other@example.com", name="Other")
        res = self.client.post(
            EVENTS_URL,
            self.payload(club=str(other_club.id)),
            format="json",
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()["club"], str(self.club.id))

    def test_status_cannot_be_set_on_create(self):
        res = self.client.post(
            EVENTS_URL,
            self.payload(status=EventStatus.PUBLISHED.value),
            format="json",
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()["status"], EventStatus.DRAFT.value)

    def test_sold_count_cannot_be_set_on_create(self):
        res = self.client.post(
            EVENTS_URL, self.payload(sold_count=50), format="json"
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()["sold_count"], 0)


class EventConditionalRuleTests(EventAPITestCase):
    def setUp(self):
        self.club, self.owner, self.guide = self.make_club_with_guide(
            "owner2@example.com", "guide2@example.com"
        )
        self.auth(self.owner)
        self.event = make_event(self.club, guide=self.guide)

    def patch(self, payload):
        return self.client.patch(
            detail_url(self.event.id), payload, format="json"
        )

    def test_multi_day_requires_end_at(self):
        res = self.patch({"duration_type": DurationType.MULTI.value})
        self.assertEqual(res.status_code, 400)
        self.assertIn("end_at", res.json()["error"]["details"])

    def test_multi_day_with_end_at_accepted(self):
        res = self.patch(
            {
                "duration_type": DurationType.MULTI.value,
                "end_at": in_days(16),
            }
        )
        self.assertEqual(res.status_code, 200, res.json())

    def test_single_day_rejects_end_at(self):
        res = self.patch(
            {
                "duration_type": DurationType.SINGLE.value,
                "end_at": in_days(16),
            }
        )
        self.assertEqual(res.status_code, 400)

    def test_end_must_be_after_start(self):
        res = self.patch(
            {
                "duration_type": DurationType.MULTI.value,
                "end_at": in_days(1),
            }
        )
        self.assertEqual(res.status_code, 400)

    def test_paid_requires_price(self):
        res = self.patch({"price_type": PriceType.PAID.value})
        self.assertEqual(res.status_code, 400)
        self.assertIn("price", res.json()["error"]["details"])

    def test_paid_with_price_accepted(self):
        res = self.patch(
            {"price_type": PriceType.PAID.value, "price": "15000.00"}
        )
        self.assertEqual(res.status_code, 200, res.json())

    def test_free_rejects_price(self):
        res = self.patch(
            {"price_type": PriceType.FREE.value, "price": "15000.00"}
        )
        self.assertEqual(res.status_code, 400)

    def test_negative_price_rejected(self):
        res = self.patch(
            {"price_type": PriceType.PAID.value, "price": "-1"}
        )
        self.assertEqual(res.status_code, 400)


class EventGuideAssignmentTests(EventAPITestCase):
    def setUp(self):
        self.club, self.owner, self.guide = self.make_club_with_guide(
            "owner3@example.com", "guide3@example.com"
        )
        self.other_club, _ = make_club("other3@example.com", name="Other")
        self.other_guide = make_member(
            self.other_club, "otherguide@example.com"
        )
        self.auth(self.owner)
        self.event = make_event(self.club)

    def test_own_team_member_can_be_assigned(self):
        res = self.client.patch(
            detail_url(self.event.id),
            {"guide": str(self.guide.id)},
            format="json",
        )
        self.assertEqual(res.status_code, 200, res.json())

    def test_another_clubs_guide_is_rejected(self):
        res = self.client.patch(
            detail_url(self.event.id),
            {"guide": str(self.other_guide.id)},
            format="json",
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("guide", res.json()["error"]["details"])

    def test_deactivated_member_is_rejected(self):
        self.guide.is_active = False
        self.guide.save(update_fields=["is_active"])
        res = self.client.patch(
            detail_url(self.event.id),
            {"guide": str(self.guide.id)},
            format="json",
        )
        self.assertEqual(res.status_code, 400)


class EventPublishTests(EventAPITestCase):
    def setUp(self):
        self.club, self.owner, self.guide = self.make_club_with_guide(
            "owner4@example.com", "guide4@example.com"
        )
        self.auth(self.owner)

    def test_publish_complete_event(self):
        event = make_event(self.club, guide=self.guide)
        res = self.client.post(publish_url(event.id))
        self.assertEqual(res.status_code, 200, res.json())
        self.assertEqual(res.json()["status"], EventStatus.PUBLISHED.value)

    def test_incomplete_event_cannot_publish(self):
        event = make_event(self.club, guide=None)
        res = self.client.post(publish_url(event.id))
        self.assertEqual(res.status_code, 400)
        self.assertIn(
            "guide", res.json()["error"]["details"]["missing_to_publish"]
        )

    def test_event_without_a_description_cannot_publish(self):
        event = make_event(self.club, guide=self.guide, description="")
        res = self.client.post(publish_url(event.id))
        self.assertEqual(res.status_code, 400)
        self.assertIn(
            "description",
            res.json()["error"]["details"]["missing_to_publish"],
        )

    def test_multi_day_without_end_cannot_publish(self):
        event = make_event(
            self.club,
            guide=self.guide,
            duration_type=DurationType.MULTI,
        )
        res = self.client.post(publish_url(event.id))
        self.assertEqual(res.status_code, 400)

    def test_missing_to_publish_is_reported_on_read(self):
        event = make_event(self.club, guide=None)
        res = self.client.get(detail_url(event.id))
        self.assertIn("guide", res.json()["missing_to_publish"])

    def test_guide_cannot_publish(self):
        event = make_event(self.club, guide=self.guide)
        self.auth(self.guide.user)
        res = self.client.post(publish_url(event.id))
        self.assertEqual(res.status_code, 403)


class EventCancelTests(EventAPITestCase):
    def setUp(self):
        self.club, self.owner, self.guide = self.make_club_with_guide(
            "owner5@example.com", "guide5@example.com"
        )
        self.auth(self.owner)
        self.event = make_event(
            self.club, guide=self.guide, status=EventStatus.PUBLISHED
        )

    def test_cancel_with_reason(self):
        res = self.client.post(
            cancel_url(self.event.id),
            {"reason": CancellationReason.WEATHER.value},
            format="json",
        )
        self.assertEqual(res.status_code, 200, res.json())

        body = res.json()
        self.assertEqual(body["status"], EventStatus.CANCELLED.value)
        self.assertEqual(
            body["cancellation_reason"], CancellationReason.WEATHER.value
        )
        self.assertIsNotNone(body["cancelled_at"])

    def test_other_requires_a_description(self):
        res = self.client.post(
            cancel_url(self.event.id),
            {"reason": CancellationReason.OTHER.value},
            format="json",
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("reason_other", res.json()["error"]["details"])

    def test_other_with_description_accepted(self):
        res = self.client.post(
            cancel_url(self.event.id),
            {
                "reason": CancellationReason.OTHER.value,
                "reason_other": "Road closed by landslide.",
            },
            format="json",
        )
        self.assertEqual(res.status_code, 200, res.json())
        self.assertEqual(
            res.json()["cancellation_reason_other"],
            "Road closed by landslide.",
        )

    def test_description_dropped_for_specific_reasons(self):
        res = self.client.post(
            cancel_url(self.event.id),
            {
                "reason": CancellationReason.WEATHER.value,
                "reason_other": "ignored",
            },
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["cancellation_reason_other"], "")

    def test_unknown_reason_rejected(self):
        res = self.client.post(
            cancel_url(self.event.id),
            {"reason": "because"},
            format="json",
        )
        self.assertEqual(res.status_code, 400)

    def test_cannot_cancel_twice(self):
        self.client.post(
            cancel_url(self.event.id),
            {"reason": CancellationReason.WEATHER.value},
            format="json",
        )
        res = self.client.post(
            cancel_url(self.event.id),
            {"reason": CancellationReason.WEATHER.value},
            format="json",
        )
        self.assertEqual(res.status_code, 400)

    def test_cancelled_event_cannot_be_edited(self):
        self.client.post(
            cancel_url(self.event.id),
            {"reason": CancellationReason.WEATHER.value},
            format="json",
        )
        res = self.client.patch(
            detail_url(self.event.id),
            {"title": "Renamed"},
            format="json",
        )
        self.assertEqual(res.status_code, 400)


class EventDeleteTests(EventAPITestCase):
    def setUp(self):
        self.club, self.owner, _ = self.make_club_with_guide(
            "owner6@example.com", "guide6@example.com"
        )
        self.auth(self.owner)

    def test_draft_can_be_deleted(self):
        event = make_event(self.club)
        res = self.client.delete(detail_url(event.id))
        self.assertEqual(res.status_code, 204)
        self.assertFalse(Event.objects.filter(pk=event.pk).exists())

    def test_published_event_cannot_be_deleted(self):
        event = make_event(self.club, status=EventStatus.PUBLISHED)
        res = self.client.delete(detail_url(event.id))
        self.assertEqual(res.status_code, 400)
        self.assertTrue(Event.objects.filter(pk=event.pk).exists())


class EventScopingTests(EventAPITestCase):
    def setUp(self):
        self.club_a, self.owner_a, self.guide_a = self.make_club_with_guide(
            "a@example.com", "ga@example.com"
        )
        self.club_b, self.owner_b, _ = self.make_club_with_guide(
            "b@example.com", "gb@example.com"
        )
        self.event_a = make_event(self.club_a, title="A event")
        self.event_b = make_event(self.club_b, title="B event")

    def titles(self):
        res = self.client.get(EVENTS_URL)
        self.assertEqual(res.status_code, 200)
        return {row["title"] for row in res.json()["results"]}

    def test_owner_sees_only_their_clubs_events(self):
        self.auth(self.owner_a)
        self.assertEqual(self.titles(), {"A event"})

    def test_owner_cannot_retrieve_another_clubs_event(self):
        self.auth(self.owner_a)
        res = self.client.get(detail_url(self.event_b.id))
        self.assertEqual(res.status_code, 404)

    def test_owner_cannot_edit_another_clubs_event(self):
        self.auth(self.owner_a)
        res = self.client.patch(
            detail_url(self.event_b.id),
            {"title": "Hijacked"},
            format="json",
        )
        self.assertEqual(res.status_code, 404)

    def test_guide_sees_only_events_assigned_to_them(self):
        assigned = make_event(
            self.club_a, title="Assigned", guide=self.guide_a
        )
        self.auth(self.guide_a.user)

        self.assertEqual(self.titles(), {"Assigned"})
        self.assertEqual(
            self.client.get(detail_url(assigned.id)).status_code, 200
        )
        self.assertEqual(
            self.client.get(detail_url(self.event_a.id)).status_code, 404
        )

    def test_guide_with_no_assignments_sees_nothing(self):
        self.auth(self.guide_a.user)
        self.assertEqual(self.titles(), set())

    def test_internal_admin_with_event_capability_sees_all_club_events(self):
        member = make_member(
            self.club_a,
            "programme@example.com",
            role=Role.INTERNAL_ADMIN,
            custom_capabilities=[Capability.EDIT_EVENT.value],
        )
        self.auth(member.user)
        self.assertEqual(self.titles(), {"A event"})

    def test_platform_admin_sees_all(self):
        self.auth(make_platform_admin())
        self.assertEqual(self.titles(), {"A event", "B event"})

    def test_platform_admin_can_filter_by_club(self):
        self.auth(make_platform_admin())
        res = self.client.get(f"{EVENTS_URL}?club={self.club_b.id}")
        titles = {row["title"] for row in res.json()["results"]}
        self.assertEqual(titles, {"B event"})


class EventAccessControlTests(EventAPITestCase):
    def setUp(self):
        self.club, self.owner, self.guide = self.make_club_with_guide(
            "owner7@example.com", "guide7@example.com"
        )
        self.event = make_event(self.club, guide=self.guide)

    def payload(self):
        return {
            "title": "New event",
            "category": ActivityType.HIKING.value,
            "languages": [Language.HY.value],
        }

    def test_unauthenticated_denied(self):
        self.assertEqual(self.client.get(EVENTS_URL).status_code, 401)

    def test_participant_denied(self):
        self.auth(make_user("p@example.com", role=Role.PARTICIPANT))
        self.assertEqual(self.client.get(EVENTS_URL).status_code, 403)

    def test_guide_can_read_their_assignments_but_not_create(self):
        self.auth(self.guide.user)
        res = self.client.get(EVENTS_URL)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json()["results"]), 1)

        res = self.client.post(EVENTS_URL, self.payload(), format="json")
        self.assertEqual(res.status_code, 403)

    def test_guide_cannot_publish_or_cancel_their_own_event(self):
        self.auth(self.guide.user)
        self.assertEqual(
            self.client.post(publish_url(self.event.id)).status_code, 403
        )
        res = self.client.post(
            cancel_url(self.event.id),
            {"reason": CancellationReason.WEATHER.value},
            format="json",
        )
        self.assertEqual(res.status_code, 403)

    def test_guide_cannot_edit(self):
        self.auth(self.guide.user)
        res = self.client.patch(
            detail_url(self.event.id),
            {"title": "Renamed"},
            format="json",
        )
        self.assertEqual(res.status_code, 403)

    def test_internal_admin_with_create_event_can_create(self):
        member = make_member(
            self.club,
            "ia@example.com",
            role=Role.INTERNAL_ADMIN,
            custom_capabilities=[Capability.CREATE_EVENT.value],
        )
        self.auth(member.user)
        res = self.client.post(EVENTS_URL, self.payload(), format="json")
        self.assertEqual(res.status_code, 201, res.json())
        self.assertEqual(res.json()["club"], str(self.club.id))

    def test_internal_admin_without_capabilities_cannot_write(self):
        member = make_member(
            self.club,
            "ia2@example.com",
            role=Role.INTERNAL_ADMIN,
            custom_capabilities=[Capability.VIEW_TEAM_MEMBERS.value],
        )
        self.auth(member.user)
        res = self.client.post(EVENTS_URL, self.payload(), format="json")
        self.assertEqual(res.status_code, 403)

    def test_internal_admin_with_edit_only_cannot_cancel(self):
        member = make_member(
            self.club,
            "ia3@example.com",
            role=Role.INTERNAL_ADMIN,
            custom_capabilities=[Capability.EDIT_EVENT.value],
        )
        self.auth(member.user)
        res = self.client.post(
            cancel_url(self.event.id),
            {"reason": CancellationReason.WEATHER.value},
            format="json",
        )
        self.assertEqual(res.status_code, 403)

    def test_internal_admin_with_cancel_only_can_cancel_but_not_edit(self):
        """Each action maps to its own capability, not a blanket write."""
        member = make_member(
            self.club,
            "ia4@example.com",
            role=Role.INTERNAL_ADMIN,
            custom_capabilities=[Capability.CANCEL_EVENT.value],
        )
        self.auth(member.user)

        res = self.client.patch(
            detail_url(self.event.id), {"title": "Nope"}, format="json"
        )
        self.assertEqual(res.status_code, 403)

        res = self.client.post(
            cancel_url(self.event.id),
            {"reason": CancellationReason.WEATHER.value},
            format="json",
        )
        self.assertEqual(res.status_code, 200, res.json())

    def test_club_owner_without_a_club_denied(self):
        self.auth(make_user("clubless@example.com", role=Role.CLUB_OWNER))
        self.assertEqual(self.client.get(EVENTS_URL).status_code, 403)


class EventFilterTests(EventAPITestCase):
    def setUp(self):
        self.club, self.owner, _ = self.make_club_with_guide(
            "owner8@example.com", "guide8@example.com"
        )
        make_event(
            self.club,
            title="Draft hike",
            category=ActivityType.HIKING.value,
            region=Region.SYUNIK.value,
        )
        make_event(
            self.club,
            title="Published climb",
            category=ActivityType.CLIMBING.value,
            region=Region.KOTAYK.value,
            status=EventStatus.PUBLISHED,
        )
        self.auth(self.owner)

    def titles(self, query):
        res = self.client.get(f"{EVENTS_URL}?{query}")
        self.assertEqual(res.status_code, 200)
        return {row["title"] for row in res.json()["results"]}

    def test_filter_by_status(self):
        self.assertEqual(self.titles("status=published"), {"Published climb"})

    def test_filter_by_category(self):
        self.assertEqual(self.titles("category=hiking"), {"Draft hike"})

    def test_filter_by_region(self):
        self.assertEqual(self.titles("region=kotayk"), {"Published climb"})

    def test_search_by_title(self):
        self.assertEqual(self.titles("search=climb"), {"Published climb"})
