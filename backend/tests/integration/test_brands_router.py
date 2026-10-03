"""Integration tests for `app.api.routers.brands` via a TestClient.

Covers creation, listing, detail (with officialContacts count),
update/version-increment, RBAC enforcement, and cross-tenant 404s --
the ordinary-path example tests the Permission_Matrix_Harness and
Cross_Tenant_Harness (task 15) later generalize across every route.
"""

import mongomock
import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from app.auth.tokens import issue_access_token
from app.config import Settings
from app.main import create_app
from app.models.role import Role
from app.repos import create_indexes


def _build_client() -> tuple[TestClient, object]:
    settings = Settings(
        DEMO_MODE=False,
        JWT_SECRET="integration-test-jwt-secret-value-32-bytes-min",
        MONGO_URI="mongodb://192.0.2.1:27017/aslinumber_test",
    )
    app = create_app(settings=settings)
    mongo_client = mongomock.MongoClient("mongodb://localhost:27017/aslinumber_test", tz_aware=True)
    db = mongo_client.get_default_database()
    create_indexes(db)
    app.state.mongo_client = mongo_client

    return TestClient(app, base_url="https://testserver"), db


@pytest.fixture
def client_and_db(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "integration-test-jwt-secret-value-32-bytes-min")
    return _build_client()


def _auth_headers(tenant_id: str, role: Role) -> dict:
    token = issue_access_token(str(ObjectId()), tenant_id, role)
    return {"Authorization": f"Bearer {token}"}


_CREATE_BODY = {
    "slug": "examplekart",
    "displayName": "ExampleKart",
    "category": "ecommerce",
    "aliases": [{"text": "EK", "lang": "en", "script": "latin", "kind": "legal"}],
    "officialDomains": [
        {"domain": "examplekart.test", "verifiedBy": "admin", "verifiedAt": "2024-01-01T00:00:00Z"}
    ],
}


def test_create_brand_as_admin_succeeds_with_version_one(client_and_db) -> None:
    client, _db = client_and_db
    tenant_id = str(ObjectId())

    response = client.post(
        "/brands", json=_CREATE_BODY, headers=_auth_headers(tenant_id, Role.ADMIN)
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["version"] == 1
    assert data["officialContacts"] == 0


def test_create_brand_as_viewer_is_forbidden(client_and_db) -> None:
    client, _db = client_and_db
    tenant_id = str(ObjectId())

    response = client.post(
        "/brands", json=_CREATE_BODY, headers=_auth_headers(tenant_id, Role.VIEWER)
    )

    assert response.status_code == 403


def test_duplicate_slug_within_tenant_is_conflict(client_and_db) -> None:
    client, _db = client_and_db
    tenant_id = str(ObjectId())
    headers = _auth_headers(tenant_id, Role.ADMIN)
    client.post("/brands", json=_CREATE_BODY, headers=headers)

    response = client.post("/brands", json=_CREATE_BODY, headers=headers)

    assert response.status_code == 409


def test_list_brands_scoped_to_tenant(client_and_db) -> None:
    client, _db = client_and_db
    tenant_a, tenant_b = str(ObjectId()), str(ObjectId())
    client.post("/brands", json=_CREATE_BODY, headers=_auth_headers(tenant_a, Role.ADMIN))

    response_a = client.get("/brands", headers=_auth_headers(tenant_a, Role.VIEWER))
    response_b = client.get("/brands", headers=_auth_headers(tenant_b, Role.VIEWER))

    assert len(response_a.json()["data"]) == 1
    assert len(response_b.json()["data"]) == 0


def test_get_brand_cross_tenant_is_not_found(client_and_db) -> None:
    client, _db = client_and_db
    tenant_a, tenant_b = str(ObjectId()), str(ObjectId())
    created = client.post("/brands", json=_CREATE_BODY, headers=_auth_headers(tenant_a, Role.ADMIN))
    brand_id = created.json()["data"]["id"]

    response = client.get(f"/brands/{brand_id}", headers=_auth_headers(tenant_b, Role.VIEWER))

    assert response.status_code == 404


def test_update_brand_increments_version_and_writes_audit_entry(client_and_db) -> None:
    client, db = client_and_db
    tenant_id = str(ObjectId())
    headers = _auth_headers(tenant_id, Role.ADMIN)
    created = client.post("/brands", json=_CREATE_BODY, headers=headers)
    brand_id = created.json()["data"]["id"]

    response = client.patch(
        f"/brands/{brand_id}", json={"displayName": "ExampleKart Updated"}, headers=headers
    )

    assert response.status_code == 200
    assert response.json()["data"]["version"] == 2
    assert response.json()["data"]["displayName"] == "ExampleKart Updated"

    audit_entries = list(db["audit_log"].find({"tenantId": ObjectId(tenant_id)}))
    assert [e["action"] for e in audit_entries] == ["brand_created", "brand_updated"]
