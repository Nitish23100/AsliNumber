"""Integration tests for `app.api.routers.tenant` via a TestClient.

Covers tenant settings read/update (including the never-disclose-
serpapiKeyEnc rule, task 11.2/Property 11, and the reflects-on-GET
example, task 11.3), member add/list/role-change/remove (task 11.5/11.6),
the owner-protection rule, the last-owner rule, and 404s for unknown
membership ids.
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


def _build_client() -> tuple[TestClient, object, Tenant]:
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

    tenants_repo = TenantsRepo(db)
    tenant = tenants_repo.create(
        Tenant(name="Demo Tenant", slug="demo-tenant", serpapiKeyEnc="fernet-encrypted-value")
    )

    client = TestClient(app, base_url="https://testserver")
    return client, db, tenant


@pytest.fixture
def client_and_db(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "integration-test-jwt-secret-value-32-bytes-min")
    return _build_client()


def _headers(tenant_id: str, role: Role) -> dict:
    token = issue_access_token(str(ObjectId()), tenant_id, role)
    return {"Authorization": f"Bearer {token}"}


def _seed_owner(db, tenant_id: ObjectId, user_id: ObjectId) -> Membership:
    return MembershipsRepo(db).create(
        Membership(userId=user_id, tenantId=tenant_id, role=Role.OWNER)
    )


# Feature: aslinumber-p2-tenancy-brands, Property 11: Tenant settings
# never disclose the encrypted SerpApi key
def test_get_tenant_never_includes_serpapi_key(client_and_db) -> None:
    client, _db, tenant = client_and_db

    response = client.get("/tenant", headers=_headers(str(tenant.id), Role.VIEWER))

    assert response.status_code == 200
    assert "serpapiKeyEnc" not in response.json()["data"]


def test_patch_tenant_reflects_on_subsequent_get(client_and_db) -> None:
    """One example changing name and settings.locale, confirming both are

    reflected on a subsequent GET /tenant (task 11.3).
    """
    client, _db, tenant = client_and_db
    headers = _headers(str(tenant.id), Role.OWNER)

    patch_response = client.patch(
        "/tenant", json={"name": "Renamed Tenant", "settings": {"locale": "hi"}}, headers=headers
    )
    get_response = client.get("/tenant", headers=headers)

    assert patch_response.status_code == 200
    assert get_response.json()["data"]["name"] == "Renamed Tenant"
    assert get_response.json()["data"]["settings"]["locale"] == "hi"
    # publicMode was not part of the PATCH body and must be preserved.
    assert get_response.json()["data"]["settings"]["publicMode"] is True


def test_patch_tenant_as_admin_is_forbidden(client_and_db) -> None:
    client, _db, tenant = client_and_db

    response = client.patch(
        "/tenant", json={"name": "Hacked"}, headers=_headers(str(tenant.id), Role.ADMIN)
    )

    assert response.status_code == 403


def test_create_member_with_new_email_creates_user_and_membership(client_and_db) -> None:
    """One example: inviting a brand-new email creates a User plus a

    Membership (task 11.5).
    """
    client, db, tenant = client_and_db

    response = client.post(
        "/tenant/members",
        json={"email": "brand.new@example.com", "role": "viewer"},
        headers=_headers(str(tenant.id), Role.ADMIN),
    )

    assert response.status_code == 201
    assert response.json()["data"]["email"] == "brand.new@example.com"
    assert db["users"].find_one({"email": "brand.new@example.com"}) is not None


def test_create_member_with_existing_user_from_other_tenant_creates_only_membership(
    client_and_db,
) -> None:
    """One example: adding an existing user (from a second tenant) creates

    only a Membership, not a second User document (task 11.5).
    """
    client, db, tenant = client_and_db

    first = client.post(
        "/tenant/members",
        json={"email": "shared.user@example.com", "role": "viewer"},
        headers=_headers(str(tenant.id), Role.ADMIN),
    )
    assert first.status_code == 201

    other_tenant = TenantsRepo(db).create(Tenant(name="Other Tenant", slug="other-tenant"))
    second = client.post(
        "/tenant/members",
        json={"email": "shared.user@example.com", "role": "analyst"},
        headers=_headers(str(other_tenant.id), Role.ADMIN),
    )

    assert second.status_code == 201
    assert db["users"].count_documents({"email": "shared.user@example.com"}) == 1


def test_patch_member_role_ordinary_path_is_reflected(client_and_db) -> None:
    """One example for a non-owner target membership, confirming the role

    change is reflected (task 11.6).
    """
    client, db, tenant = client_and_db
    _seed_owner(db, tenant.id, ObjectId())
    headers = _headers(str(tenant.id), Role.ADMIN)
    created = client.post(
        "/tenant/members", json={"email": "member@example.com", "role": "viewer"}, headers=headers
    )
    membership_id = created.json()["data"]["id"]

    response = client.patch(
        f"/tenant/members/{membership_id}", json={"role": "analyst"}, headers=headers
    )

    assert response.status_code == 200
    assert response.json()["data"]["role"] == "analyst"


def test_delete_member_ordinary_path_is_reflected(client_and_db) -> None:
    """One example for a non-owner target membership, confirming removal

    is reflected (task 11.6).
    """
    client, db, tenant = client_and_db
    _seed_owner(db, tenant.id, ObjectId())
    headers = _headers(str(tenant.id), Role.ADMIN)
    created = client.post(
        "/tenant/members", json={"email": "member2@example.com", "role": "viewer"}, headers=headers
    )
    membership_id = created.json()["data"]["id"]

    response = client.delete(f"/tenant/members/{membership_id}", headers=headers)

    assert response.status_code == 204
    assert MembershipsRepo(db).find_by_id(tenant.id, membership_id) is None


def test_admin_cannot_modify_owner_membership(client_and_db) -> None:
    client, db, tenant = client_and_db
    owner_membership = _seed_owner(db, tenant.id, ObjectId())

    response = client.patch(
        f"/tenant/members/{owner_membership.id}",
        json={"role": "admin"},
        headers=_headers(str(tenant.id), Role.ADMIN),
    )

    assert response.status_code == 403


def test_removing_the_last_owner_is_rejected(client_and_db) -> None:
    client, db, tenant = client_and_db
    owner_membership = _seed_owner(db, tenant.id, ObjectId())

    response = client.delete(
        f"/tenant/members/{owner_membership.id}", headers=_headers(str(tenant.id), Role.OWNER)
    )

    assert response.status_code == 409


def test_patch_unknown_membership_is_not_found(client_and_db) -> None:
    client, _db, tenant = client_and_db

    response = client.patch(
        f"/tenant/members/{ObjectId()}",
        json={"role": "admin"},
        headers=_headers(str(tenant.id), Role.ADMIN),
    )

    assert response.status_code == 404
