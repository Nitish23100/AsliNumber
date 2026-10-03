"""Integration tests for backend.app.api.routers.auth's auth routes.

Exercises login, logout, refresh (rotation + reuse detection), lockout,
switch-tenant, and /me end to end through a TestClient, against an
in-memory mongomock database (see tests/integration/conftest.py for why).
`create_app`'s real MongoClient is swapped for the mongomock one after
construction, since `create_app(settings=...)` always builds a real
`pymongo.MongoClient` internally for the live-deployment path.
"""

import mongomock
import pytest
from fastapi.testclient import TestClient

from app.auth.passwords import hash_password
from app.config import Settings
from app.core.ratelimit import login_rate_limiter
from app.main import create_app
from app.models.membership import Membership
from app.models.tenant import Tenant
from app.models.user import User
from app.repos import create_indexes
from app.repos.memberships_repo import MembershipsRepo
from app.repos.tenants_repo import TenantsRepo
from app.repos.users_repo import UsersRepo

_TEST_PASSWORD = "correct-horse-battery-staple"


def _build_client() -> TestClient:
    settings = Settings(
        DEMO_MODE=False,
        JWT_SECRET="integration-test-jwt-secret-value-32-bytes-min",
        MONGO_URI="mongodb://192.0.2.1:27017/aslinumber_test",
    )
    app = create_app(settings=settings)

    # A URI with an embedded database name, so `get_default_database()`
    # (what `auth.py`'s routes actually call, matching the real client's
    # usage against the Atlas URI in `.env`) resolves without needing a
    # separate `default=` argument -- this mirrors production, where
    # MONGO_URI carries `/aslinumber`.
    mongo_client = mongomock.MongoClient("mongodb://localhost:27017/aslinumber_test", tz_aware=True)
    db = mongo_client.get_default_database()
    create_indexes(db)
    app.state.mongo_client = mongo_client

    # https base_url, not the TestClient default of http://testserver:
    # the refresh cookie is set with `Secure` (correct, required by
    # Requirement 8.1), and httpx's cookie jar -- like a real browser --
    # will not attach a Secure cookie to a plain-HTTP request. Testing
    # over https matches how this cookie actually behaves in production.
    return TestClient(app, base_url="https://testserver"), db


def _seed_user_with_membership(db):
    tenants_repo = TenantsRepo(db)
    users_repo = UsersRepo(db)
    memberships_repo = MembershipsRepo(db)

    tenant = tenants_repo.create(Tenant(name="Demo Tenant", slug="demo-tenant"))
    user = users_repo.create(
        User(
            email="jane.doe@example.com",
            passwordHash=hash_password(_TEST_PASSWORD),
            name="Jane Doe",
            status="active",
        )
    )
    memberships_repo.create(Membership(userId=user.id, tenantId=tenant.id, role="analyst"))
    return tenant, user


@pytest.fixture
def client_and_db(monkeypatch):
    # `issue_access_token`/`decode_access_token` (task 5.3) instantiate
    # their own `Settings()` read from the environment on every call,
    # rather than taking the request's `app.state.settings` -- matching
    # that module's own test convention (see tests/unit/test_tokens.py),
    # JWT_SECRET must be set via the environment, not via a constructor
    # kwarg on the `Settings(...)` passed to `create_app`.
    monkeypatch.setenv("JWT_SECRET", "integration-test-jwt-secret-value-32-bytes-min")
    login_rate_limiter.reset()
    return _build_client()


def test_login_with_correct_credentials_succeeds(client_and_db) -> None:
    client, db = client_and_db
    _seed_user_with_membership(db)

    response = client.post(
        "/auth/login", json={"email": "jane.doe@example.com", "password": _TEST_PASSWORD}
    )

    assert response.status_code == 200
    assert "accessToken" in response.json()["data"]
    assert response.cookies.get("refreshToken") is not None


