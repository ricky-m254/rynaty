"""
clients/exceptions.py
----------------------
Standard API error response format (spec §9.1).

Every error — 400, 401, 403, 404, 429, 500 — returns:
{
    "success": false,
    "error": {
        "code":    "TENANT_NOT_FOUND",     // machine-readable, uppercase snake
        "message": "Tenant not found.",    // human-readable
        "details": {}                       // optional extra context
    },
    "request_id": "a1b2c3d4"              // 8-char UUID prefix for tracing
}

All success responses keep the DRF default (callers wrap in {"success": true, "data": ...}
at the serializer/view level where needed).

To activate, add to settings.py:
    REST_FRAMEWORK = {
        "EXCEPTION_HANDLER": "clients.exceptions.platform_exception_handler",
        ...
    }
"""
from __future__ import annotations

import uuid
import logging

from rest_framework.views import exception_handler as drf_exception_handler
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger(__name__)


# ── HTTP status → error code mapping ─────────────────────────────────────────

_STATUS_CODES: dict[int, str] = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMITED",
    500: "INTERNAL_ERROR",
    502: "BAD_GATEWAY",
    503: "SERVICE_UNAVAILABLE",
}


def _request_id() -> str:
    return str(uuid.uuid4()).replace("-", "")[:8]


def _normalise_detail(detail) -> tuple[str, dict]:
    """
    Convert DRF's varied error detail formats into (message, details) tuple.
    DRF can give us: str, list, dict, or ErrorDetail instances.
    """
    if isinstance(detail, str):
        return detail, {}

    if isinstance(detail, list):
        # Flat list of messages
        messages = [str(d) for d in detail]
        return messages[0] if messages else "An error occurred.", {"errors": messages}

    if isinstance(detail, dict):
        # Field-level validation errors
        field_errors = {}
        first_msg = ""
        for field, errors in detail.items():
            if isinstance(errors, list):
                msgs = [str(e) for e in errors]
                field_errors[field] = msgs
                if not first_msg:
                    first_msg = f"{field}: {msgs[0]}" if field != "non_field_errors" else msgs[0]
            else:
                field_errors[field] = str(errors)
                if not first_msg:
                    first_msg = str(errors)
        return first_msg or "Validation error.", field_errors

    return str(detail), {}


def platform_exception_handler(exc, context) -> Response | None:
    """
    DRF EXCEPTION_HANDLER.

    Wraps all DRF exceptions into the standard SmartCampus error envelope.
    Falls back to DRF default for unhandled exceptions (Django will then
    return a 500 which Django REST Framework's default handler catches).
    """
    # Let DRF handle the exception first to get the response
    response = drf_exception_handler(exc, context)

    if response is None:
        # Unhandled exception — DRF returned None, Django will 500
        # Log it here for visibility
        req_id = _request_id()
        logger.exception(
            "[platform_exception_handler] Unhandled exception req_id=%s path=%s",
            req_id,
            getattr(getattr(context.get("request"), "path", None), "__str__", lambda: "?")(),
        )
        return Response(
            {
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Something went wrong. Our team has been notified.",
                    "details": {},
                },
                "request_id": req_id,
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    req_id = _request_id()
    http_status = response.status_code
    error_code = _STATUS_CODES.get(http_status, "HTTP_ERROR")

    # Extract human-readable message and optional field details
    raw_detail = response.data
    if isinstance(raw_detail, dict) and "detail" in raw_detail and len(raw_detail) == 1:
        message, details = _normalise_detail(raw_detail["detail"])
    elif isinstance(raw_detail, dict) and "detail" not in raw_detail:
        # Field-level validation errors (no top-level "detail" key)
        message, details = _normalise_detail(raw_detail)
        error_code = "VALIDATION_ERROR"
    else:
        message, details = _normalise_detail(raw_detail)

    # Override code with more specific one if provided by the view
    if isinstance(raw_detail, dict) and "code" in raw_detail:
        error_code = str(raw_detail["code"]).upper().replace(" ", "_")

    response.data = {
        "success": False,
        "error": {
            "code": error_code,
            "message": message,
            "details": details,
        },
        "request_id": req_id,
    }

    return response


# ── Convenience exception classes ─────────────────────────────────────────────

class PlatformError(Exception):
    """
    Raise from any platform view to return a spec-compliant error response.
    Usage:
        raise PlatformError("TENANT_SUSPENDED", "This tenant is suspended.", http_status=403)
    """
    def __init__(
        self,
        code: str,
        message: str,
        http_status: int = 400,
        details: dict | None = None,
    ):
        self.code = code
        self.message = message
        self.http_status = http_status
        self.details = details or {}
        super().__init__(message)

    def to_response(self) -> Response:
        return Response(
            {
                "success": False,
                "error": {
                    "code": self.code,
                    "message": self.message,
                    "details": self.details,
                },
                "request_id": _request_id(),
            },
            status=self.http_status,
        )
