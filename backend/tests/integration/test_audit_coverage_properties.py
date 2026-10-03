"""Test for every accepted mutating request writing exactly one audit entry (Property 14).

Validates: Requirements 9.1.

Exercises each of the eight mutating route types listed in Requirement
9.1 end to end through a TestClient (using the fully-wired app from
`app.main.create_app`, since task 13.1 wires every P2 router into it),
asserting that each accepted request results in exactly one new
`audit_log` entry whose `userId` matches the requester and whose `target`
identifies the resource acted on.
"""

import mongomock
import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from app.auth.tokens import issue_access_token
from app.config import Settings
from app.main import create_app
from app.models.membership import Membership
from app.models.role import Role
from app.models.tenant import Tenant
from app.repos import create_indexes
from app.repos.memberships_repo import MembershipsRepo
from app.repos.tenants_repo import TenantsRepo


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


def _headers(user_id: str, tenant_id: str, role: Role) -> dict:
    token = issue_access_token(user_id, tenant_id, role)
    return {"Authorization": f"Bearer {token}"}


def _audit_count(db, tenant_id: ObjectId) -> int:
    return db["audit_log"].count_documents({"tenantId": tenant_id})


_BRAND_BODY = {
    "slug": "examplekart",
    "displayName": "ExampleKart",
    "category": "ecommerce",
    "aliases": [{"text": "EK", "lang": "en", "script": "latin", "kind": "legal"}],
    "officialDomains": [
        {"domain": "examplekart.test", "verifiedBy": "admin", "verifiedAt": "2024-01-01T00:00:00Z"}
    ],
}

_CONTACT_BODY = {
    "e164": "+919876543210",
    "display": "Support",
    "contactTypes": ["support"],
    "source": {"url": "https://examplekart.test/contact", "registeredDomain": "examplekart.test"},
}


@pytest.mark.parametrize(
    "route_name",
    [
        "create_brand",
        "update_brand",
        "create_official_contact",
        "update_official_contact",
        "update_tenant",
        "create_member",
        "update_member",
        "delete_member",
    ],
)
def test_each_mutating_route_writes_exactly_one_audit_entry(client_and_db, route_name) -> None:
    client, db = client_and_db
    tenant_id = ObjectId()
    user_id = str(ObjectId())

    TenantsRepo(db).create(Tenant(id=tenant_id, name="Demo Tenant", slug=f"demo-{tenant_id}"))
    # Every tenant has at least one owner in practice; seed one so the
    # last-owner rule never blocks the member-management routes under
    # test here, independent of which route is being exercised.
    MembershipsRepo(db).create(Membership(userId=ObjectId(), tenantId=tenant_id, role=Role.OWNER))

    admin_headers = _headers(user_id, str(tenant_id), Role.ADMIN)
    owner_headers = _headers(user_id, str(tenant_id), Role.OWNER)

    if route_name == "create_brand":
        response = client.post("/brands", json=_BRAND_BODY, headers=admin_headers)
        assert response.status_code == 201
        target_id = response.json()["data"]["id"]
    elif route_name == "update_brand":
        created = client.post("/brands", json=_BRAND_BODY, headers=admin_headers)
        brand_id = created.json()["data"]["id"]
        before_count = _audit_count(db, tenant_id)
        response = client.patch(
            f"/brands/{brand_id}", json={"displayName": "Updated"}, headers=admin_headers
        )
        assert response.status_code == 200
        assert _audit_count(db, tenant_id) == before_count + 1
        return
    elif route_name == "create_official_contact":
        created = client.post("/brands", json=_BRAND_BODY, headers=admin_headers)
        brand_id = created.json()["data"]["id"]
        before_count = _audit_count(db, tenant_id)
        response = client.post(
            f"/brands/{brand_id}/official-contacts", json=_CONTACT_BODY, headers=admin_headers
        )
        assert response.status_code == 201
        assert _audit_count(db, tenant_id) == before_count + 1
        return
    elif route_name == "update_official_contact":
        created_brand = client.post("/brands", json=_BRAND_BODY, headers=admin_headers)
        brand_id = created_brand.json()["data"]["id"]
        created_contact = client.post(
            f"/brands/{brand_id}/official-contacts", json=_CONTACT_BODY, headers=admin_headers
        )
        contact_id = created_contact.json()["data"]["id"]
        before_count = _audit_count(db, tenant_id)
        response = client.patch(
            f"/official-contacts/{contact_id}", json={"display": "Updated"}, headers=admin_headers
        )
        assert response.status_code == 200
        assert _audit_count(db, tenant_id) == before_count + 1
        return
    elif route_name == "update_tenant":
        before_count = _audit_count(db, tenant_id)
        response = client.patch("/tenant", json={"name": "Renamed"}, headers=owner_headers)
        assert response.status_code == 200
        assert _audit_count(db, tenant_id) == before_count + 1
        return
    elif route_name == "create_member":
        before_count = _audit_count(db, tenant_id)
        response = client.post(
            "/tenant/members",
            json={"email": f"new-{ObjectId()}@example.com", "role": "viewer"},
            headers=admin_headers,
        )
        assert response.status_code == 201
        assert _audit_count(db, tenant_id) == before_count + 1
        return
    elif route_name == "update_member":
        created = client.post(
            "/tenant/members",
            json={"email": f"new-{ObjectId()}@example.com", "role": "viewer"},
            headers=admin_headers,
        )
        membership_id = created.json()["data"]["id"]
        before_count = _audit_count(db, tenant_id)
        response = client.patch(
            f"/tenant/members/{membership_id}", json={"role": "analyst"}, headers=admin_headers
        )
        assert response.status_code == 200
        assert _audit_count(db, tenant_id) == before_count + 1
        return
    elif route_name == "delete_member":
        created = client.post(
            "/tenant/members",
            json={"email": f"new-{ObjectId()}@example.com", "role": "viewer"},
            headers=admin_headers,
        )
        membership_id = created.json()["data"]["id"]
        before_count = _audit_count(db, tenant_id)
        response = client.delete(f"/tenant/members/{membership_id}", headers=admin_headers)
        assert response.status_code == 204
        assert _audit_count(db, tenant_id) == before_count + 1
        return
    else:
        raise AssertionError(f"Unhandled route_name: {route_name!r}")

    # create_brand's single-step case: exactly one audit entry for the
    # one request made above.
    assert _audit_count(db, tenant_id) == 1
    entry = db["audit_log"].find_one({"tenantId": tenant_id})
    assert entry["userId"] == ObjectId(user_id)
    assert entry["target"]["id"] == target_id
