"""Unit tests for backend.app.core.security_headers.

Smoke tests proving the middleware attaches the three required headers to
a normal response AND to error responses (a raised ``HTTPException`` and
an unmatched-route 404), using a minimal FastAPI app mounted just for this
test. This is example-based verification only; the exhaustive
Hypothesis-based property test (design Property 3, task 2.5) covers the
same behavior across arbitrary paths/methods on top of this middleware.
"""

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.security_headers import SecurityHeadersMiddleware

_EXPECTED_HEADERS = {
    "content-security-policy": "default-src 'none'",
    "x-frame-options": "DENY",
    "referrer-policy": "no-referrer",
}


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


def _assert_security_headers_present(headers) -> None:
    for name, value in _EXPECTED_HEADERS.items():
        assert headers.get(name) == value


def test_security_headers_present_on_successful_response() -> None:
    client = TestClient(_build_app())

    response = client.get("/ok")

    assert response.status_code == 200
    _assert_security_headers_present(response.headers)


def test_security_headers_present_on_raised_http_exception() -> None:
    client = TestClient(_build_app())

    response = client.get("/boom")

    assert response.status_code == 500
    _assert_security_headers_present(response.headers)


def test_security_headers_present_on_403_response() -> None:
    client = TestClient(_build_app())

    response = client.get("/forbidden")

    assert response.status_code == 403
    _assert_security_headers_present(response.headers)


def test_security_headers_present_on_unmatched_route_404() -> None:
    # No route is registered for this path, so Starlette's routing itself
    # produces the 404 -- never reaching a handler at all -- which still
    # must carry the security headers per the design's Error Handling
    # section ("runs unconditionally, including on 401/403/422/500
    # responses").
    client = TestClient(_build_app())

    response = client.get("/does-not-exist")

    assert response.status_code == 404
    _assert_security_headers_present(response.headers)
