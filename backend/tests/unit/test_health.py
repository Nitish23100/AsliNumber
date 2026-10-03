"""Unit tests for GET /health (backend.app.api.routers.system).

Per Requirement 3.1/3.2: MongoDB reachable -> 200 with mongo: ok;
MongoDB unreachable (mocked) -> 200 with mongo: unavailable. Both are
HTTP 200 -- the health endpoint's status code reflects the API process
being up, never the database's state.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def _build_test_app():
    settings = Settings(DEMO_MODE=False, MONGO_URI="mongodb://192.0.2.1:27017/aslinumber_test")
    return create_app(settings=settings)


def test_health_returns_200_with_mongo_ok_when_reachable() -> None:
    app = _build_test_app()
    client = TestClient(app)

    with patch("app.api.routers.system.is_reachable", return_value=True):
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "mongo": "ok"}


def test_health_returns_200_with_mongo_unavailable_when_unreachable() -> None:
    app = _build_test_app()
    client = TestClient(app)

    with patch("app.api.routers.system.is_reachable", return_value=False):
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "mongo": "unavailable"}
