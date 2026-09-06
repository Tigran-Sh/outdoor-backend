"""Club and team-member enumerations.

Like ``apps.users.constants``, these are fixed, code-defined taxonomies
(no DB-driven lookup tables). Values are stable, API-friendly snake_case
keys; the frontend maps its own camelCase labels onto them.
"""

from django.db import models

from apps.users.constants import Role


class ClubStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    PENDING_APPROVAL = "pending_approval", "Pending approval"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    SUSPENDED = "suspended", "Suspended"


class EntityType(models.TextChoices):
    """The legal form a club operates under."""

    INDIVIDUAL = "individual", "Individual"
    SOLE_TRADER = "sole_trader", "Sole trader"
    LLC = "llc", "LLC"
    INFORMAL = "informal", "Informal group"


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


class TeamRole(models.TextChoices):
    """Club-internal job title.

    Deliberately separate from the platform-wide ``users.Role``: this is
    a label inside a club, not an authorization role.
    """

    LEAD_GUIDE = "lead_guide", "Lead guide"
    SWEEP_GUIDE = "sweep_guide", "Sweep guide"
    MANAGER = "manager", "Manager"
    ADMIN_ASSISTANT = "admin_assistant", "Admin assistant"


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


# Platform roles a Club Owner may provision for a team member. Anything
# else (e.g. platform_admin) is never creatable through the team API.
TEAM_MEMBER_ROLES = frozenset({Role.GUIDE, Role.INTERNAL_ADMIN})


# Legal forms that must declare a tax ID (ՀՎՀՀ). The remaining forms
# instead have to upload the owner's identity document.
TAX_ID_ENTITY_TYPES = frozenset({EntityType.SOLE_TRADER, EntityType.LLC})
ID_DOCUMENT_ENTITY_TYPES = frozenset(
    {EntityType.INDIVIDUAL, EntityType.INFORMAL}
)

# At least one of these must be filled in: they are the club's public
# contact channels.
SOCIAL_FIELDS = ("instagram", "facebook", "telegram")

# Fields that must all be present before a club profile counts as
# complete. The conditional legal fields are checked separately.
REQUIRED_PROFILE_FIELDS = (
    "name",
    "logo",
    "about",
    "activity_types",
    "base_region",
    "email",
    "phone",
)

ABOUT_MIN_LENGTH = 50
YEAR_FOUNDED_MIN = 1900
