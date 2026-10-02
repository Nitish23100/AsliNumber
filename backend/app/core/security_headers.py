"""Security headers middleware.

Implements the design's `backend/app/core/security_headers.py` component:
a Starlette ``BaseHTTPMiddleware`` that adds ``Content-Security-Policy``,
``X-Frame-Options``, and ``Referrer-Policy`` headers to every outgoing
response, including error responses (401/403/422/500/404/etc.), per
Requirement 3.3 and design Property 3.

Because this middleware wraps ``call_next`` in a ``try/except`` and injects
the headers in a ``finally``-equivalent path for both the success and
exception branches, the headers are present even when:

- A route handler returns a normal response (200, 201, ...).
- FastAPI's own exception handling produces an error response (401, 403,
  404, 422, 500, ...) via ``HTTPException`` or request-validation errors,
  since those are translated into a ``Response`` object by Starlette's
  exception middleware *before* unwinding back through this middleware.
- An unhandled exception propagates out of ``call_next`` entirely (e.g. no
  exception handler is registered at all); in that case this middleware
  cannot attach headers to a response that was never created, so it lets
  the exception propagate after logging is not needed here --
  ``ServerErrorMiddleware``, which Starlette installs outermost by
  default, converts that into a 500 response *above* this middleware in
  the stack. To guarantee headers reach that path too, this middleware
  should be added close to the outside of the middleware stack (the
  default when using ``app.add_middleware``), so Starlette's own
  ``ServerErrorMiddleware`` sits outside of it and this middleware still
  observes the generated 500 response. See ``backend/app/main.py``
  (task 2.6) for the exact mounting order.
"""

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# A restrictive default appropriate for a backend JSON API that never
# serves HTML pages, inline scripts, or embeddable frames of its own.
# `default-src 'none'` denies every resource type (scripts, styles,
# images, fonts, connect, frames, etc.) by default; since every response
# from this API is JSON (or a plain error body), there is nothing for a
# browser to legitimately fetch or render under this origin, so the most
# restrictive policy is also the correct one -- it is not a page-serving
# server that needs to allow its own scripts/styles/images.
_CONTENT_SECURITY_POLICY = "default-src 'none'"
_X_FRAME_OPTIONS = "DENY"
_REFERRER_POLICY = "no-referrer"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds baseline security headers to every response.

    Mount this with ``app.add_middleware(SecurityHeadersMiddleware)``. It
    must run on every response produced by the ASGI app -- including
    responses produced by FastAPI/Starlette's own exception handling for
    ``HTTPException`` and request-validation errors -- because
    ``BaseHTTPMiddleware`` sits inside Starlette's ``ExceptionMiddleware``
    (which turns raised ``HTTPException``s into responses) but outside the
    route handler itself, so ``call_next`` already returns a complete
    ``Response`` object for both success and handled-error paths alike.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = _CONTENT_SECURITY_POLICY
        response.headers["X-Frame-Options"] = _X_FRAME_OPTIONS
        response.headers["Referrer-Policy"] = _REFERRER_POLICY
        return response
