"""Consistent API error responses.

Wraps DRF's default exception handling so that error payloads follow a
predictable shape::

    {
        "error": {
            "code": "permission_denied",
            "message": "You do not have permission to perform this action.",
            "details": {...}   # optional, for field validation errors
        }
    }
"""

from rest_framework.views import exception_handler as drf_exception_handler


def _error_code(exc, response):
    """Derive a stable, machine-readable error code."""
    code = getattr(exc, "default_code", None)
    if code:
        return str(code)
    status_code = response.status_code
    return {
        400: "bad_request",
        401: "not_authenticated",
        403: "permission_denied",
        404: "not_found",
        405: "method_not_allowed",
        409: "conflict",
        429: "throttled",
    }.get(status_code, "error")


def _error_message(data):
    """Extract a human-readable message from DRF error data."""
    if isinstance(data, dict):
        detail = data.get("detail")
        if detail is not None:
            return str(detail)
        return "Invalid input."
    if isinstance(data, list) and data:
        return str(data[0])
    return str(data)


def custom_exception_handler(exc, context):
    """DRF exception handler producing the unified error envelope."""
    response = drf_exception_handler(exc, context)
    if response is None:
        return None

    data = response.data
    error = {
        "code": _error_code(exc, response),
        "message": _error_message(data),
    }

    # Preserve field-level validation details when present.
    if isinstance(data, dict) and "detail" not in data:
        error["details"] = data

    response.data = {"error": error}
    return response
