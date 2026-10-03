"""Integration test for login rate limiting (task 9.6).

Validates: Requirement 9.5. Exceeding the configured per-IP threshold
returns HTTP 429.
"""

import mongomock
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.core.ratelimit import login_rate_limiter
from app.main import create_app
from app.repos import create_indexes


@pytest.fixture
def rate_limit_client(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "integration-test-jwt-secret-value-32-bytes-min")
    login_rate_limiter.reset()

    settings = Settings(
        DEMO_MODE=False,
        MONGO_URI="mongodb://192.0.2.1:27017/aslinumber_test",
    )
    app = create_app(settings=settings)
    mongo_client = mongomock.MongoClient("mongodb://localhost:27017/aslinumber_test", tz_aware=True)
    db = mongo_client.get_default_database()
    create_indexes(db)
    app.state.mongo_client = mongo_client

    return TestClient(app, base_url="https://testserver")


def test_exceeding_login_rate_limit_returns_429(rate_limit_client) -> None:
    client = rate_limit_client

    # login_rate_limiter allows 10 requests/minute (app/core/ratelimit.py);
    # the 11th from the same client IP must be rejected with 429,
    # regardless of credentials correctness -- the limiter runs before
    # any password check.
    for _ in range(10):
        response = client.post(
            "/auth/login", json={"email": "nobody@example.com", "password": "wrong"}
        )
        assert response.status_code != 429

    limited_response = client.post(
        "/auth/login", json={"email": "nobody@example.com", "password": "wrong"}
    )

    assert limited_response.status_code == 429
    assert limited_response.json()["error"]["code"] == "RATE_LIMITED"
