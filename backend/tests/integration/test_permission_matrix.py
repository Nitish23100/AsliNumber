"""Permission_Matrix_Harness (task 15.1).

For every entry in ROUTE_TABLE and every Role, asserts the response
accepts (status < 400) if and only if the requester role's rank is at or
above the route's configured minimum role's rank -- otherwise asserts a
403.

Feature: aslinumber-p2-tenancy-brands, Property 17: RBAC rank enforcement
is total across the route table.
Validates: Requirements 10.1, 10.2, 10.3, 10.4, 10.5.
"""

import itertools

import mongomock
import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from app.api.route_table import ROUTE_TABLE
from app.auth.tokens import issue_access_token
from app.config import Settings
from app.main import create_app
from app.models.membership import Membership
from app.models.role import Role
from app.models.tenant import Tenant
from app.repos import create_indexes
from app.repos.memberships_repo import MembershipsRepo
from app.repos.tenants_repo import TenantsRepo

_counter = itertools.count()


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
def harness_env(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "integration-test-jwt-secret-value-32-bytes-min")
    return _build_client()


def _seed_tenant_resources(db) -> dict:
    """Build one fresh tenant with a brand, an official contact, an owner

    membership (so the last-owner rule never blocks a sample mutation),
    and a non-owner membership -- everything every route's sample_request
    factory in this phase might need, keyed by the ctx names each
    router's factories expect.
    """
    tenant_id = ObjectId()
    n = next(_counter)
    TenantsRepo(db).create(Tenant(id=tenant_id, name=f"Tenant {n}", slug=f"tenant-{n}"))
    MembershipsRepo(db).create(Membership(userId=ObjectId(), tenantId=tenant_id, role=Role.OWNER))
    non_owner_membership = MembershipsRepo(db).create(
        Membership(userId=ObjectId(), tenantId=tenant_id, role=Role.VIEWER)
    )

    brand_doc = {
        "_id": ObjectId(),
        "tenantId": tenant_id,
        "slug": f"brand-{n}",
        "displayName": f"Brand {n}",
        "category": "ecommerce",
        "group": None,
        "aliases": [{"text": "B", "lang": "en", "script": "latin", "kind": "legal"}],
        "officialDomains": [
            {
                "domain": f"brand{n}.test",
                "verifiedBy": "tester",
                "verifiedAt": "2024-01-01T00:00:00Z",
            }
        ],
        "publicLookup": False,
        "active": True,
        "version": 1,
    }
    db["brands"].insert_one(brand_doc)

    contact_doc = {
        "_id": ObjectId(),
        "tenantId": tenant_id,
        "brandId": brand_doc["_id"],
        "e164": f"+9198{n:08d}",
        "display": "Support",
        "contactTypes": ["support"],
        "scope": None,
        "authority": "supporting",
        "method": "manual",
        "source": {"url": "https://e.test", "registeredDomain": "e.test"},
        "retrievedAt": "2024-01-01T00:00:00Z",
        "status": "active",
        "validFrom": "2024-01-01T00:00:00Z",
        "validTo": None,
    }
    db["official_contacts"].insert_one(contact_doc)

    return {
        "tenant_id": tenant_id,
        "brand_id": str(brand_doc["_id"]),
        "contact_id": str(contact_doc["_id"]),
        "non_owner_membership_id": str(non_owner_membership.id),
        "unique_slug": lambda: f"slug-{next(_counter)}",
        "unique_e164": lambda: f"+9199{next(_counter):08d}",
        "unique_email": lambda: f"member-{next(_counter)}@example.com",
    }


@pytest.mark.parametrize("entry", ROUTE_TABLE, ids=lambda e: f"{e.method}_{e.path_template}")
@pytest.mark.parametrize("role", list(Role), ids=lambda r: r.value)
def test_permission_matrix(harness_env, entry, role) -> None:
    client, db = harness_env
    ctx = _seed_tenant_resources(db)

    path_params, body = entry.sample_request(ctx)
    path = entry.path_template.format(**path_params)
    token = issue_access_token(str(ObjectId()), str(ctx["tenant_id"]), role)
    headers = {"Authorization": f"Bearer {token}"}

    response = client.request(entry.method, path, json=body, headers=headers)

    should_accept = role.rank >= entry.minimum_role.rank
    if should_accept:
        assert response.status_code < 400, (
            f"{entry.method} {entry.path_template} with role={role.value} (>= minimum "
            f"{entry.minimum_role.value}) expected acceptance, got {response.status_code}: "
            f"{response.text}"
        )
    else:
        assert response.status_code == 403, (
            f"{entry.method} {entry.path_template} with role={role.value} (< minimum "
            f"{entry.minimum_role.value}) expected 403, got {response.status_code}: {response.text}"
        )
