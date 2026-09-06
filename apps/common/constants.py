"""Platform-wide taxonomies shared across domains.

These describe the marketplace itself rather than any one app: a club
declares which activities it runs, a team member which they guide, and
an event which one it is. Keeping a single definition means those three
can be compared and filtered against each other.

Values are stable, API-friendly snake_case keys and double as the
frontend's i18n keys — never rename or reorder them.
"""

from django.db import models


class ActivityType(models.TextChoices):
    HIKING = "hiking", "Hiking"
    TRAIL_RUNNING = "trail_running", "Trail running"
    CYCLING = "cycling", "Cycling"
    CLIMBING = "climbing", "Climbing"
    ZIPLINE = "zipline", "Zipline"
    SKYDIVING = "skydiving", "Skydiving"
    PARACHUTING = "parachuting", "Parachuting"
    PARAGLIDING = "paragliding", "Paragliding"
    HANG_GLIDING = "hang_gliding", "Hang gliding"
    SUP_BOARDING = "sup_boarding", "SUP boarding"
    YACHTING = "yachting", "Yachting"
    SURFING = "surfing", "Surfing"
    KAYAKING = "kayaking", "Kayaking"
    RAFTING = "rafting", "Rafting"
    CANYONEERING = "canyoneering", "Canyoneering"
    WAKEBOARDING = "wakeboarding", "Wakeboarding"
    SKIING = "skiing", "Skiing"
    SNOWBOARDING = "snowboarding", "Snowboarding"
    OTHER = "other", "Other"


class Language(models.TextChoices):
    EN = "en", "English"
    HY = "hy", "Armenian"
    RU = "ru", "Russian"


class Region(models.TextChoices):
    """Administrative regions of Armenia (plus Yerevan)."""

    YEREVAN = "yerevan", "Yerevan"
    ARAGATSOTN = "aragatsotn", "Aragatsotn"
    ARARAT = "ararat", "Ararat"
    ARMAVIR = "armavir", "Armavir"
    GEGHARKUNIK = "gegharkunik", "Gegharkunik"
    KOTAYK = "kotayk", "Kotayk"
    LORI = "lori", "Lori"
    SHIRAK = "shirak", "Shirak"
    SYUNIK = "syunik", "Syunik"
    TAVUSH = "tavush", "Tavush"
    VAYOTS_DZOR = "vayots_dzor", "Vayots Dzor"
