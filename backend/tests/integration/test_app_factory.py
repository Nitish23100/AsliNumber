"""Integration tests for backend.app.main's FastAPI app factory.

Confirms the app factory wires routes and middleware correctly. The
exhaustive mocked-Mongo-reachable/unreachable behavior of ``/health``
itself is task 2.7's test, not this one.
"""

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def _build_test_app():
    # DEMO_MODE=False avoids triggering startup seeding (which does not
    # exist yet) and the DEMO_MODE startup guard entirely.
    settings = Settings(DEMO_MODE=False, MONGO_URI="mongodb://192.0.2.1:27017/aslinumber_test")
    return create_app(settings=settings)


def test_app_has_health_route() -> None:
    # Exercised through the TestClient rather than inspecting
    # `app.routes` directly: some FastAPI/Starlette versions wrap
    # included-router entries in objects (e.g. `_IncludedRouter`) that
    # don't expose a `.path` attribute, so asserting on the actual
    # dispatch behavior is both correct and version-resilient.
    app = _build_test_app()
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200


def test_security_headers_middleware_is_mounted() -> None:
    app = _build_test_app()
    client = TestClient(app)

    response = client.get("/health")

    assert response.headers.get("x-frame-options") == "DENY"
    assert response.headers.get("referrer-policy") == "no-referrer"
    assert response.headers.get("content-security-policy") == "default-src 'none'"


def test_health_endpoint_returns_200() -> None:
    app = _build_test_app()
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["mongo"] in ("ok", "unavailable")
