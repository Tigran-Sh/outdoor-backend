"""Turn an event's single category into a list of them.

The auto-generated version dropped ``category`` before the new column
existed, losing every event's category. The copy step in the middle is
what makes this safe to run against a live database.
"""

import django.contrib.postgres.fields
from django.db import migrations, models

from apps.common.constants import ActivityType


def to_list(apps, schema_editor):
    Event = apps.get_model("events", "Event")
    for event in Event.objects.exclude(category="").iterator():
        Event.objects.filter(pk=event.pk).update(categories=[event.category])


def to_single(apps, schema_editor):
    Event = apps.get_model("events", "Event")
    for event in Event.objects.iterator():
        Event.objects.filter(pk=event.pk).update(
            category=event.categories[0] if event.categories else ""
        )


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0002_event_description'),
    ]

    operations = [
        migrations.AddField(
            model_name='event',
            name='categories',
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.CharField(
                    choices=ActivityType.choices, max_length=32
                ),
                blank=True,
                default=list,
                size=None,
            ),
        ),
        migrations.RunPython(to_list, to_single),
        migrations.RemoveField(
            model_name='event',
            name='category',
        ),
    ]
