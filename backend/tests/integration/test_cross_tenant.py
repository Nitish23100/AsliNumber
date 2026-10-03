"""Cross_Tenant_Harness (task 15.2).

For every ROUTE_TABLE entry that carries a `resource_kind`, creates that
resource in tenant A, authenticates as a member of tenant B, and asserts
the response is HTTP 404 -- a cross-tenant resource reference is
indistinguishable from the resource simply not existing.

Feature: aslinumber-p2-tenancy-brands, Property 18: Cross-tenant resource
references are indistinguishable from absence.
Validates: Requirements 11.1, 11.2, 11.3, 11.4.
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

_RESOURCE_ADDRESSING_ROUTES = [entry for entry in ROUTE_TABLE if entry.resource_kind is not None]


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


def _seed_tenant_with_resources(db) -> dict:
    """Build one fresh tenant (tenant A) with a brand, an official

    contact, and a non-owner membership -- every resource kind the
    ROUTE_TABLE's resource-addressing routes might reference.
    """
    tenant_id = ObjectId()
    n = next(_counter)
    TenantsRepo(db).create(Tenant(id=tenant_id, name=f"Tenant A{n}", slug=f"tenant-a-{n}"))
    MembershipsRepo(db).create(Membership(userId=ObjectId(), tenantId=tenant_id, role=Role.OWNER))
    non_owner_membership = MembershipsRepo(db).create(
        Membership(userId=ObjectId(), tenantId=tenant_id, role=Role.VIEWER)
    )

    brand_doc = {
        "_id": ObjectId(),
        "tenantId": tenant_id,
        "slug": f"brand-a-{n}",
        "displayName": f"Brand A{n}",
        "category": "ecommerce",
        "group": None,
        "aliases": [{"text": "B", "lang": "en", "script": "latin", "kind": "legal"}],
        "officialDomains": [
            {
                "domain": f"brand-a-{n}.test",
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
        "e164": f"+9197{n:08d}",
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

    resource_ids = {
        "brand": str(brand_doc["_id"]),
        "official_contact": str(contact_doc["_id"]),
        "membership": str(non_owner_membership.id),
    }

    ctx = {
        "tenant_id": tenant_id,
        "brand_id": resource_ids["brand"],
        "contact_id": resource_ids["official_contact"],
        "non_owner_membership_id": resource_ids["membership"],
        "unique_slug": lambda: f"slug-{next(_counter)}",
        "unique_e164": lambda: f"+9196{next(_counter):08d}",
        "unique_email": lambda: f"member-{next(_counter)}@example.com",
    }
    return ctx, resource_ids


@pytest.mark.parametrize(
    "entry", _RESOURCE_ADDRESSING_ROUTES, ids=lambda e: f"{e.method}_{e.path_template}"
)
def test_cross_tenant_resource_reference_is_not_found(harness_env, entry) -> None:
    client, db = harness_env
    ctx_a, _resource_ids = _seed_tenant_with_resources(db)

    # Tenant B: a separate tenant with its own owner membership, whose
    # member will authenticate and attempt to reach tenant A's resource.
    tenant_b_id = ObjectId()
    n = next(_counter)
    TenantsRepo(db).create(Tenant(id=tenant_b_id, name=f"Tenant B{n}", slug=f"tenant-b-{n}"))
    MembershipsRepo(db).create(Membership(userId=ObjectId(), tenantId=tenant_b_id, role=Role.OWNER))

    path_params, body = entry.sample_request(ctx_a)
    path = entry.path_template.format(**path_params)

    # Use the route's own configured minimum role so the request clears
    # the RBAC check and the only remaining reason for rejection is the
    # cross-tenant resource reference itself.
    token = issue_access_token(str(ObjectId()), str(tenant_b_id), entry.minimum_role)
    headers = {"Authorization": f"Bearer {token}"}

    response = client.request(entry.method, path, json=body, headers=headers)

    assert response.status_code == 404, (
        f"{entry.method} {entry.path_template} referencing a tenant-A resource from a "
        f"tenant-B requester expected 404, got {response.status_code}: {response.text}"
    )