def test_login_with_wrong_password_fails_with_generic_message(client_and_db) -> None:
    client, db = client_and_db
    _seed_user_with_membership(db)

    response = client.post(
        "/auth/login", json={"email": "jane.doe@example.com", "password": "wrong-password"}
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


def test_login_with_unknown_email_fails_with_same_generic_message(client_and_db) -> None:
    client, db = client_and_db
    _seed_user_with_membership(db)

    known_wrong = client.post(
        "/auth/login", json={"email": "jane.doe@example.com", "password": "wrong-password"}
    )
    unknown = client.post(
        "/auth/login", json={"email": "nobody@example.com", "password": "wrong-password"}
    )

    assert known_wrong.status_code == unknown.status_code == 401
    assert known_wrong.json() == unknown.json()


def test_five_failed_logins_lock_the_account(client_and_db) -> None:
    client, db = client_and_db
    _seed_user_with_membership(db)

    for _ in range(5):
        client.post(
            "/auth/login", json={"email": "jane.doe@example.com", "password": "wrong-password"}
        )

    # A 6th attempt with the CORRECT password is still rejected while locked.
    response = client.post(
        "/auth/login", json={"email": "jane.doe@example.com", "password": _TEST_PASSWORD}
    )

    assert response.status_code == 401


def test_refresh_rotates_the_token_and_issues_a_new_access_token(client_and_db) -> None:
    client, db = client_and_db
    _seed_user_with_membership(db)
    client.post("/auth/login", json={"email": "jane.doe@example.com", "password": _TEST_PASSWORD})

    response = client.post("/auth/refresh")

    assert response.status_code == 200
    assert "accessToken" in response.json()["data"]


def test_reusing_a_rotated_refresh_token_is_rejected(client_and_db) -> None:
    client, db = client_and_db
    _seed_user_with_membership(db)
    client.post("/auth/login", json={"email": "jane.doe@example.com", "password": _TEST_PASSWORD})
    old_refresh_cookie = client.cookies.get("refreshToken")

    # First refresh succeeds and rotates the cookie.
    first = client.post("/auth/refresh")
    assert first.status_code == 200

    # Replay the OLD (now-rotated) refresh token: must be rejected.
    client.cookies.set("refreshToken", old_refresh_cookie)
    replayed = client.post("/auth/refresh")

    assert replayed.status_code == 401
    assert replayed.json()["error"]["code"] == "UNAUTHENTICATED"


def test_me_returns_authenticated_user_identity(client_and_db) -> None:
    client, db = client_and_db
    _seed_user_with_membership(db)
    login_response = client.post(
        "/auth/login", json={"email": "jane.doe@example.com", "password": _TEST_PASSWORD}
    )
    access_token = login_response.json()["data"]["accessToken"]

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {access_token}"})

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["email"] == "jane.doe@example.com"
    assert body["role"] == "analyst"
    assert len(body["memberships"]) == 1


def test_me_without_a_token_is_rejected(client_and_db) -> None:
    client, _db = client_and_db

    response = client.get("/auth/me")

    assert response.status_code == 401


def test_switch_tenant_issues_a_token_scoped_to_the_other_membership(client_and_db) -> None:
    client, db = client_and_db
    _tenant1, user = _seed_user_with_membership(db)
    tenants_repo = TenantsRepo(db)
    memberships_repo = MembershipsRepo(db)
    tenant2 = tenants_repo.create(Tenant(name="Second Tenant", slug="second-tenant"))
    memberships_repo.create(Membership(userId=user.id, tenantId=tenant2.id, role="owner"))

    login_response = client.post(
        "/auth/login", json={"email": "jane.doe@example.com", "password": _TEST_PASSWORD}
    )
    access_token = login_response.json()["data"]["accessToken"]

    response = client.post(
        "/auth/switch-tenant",
        json={"tenantId": str(tenant2.id)},
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 200
    new_token = response.json()["data"]["accessToken"]
    me_response = client.get("/auth/me", headers={"Authorization": f"Bearer {new_token}"})
    assert me_response.json()["data"]["role"] == "owner"


def test_logout_revokes_the_session(client_and_db) -> None:
    client, db = client_and_db
    _seed_user_with_membership(db)
    login_response = client.post(
        "/auth/login", json={"email": "jane.doe@example.com", "password": _TEST_PASSWORD}
    )
    access_token = login_response.json()["data"]["accessToken"]

    logout_response = client.post(
        "/auth/logout", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert logout_response.status_code == 200

    refresh_response = client.post("/auth/refresh")
    assert refresh_response.status_code == 401
