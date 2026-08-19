"""drf-yasg schema definitions for the common API."""

from drf_yasg import openapi

HEALTH_SCHEMA = dict(
    tags=["Health"],
    operation_summary="Health check",
    operation_description="Returns process health. Public endpoint.",
    security=[],
    responses={
        200: openapi.Response(
            description="Service is healthy",
            examples={"application/json": {"status": "ok"}},
        ),
    },
)
