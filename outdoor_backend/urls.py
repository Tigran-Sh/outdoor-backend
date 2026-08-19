"""Root URL configuration for the outdoor_backend project."""

from django.contrib import admin
from django.urls import include, path

from apps.common.api.views import HealthView
from outdoor_backend.schema import schema_view

api_v1_patterns = [
    path("", include("apps.users.urls")),
]

urlpatterns = [
    # Django admin
    path("django-admin/", admin.site.urls),

    # Versioned business APIs
    path("api/v1/", include(api_v1_patterns)),

    # Infrastructure endpoints (no version prefix)
    path("api/health/", HealthView.as_view(), name="health"),
    path(
        "api/swagger/",
        schema_view.with_ui("swagger", cache_timeout=0),
        name="schema-swagger-ui",
    ),
    path(
        "api/redoc/",
        schema_view.with_ui("redoc", cache_timeout=0),
        name="schema-redoc",
    ),
    path(
        "api/swagger.json",
        schema_view.without_ui(cache_timeout=0),
        name="schema-json",
    ),
]
