"""Error envelope and the application-wide error exception type.

Implements the design's Error Handling section: every error response body
is shaped exactly as ``{"error": {"code": ..., "message": ..., "details":
...}}``, as opposed to the ``{"data": ..., "meta": {...}}`` shape used by
success responses (plan §9.7).

P1's auth skeleton reaches five error codes: ``VALIDATION_ERROR``,
``UNAUTHENTICATED``, ``FORBIDDEN``, ``RATE_LIMITED``, and ``INTERNAL``.
P2 adds two more per its own Error Handling section: ``CONFLICT`` (409 --
duplicate brand slug within a tenant; the Last_Owner_Rule) and
``NOT_FOUND`` (404 -- a brand/official-contact/membership id absent from
the requester's TenantContext, including ids that exist only in a
different tenant). ``AppError`` is the single parameterized exception a
FastAPI exception handler catches and converts into the envelope with the
matching HTTP status code.

Nothing here implements the error-handling *behaviors* described
narratively in the design (refresh-reuse/expired/unknown-token response
indistinguishability, lockout non-disclosure of remaining attempts or
unlock time) -- those are route-level decisions about which code/message a
later task chooses to raise with, not something this module can enforce.
This module only has to make sure ``UNAUTHENTICATED`` carries a single
generic message content regardless of caller, which later call sites
achieve simply by passing the same message string; it does not need
special support here.
"""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class ErrorCode(StrEnum):
    """The error codes reachable from this phase's auth skeleton.

    Per the design's Error Handling table:

    | Code | HTTP | Raised when |
    |---|---|---|
    | VALIDATION_ERROR | 422 | Login/refresh body fails Pydantic validation |
    | UNAUTHENTICATED | 401 | Missing/invalid/expired token; wrong password; locked |
    | | | account; expired/unknown/reused refresh token |
    | FORBIDDEN | 403 | Access token's role rank is below a route's required minimum |
    | RATE_LIMITED | 429 | Login endpoint's per-IP rate limit is exceeded |
    | INTERNAL | 500 | Unhandled exception |

    Later phases extend this set per the full implementation plan §9.7's
    error-code table, once the functionality that raises each code exists:
    ``CONFLICT``, ``SWEEP_STATE``, ``BUDGET_EXCEEDED``, and
    ``ML_INSUFFICIENT_LABELS`` (all HTTP 409), ``API_KEY_MISSING`` (400),
    ``UPSTREAM_ERROR`` (502), and ``UPSTREAM_TIMEOUT`` (504). Not
    implemented in this phase -- add them to this enum and to
    ``_DEFAULT_STATUS_CODES`` below when the owning feature lands.
    """

    VALIDATION_ERROR = "VALIDATION_ERROR"
    UNAUTHENTICATED = "UNAUTHENTICATED"
    FORBIDDEN = "FORBIDDEN"
    RATE_LIMITED = "RATE_LIMITED"
    INTERNAL = "INTERNAL"
    CONFLICT = "CONFLICT"
    NOT_FOUND = "NOT_FOUND"


_DEFAULT_STATUS_CODES: dict[ErrorCode, int] = {
    ErrorCode.VALIDATION_ERROR: 422,
    ErrorCode.UNAUTHENTICATED: 401,
    ErrorCode.FORBIDDEN: 403,
    ErrorCode.RATE_LIMITED: 429,
    ErrorCode.INTERNAL: 500,
    ErrorCode.CONFLICT: 409,
    ErrorCode.NOT_FOUND: 404,
}


class ErrorDetail(BaseModel):
    """The ``error`` object inside the envelope."""

    code: ErrorCode
    message: str
    details: dict[str, Any] | None = None


class ErrorEnvelope(BaseModel):
    """The full error response body: ``{"error": {code, message, details}}``."""

    error: ErrorDetail


def build_error_envelope(
    code: ErrorCode, message: str, details: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Build the exact ``{"error": {...}}`` envelope dict for a response body.

    Args:
        code: One of :class:`ErrorCode`.
        message: A human-readable error message. Caller is responsible for
            avoiding disclosure of sensitive detail (e.g. the design's
            lockout non-disclosure rule), since this function only shapes
            whatever message it is given.
        details: Optional structured detail (e.g. per-field validation
            errors). ``None`` by default.

    Returns:
        A plain ``dict`` matching ``{"error": {"code", "message",
        "details"}}``, suitable for passing directly as a JSON response
        body.
    """
    return ErrorEnvelope(error=ErrorDetail(code=code, message=message, details=details)).model_dump(
        mode="json"
    )


class AppError(Exception):
    """A single parameterized exception for every application-level error.

    A later FastAPI exception handler (task 2.6 or a later auth-routes
    task) catches ``AppError`` and responds with ``status_code`` and the
    envelope from :meth:`to_envelope`, so route handlers only need to
    ``raise AppError(...)`` instead of each defining their own exception
    type.

    Args:
        code: One of :class:`ErrorCode`.
        message: A human-readable error message included in the envelope.
        status_code: The HTTP status to respond with. Defaults to the
            code's status from the design's Error Handling table (see
            :data:`_DEFAULT_STATUS_CODES`) when omitted, so call sites for
            the five codes above don't need to repeat the status code;
            an explicit value still overrides the default when needed.
        details: Optional structured detail included in the envelope.
    """

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code if status_code is not None else _DEFAULT_STATUS_CODES[code]
        self.details = details
        super().__init__(message)

    def to_envelope(self) -> dict[str, Any]:
        """Return this error's ``{"error": {...}}`` response body."""
        return build_error_envelope(self.code, self.message, self.details)
