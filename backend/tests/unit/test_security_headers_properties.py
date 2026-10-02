"""Property-based test for backend.app.core.security_headers.

Exhaustive Hypothesis coverage proving Property 3 holds across arbitrary
request paths and status codes, complementing the four fixed smoke-test
examples in tests/unit/test_security_headers.py (task 2.4). See
design.md's Correctness Properties section for the full property
statement.
"""

import string

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.security_headers import SecurityHeadersMiddleware

_EXPECTED_HEADERS = {
    "content-security-policy": "default-src 'none'",
    "x-frame-options": "DENY",
    "referrer-policy": "no-referrer",
}

# Registered routes exercising the three "handled" response paths: a plain
# 200, a raised HTTPException producing a 500, and a raised HTTPException
# producing a 403. Mirrors the registered-route set in
# tests/unit/test_security_headers.py.
_REGISTERED_PATHS = ("/ok", "/boom", "/forbidden")

# Characters safe to embed directly in a single URL path segment without
# percent-encoding, so each generated string is a well-formed path
# component that Starlette's router can attempt (and fail) to match.
_PATH_SEGMENT_ALPHABET = string.ascii_letters + string.digits + "-_"

_unregistered_path_segment = st.text(
    alphabet=_PATH_SEGMENT_ALPHABET, min_size=1, max_size=40
)

# A mix of the three registered paths (covering 200/500/403) and many
# arbitrary, never-registered paths (covering 404 across arbitrary unmatched
# routes rather than one hardcoded "/does-not-exist" example). The
# "unregistered-" prefix guarantees no generated path can ever collide with
# a registered one.
_request_path = st.one_of(
    st.sampled_from(_REGISTERED_PATHS),
    _unregistered_path_segment.map(lambda segment: f"/unregistered-{segment}"),
)


def _build_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/ok")
    def ok() -> dict:
        return {"status": "ok"}

    @app.get("/boom")
    def boom() -> None:
        raise HTTPException(status_code=500, detail="boom")

    @app.get("/forbidden")
    def forbidden() -> None:
        raise HTTPException(status_code=403, detail="nope")

    return app


# Built once at import time, not per Hypothesis example: the app and its
# middleware carry no mutable state that depends on the request path, so
# reusing one client across every generated example is safe and keeps the
# property test from paying FastAPI app construction cost 100+ times over.
_client = TestClient(_build_app())


def _assert_security_headers_present(headers) -> None:
    for name, value in _EXPECTED_HEADERS.items():
        assert headers.get(name) == value


# Feature: aslinumber-p1-foundation, Property 3: Security headers are present on every response
@settings(max_examples=100)
@given(path=_request_path)
def test_security_headers_present_on_every_response(path: str) -> None:
    """For any request path handled by the Backend_API -- registered or

    not, success or error -- the response carries all three required
    security headers with their exact expected values, regardless of the
    resulting status code.
    """
    response = _client.get(path)

    # Every generated path resolves to exactly one of: 200 (/ok), 500
    # (/boom), 403 (/forbidden), or 404 (any unregistered path) -- never an
    # unhandled exception that would bypass the middleware's response path
    # entirely.
    assert response.status_code in (200, 403, 404, 500)
    _assert_security_headers_present(response.headers)
