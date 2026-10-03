"""Integration tests for `app.repos.official_contacts_repo`.

Covers the create+find round trip, the unique
(tenantId, brandId, e164) index, listing including deprecated entries,
and the structural absence of a delete method.
"""

from datetime import UTC, datetime

import pytest
from bson import ObjectId
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from app.models.brand import Authority, ContactMethod, ContactStatus
from app.models.official_contact import ContactSource, OfficialContact
from app.repos.official_contacts_repo import OfficialContactsRepo


def _make_contact(
    tenant_id: ObjectId, brand_id: ObjectId, e164: str = "+919876543210"
) -> OfficialContact:
    return OfficialContact(
        tenantId=tenant_id,
        brandId=brand_id,
        e164=e164,
        display=e164,
        contactTypes=["customer_care"],
        authority=Authority.SUPPORTING,
        method=ContactMethod.MANUAL,
        source=ContactSource(url="https://examplekart.test", registeredDomain="examplekart.test"),
        retrievedAt=datetime.now(UTC),
        validFrom=datetime.now(UTC),
    )


def test_create_and_find_by_id_round_trip(db: Database) -> None:
    repo = OfficialContactsRepo(db)
    tenant_id, brand_id = ObjectId(), ObjectId()

    created = repo.create(_make_contact(tenant_id, brand_id))
    found = repo.find_by_id(tenant_id, created.id)

    assert found is not None
    assert found.e164 == "+919876543210"


def test_find_by_id_scoped_by_tenant(db: Database) -> None:
    repo = OfficialContactsRepo(db)
    tenant_id, brand_id = ObjectId(), ObjectId()
    created = repo.create(_make_contact(tenant_id, brand_id))

    not_found = repo.find_by_id(ObjectId(), created.id)

    assert not_found is None


def test_duplicate_e164_for_same_brand_and_tenant_raises(db: Database) -> None:
    repo = OfficialContactsRepo(db)
    tenant_id, brand_id = ObjectId(), ObjectId()
    repo.create(_make_contact(tenant_id, brand_id, e164="+919876543210"))

    with pytest.raises(DuplicateKeyError):
        repo.create(_make_contact(tenant_id, brand_id, e164="+919876543210"))


def test_same_e164_for_different_brand_succeeds(db: Database) -> None:
    repo = OfficialContactsRepo(db)
    tenant_id = ObjectId()
    repo.create(_make_contact(tenant_id, ObjectId(), e164="+919876543210"))

    # Same number, different brand (shared call centre case) -- allowed
    # at the repository/index level; the group-handling de-duplication
    # logic for reuse detection belongs to a much later phase (P8), not P2.
    created = repo.create(_make_contact(tenant_id, ObjectId(), e164="+919876543210"))

    assert created.e164 == "+919876543210"


def test_list_by_brand_includes_deprecated_entries(db: Database) -> None:
    repo = OfficialContactsRepo(db)
    tenant_id, brand_id = ObjectId(), ObjectId()
    active = repo.create(_make_contact(tenant_id, brand_id, e164="+919876543210"))
    deprecated = repo.create(_make_contact(tenant_id, brand_id, e164="+919876543211"))
    repo.update(tenant_id, deprecated.id, {"status": ContactStatus.DEPRECATED.value})

    results = repo.list_by_brand(tenant_id, brand_id)

    assert len(results) == 2
    statuses = {str(r.id): r.status for r in results}
    assert statuses[str(active.id)] == ContactStatus.ACTIVE
    assert statuses[str(deprecated.id)] == ContactStatus.DEPRECATED


def test_update_scoped_by_tenant_returns_none_for_other_tenant(db: Database) -> None:
    repo = OfficialContactsRepo(db)
    tenant_id, brand_id = ObjectId(), ObjectId()
    created = repo.create(_make_contact(tenant_id, brand_id))

    result = repo.update(ObjectId(), created.id, {"display": "Hijacked"})

    assert result is None


def test_no_delete_method_exists() -> None:
    """Structural check: a hard delete is unreachable from this repository."""
    assert not hasattr(OfficialContactsRepo, "delete")
