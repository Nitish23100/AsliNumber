"""Integration tests for `app.api.routers.audit` via a TestClient."""

import mongomock
import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from app.auth.tokens import issue_access_token
from app.config import Settings
from app.main import create_app
from app.models.audit_log_entry import AuditTarget
from app.models.role import Role
from app.repos import create_indexes
from app.repos.audit_log_repo import AuditLogRepo


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


def _headers(tenant_id: str, role: Role) -> dict:
    token = issue_access_token(str(ObjectId()), tenant_id, role)
    return {"Authorization": f"Bearer {token}"}


def test_list_audit_log_scoped_to_tenant(client_and_db) -> None:
    client, db = client_and_db
    tenant_a, tenant_b = ObjectId(), ObjectId()
    repo = AuditLogRepo(db)
    repo.write_entry(tenant_a, ObjectId(), "brand_created", AuditTarget(type="brand", id="x"), "h1")
    repo.write_entry(tenant_b, ObjectId(), "brand_created", AuditTarget(type="brand", id="y"), "h2")

    response = client.get("/audit-log", headers=_headers(str(tenant_a), Role.ADMIN))

    assert response.status_code == 200
    assert len(response.json()["data"]) == 1


def test_list_audit_log_filterable_by_action(client_and_db) -> None:
    client, db = client_and_db
    tenant_id = ObjectId()
    repo = AuditLogRepo(db)
    repo.write_entry(
        tenant_id, ObjectId(), "brand_created", AuditTarget(type="brand", id="x"), "h1"
    )
    repo.write_entry(
        tenant_id, ObjectId(), "brand_updated", AuditTarget(type="brand", id="x"), "h2"
    )

    response = client.get(
        "/audit-log",
        params={"action": "brand_updated"},
        headers=_headers(str(tenant_id), Role.ADMIN),
    )

    assert response.status_code == 200
    assert len(response.json()["data"]) == 1
    assert response.json()["data"][0]["action"] == "brand_updated"


def test_list_audit_log_as_viewer_is_forbidden(client_and_db) -> None:
    client, _db = client_and_db
    tenant_id = ObjectId()

    response = client.get("/audit-log", headers=_headers(str(tenant_id), Role.VIEWER))

    assert response.status_code == 403
