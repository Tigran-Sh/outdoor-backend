"""Migration tests.

``0003_event_categories`` turns ``category`` into ``categories``. The
auto-generated version dropped the old column before the new one was
populated, which would have silently wiped the category off every event
already in the database — hence this test rather than trust.
"""

from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from apps.clubs.models import Club


class EventCategoriesMigrationTests(TransactionTestCase):
    before = [("events", "0002_event_description")]
    after = [("events", "0003_event_categories")]

    def tearDown(self):
        # Leave the database on the latest schema for whatever runs next.
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(self.after)

    @staticmethod
    def _state(targets):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(targets)
        return executor.loader.project_state(targets).apps

    def test_an_existing_category_becomes_a_one_item_list(self):
        old = self._state(self.before)
        # Only the events schema moves here, so users and clubs are used
        # through their real models.
        Event = old.get_model("events", "Event")

        owner = get_user_model().objects.create_user(
            email="probe@example.com", password="x", full_name="Probe"
        )
        club = Club.objects.create(owner=owner, name="Probe Club")
        climb = Event.objects.create(
            club_id=club.pk, title="Climb", category="climbing"
        )
        blank = Event.objects.create(club_id=club.pk, title="Undecided")

        new = self._state(self.after)
        Event = new.get_model("events", "Event")

        self.assertEqual(
            Event.objects.get(pk=climb.pk).categories, ["climbing"]
        )
        # An event that never had one stays empty rather than gaining [""].
        self.assertEqual(Event.objects.get(pk=blank.pk).categories, [])
