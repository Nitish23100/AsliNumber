"""Integration tests for `app.repos.audit_log_repo`.

Covers write+list, filtering by action/userId/target.id, tenant
scoping, and the hash_client_ip helper's non-disclosure of the raw IP.
"""

from bson import ObjectId
from pymongo.database import Database

from app.models.audit_log_entry import AuditTarget
from app.repos.audit_log_repo import AuditLogRepo, hash_client_ip


def test_write_entry_and_list_by_tenant_round_trip(db: Database) -> None:
    repo = AuditLogRepo(db)
    tenant_id, user_id = ObjectId(), ObjectId()

    repo.write_entry(
        tenant_id,
        user_id,
        "brand_created",
        AuditTarget(type="brand", id=str(ObjectId())),
        "iphash1",
    )

    results = repo.list_by_tenant(tenant_id)

    assert len(results) == 1
    assert results[0].action == "brand_created"


def test_list_by_tenant_scoped_to_that_tenant_only(db: Database) -> None:
    repo = AuditLogRepo(db)
    tenant_a, tenant_b = ObjectId(), ObjectId()
    repo.write_entry(tenant_a, ObjectId(), "brand_created", AuditTarget(type="brand", id="x"), "h1")
    repo.write_entry(tenant_b, ObjectId(), "brand_created", AuditTarget(type="brand", id="y"), "h2")

    results_a = repo.list_by_tenant(tenant_a)

    assert len(results_a) == 1
    assert results_a[0].target.id == "x"


def test_filter_by_action(db: Database) -> None:
    repo = AuditLogRepo(db)
    tenant_id = ObjectId()
    repo.write_entry(
        tenant_id, ObjectId(), "brand_created", AuditTarget(type="brand", id="x"), "h1"
    )
    repo.write_entry(
        tenant_id, ObjectId(), "brand_updated", AuditTarget(type="brand", id="x"), "h2"
    )

    results = repo.list_by_tenant(tenant_id, action="brand_updated")

    assert len(results) == 1
    assert results[0].action == "brand_updated"


def test_filter_by_user_id(db: Database) -> None:
    repo = AuditLogRepo(db)
    tenant_id = ObjectId()
    user_a, user_b = ObjectId(), ObjectId()
    repo.write_entry(tenant_id, user_a, "brand_created", AuditTarget(type="brand", id="x"), "h1")
    repo.write_entry(tenant_id, user_b, "brand_created", AuditTarget(type="brand", id="y"), "h2")

    results = repo.list_by_tenant(tenant_id, user_id=user_a)

    assert len(results) == 1
    assert results[0].userId == user_a


def test_filter_by_target_id(db: Database) -> None:
    repo = AuditLogRepo(db)
    tenant_id = ObjectId()
    repo.write_entry(
        tenant_id, ObjectId(), "brand_created", AuditTarget(type="brand", id="x"), "h1"
    )
    repo.write_entry(
        tenant_id, ObjectId(), "brand_created", AuditTarget(type="brand", id="y"), "h2"
    )

    results = repo.list_by_tenant(tenant_id, target_id="y")

    assert len(results) == 1
    assert results[0].target.id == "y"


def test_entries_are_never_updated_or_deleted() -> None:
    """Structural check: no update/delete method exists on this repository."""
    assert not hasattr(AuditLogRepo, "update")
    assert not hasattr(AuditLogRepo, "delete")


def test_hash_client_ip_never_discloses_the_raw_ip() -> None:
    salt, ip = "some-secret-salt", "203.0.113.42"

    hashed = hash_client_ip(salt, ip)

    assert hashed != ip
    assert ip not in hashed


def test_hash_client_ip_is_deterministic() -> None:
    salt, ip = "some-secret-salt", "203.0.113.42"

    first = hash_client_ip(salt, ip)
    second = hash_client_ip(salt, ip)

    assert first == second
