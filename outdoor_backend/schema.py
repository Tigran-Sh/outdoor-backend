"""drf-yasg schema view configuration.

Kept separate from ``urls.py`` to keep URL routing clean.
"""

from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework.permissions import AllowAny

schema_view = get_schema_view(
    openapi.Info(
        title="Outdoor Backend API",
        default_version="v1",
        description=(
            "Backend API for the Armenian outdoor experiences "
            "marketplace. Authenticate via /api/v1/auth/login/ and send "
            "the access token as: Authorization: Bearer <access-token>."
        ),
    ),
    public=True,
    permission_classes=[AllowAny],
)
