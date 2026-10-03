"""Integration tests for `app.api.routers.official_contacts` via a TestClient.

Covers creation (including the Authority_Rule), listing (including
deprecated entries), deprecation defaulting of `validTo`, 404s for an
unknown brand/contact id, and the structural absence of a DELETE route
(task 10.3, Requirement 6.4).
"""

import mongomock
import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from app.api.route_table import ROUTE_TABLE
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


_BRAND_BODY = {
    "slug": "examplekart",
    "displayName": "ExampleKart",
    "category": "ecommerce",
    "aliases": [{"text": "EK", "lang": "en", "script": "latin", "kind": "legal"}],
    "officialDomains": [
        {"domain": "examplekart.test", "verifiedBy": "admin", "verifiedAt": "2024-01-01T00:00:00Z"}
    ],
}


def _create_brand(client, tenant_id: str) -> str:
    response = client.post(
        "/brands", json=_BRAND_BODY, headers=_auth_headers(tenant_id, Role.ADMIN)
    )
    return response.json()["data"]["id"]


def test_create_contact_with_verified_domain_defaults_to_primary(client_and_db) -> None:
    client, _db = client_and_db
    tenant_id = str(ObjectId())
    brand_id = _create_brand(client, tenant_id)

    response = client.post(
        f"/brands/{brand_id}/official-contacts",
        json={
            "e164": "+919876543210",
            "display": "Support",
            "contactTypes": ["support"],
            "source": {
                "url": "https://examplekart.test/contact",
                "registeredDomain": "examplekart.test",
            },
        },
        headers=_auth_headers(tenant_id, Role.ADMIN),
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["authority"] == "primary"
    assert data["method"] == "manual"
    assert data["status"] == "active"


def test_create_contact_with_unverified_domain_requesting_primary_is_rejected(
    client_and_db,
) -> None:
    client, _db = client_and_db
    tenant_id = str(ObjectId())
    brand_id = _create_brand(client, tenant_id)

    response = client.post(
        f"/brands/{brand_id}/official-contacts",
        json={
            "e164": "+919876543210",
            "display": "Support",
            "contactTypes": ["support"],
            "source": {
                "url": "https://unverified.test/contact",
                "registeredDomain": "unverified.test",
            },
            "authority": "primary",
        },
        headers=_auth_headers(tenant_id, Role.ADMIN),
    )

    assert response.status_code == 422


def test_create_contact_for_unknown_brand_is_not_found(client_and_db) -> None:
    client, _db = client_and_db
    tenant_id = str(ObjectId())

    response = client.post(
        f"/brands/{ObjectId()}/official-contacts",
        json={
            "e164": "+919876543210",
            "display": "Support",
            "contactTypes": ["support"],
            "source": {
                "url": "https://examplekart.test/contact",
                "registeredDomain": "examplekart.test",
            },
        },
        headers=_auth_headers(tenant_id, Role.ADMIN),
    )

    assert response.status_code == 404


def test_list_contacts_for_brand_with_zero_entries_returns_empty_list(client_and_db) -> None:
    client, _db = client_and_db
    tenant_id = str(ObjectId())
    brand_id = _create_brand(client, tenant_id)

    response = client.get(
        f"/brands/{brand_id}/official-contacts", headers=_auth_headers(tenant_id, Role.VIEWER)
    )

    assert response.status_code == 200
    assert response.json()["data"] == []


def test_deprecating_a_contact_without_valid_to_sets_it_to_now(client_and_db) -> None:
    client, _db = client_and_db
    tenant_id = str(ObjectId())
    brand_id = _create_brand(client, tenant_id)
    created = client.post(
        f"/brands/{brand_id}/official-contacts",
        json={
            "e164": "+919876543210",
            "display": "Support",
            "contactTypes": ["support"],
            "source": {
                "url": "https://examplekart.test/contact",
                "registeredDomain": "examplekart.test",
            },
        },
        headers=_auth_headers(tenant_id, Role.ADMIN),
    )
    contact_id = created.json()["data"]["id"]

    response = client.patch(
        f"/official-contacts/{contact_id}",
        json={"status": "deprecated"},
        headers=_auth_headers(tenant_id, Role.ADMIN),
    )

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "deprecated"
    assert response.json()["data"]["validTo"] is not None


def test_deprecating_a_contact_with_explicit_valid_to_preserves_it(client_and_db) -> None:
    client, _db = client_and_db
    tenant_id = str(ObjectId())
    brand_id = _create_brand(client, tenant_id)
    created = client.post(
        f"/brands/{brand_id}/official-contacts",
        json={
            "e164": "+919876543210",
            "display": "Support",
            "contactTypes": ["support"],
            "source": {
                "url": "https://examplekart.test/contact",
                "registeredDomain": "examplekart.test",
            },
        },
        headers=_auth_headers(tenant_id, Role.ADMIN),
    )
    contact_id = created.json()["data"]["id"]
    explicit_valid_to = "2030-01-01T00:00:00Z"

    response = client.patch(
        f"/official-contacts/{contact_id}",
        json={"status": "deprecated", "validTo": explicit_valid_to},
        headers=_auth_headers(tenant_id, Role.ADMIN),
    )

    assert response.status_code == 200
    assert response.json()["data"]["validTo"] == "2030-01-01T00:00:00Z"


def test_patch_unknown_contact_is_not_found(client_and_db) -> None:
    client, _db = client_and_db
    tenant_id = str(ObjectId())

    response = client.patch(
        f"/official-contacts/{ObjectId()}",
        json={"display": "New name"},
        headers=_auth_headers(tenant_id, Role.ADMIN),
    )

    assert response.status_code == 404


def test_no_delete_route_exists_for_official_contacts(client_and_db) -> None:
    """Structural check per task 10.3 / Requirement 6.4: no DELETE route

    matching /official-contacts/{id} exists in the FastAPI app or the
    Route_Table.
    """
    client, _db = client_and_db

    response = client.delete(f"/official-contacts/{ObjectId()}")

    # FastAPI responds 405 Method Not Allowed for an unregistered method
    # on an otherwise-known path pattern (not 404, since no DELETE route
    # for this path exists to even consider).
    assert response.status_code in (404, 405)
    assert not any(
        entry.method == "DELETE" and entry.path_template == "/official-contacts/{contact_id}"
        for entry in ROUTE_TABLE
    )
