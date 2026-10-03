"""Integration tests for `app.repos.brands_repo`.

Covers the create+find round trip, the unique-per-tenant slug index,
pagination, version-incrementing updates, and cross-tenant scoping.
Runs against the in-memory `mongomock` database fixture (see
`conftest.py` for why).
"""

from datetime import UTC, datetime

import pytest
from bson import ObjectId
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from app.models.brand import Alias, Brand, OfficialDomain
from app.repos.brands_repo import BrandsRepo


def _make_brand(tenant_id: ObjectId, slug: str = "examplekart") -> Brand:
    return Brand(
        tenantId=tenant_id,
        slug=slug,
        displayName="ExampleKart",
        category="ecommerce",
        aliases=[Alias(text="ExampleKart", lang="en", script="latin", kind="legal")],
        officialDomains=[
            OfficialDomain(
                domain="examplekart.test", verifiedBy="admin", verifiedAt=datetime.now(UTC)
            )
        ],
    )


def test_create_and_find_by_slug_round_trip(db: Database) -> None:
    repo = BrandsRepo(db)
    tenant_id = ObjectId()

    created = repo.create(_make_brand(tenant_id))
    found = repo.find_by_slug(tenant_id, "examplekart")

    assert found is not None
    assert found.id == created.id
    assert found.displayName == "ExampleKart"


def test_find_by_id_scoped_by_tenant(db: Database) -> None:
    repo = BrandsRepo(db)
    tenant_id = ObjectId()
    created = repo.create(_make_brand(tenant_id))

    found = repo.find_by_id(tenant_id, created.id)
    not_found = repo.find_by_id(ObjectId(), created.id)

    assert found is not None
    assert found.id == created.id
    assert not_found is None


def test_duplicate_slug_within_same_tenant_raises(db: Database) -> None:
    repo = BrandsRepo(db)
    tenant_id = ObjectId()
    repo.create(_make_brand(tenant_id, slug="examplekart"))

    with pytest.raises(DuplicateKeyError):
        repo.create(_make_brand(tenant_id, slug="examplekart"))


def test_same_slug_in_different_tenants_succeeds_independently(db: Database) -> None:
    repo = BrandsRepo(db)
    tenant_a, tenant_b = ObjectId(), ObjectId()

    created_a = repo.create(_make_brand(tenant_a, slug="examplekart"))
    created_b = repo.create(_make_brand(tenant_b, slug="examplekart"))

    assert created_a.id != created_b.id
    assert repo.find_by_slug(tenant_a, "examplekart") is not None
    assert repo.find_by_slug(tenant_b, "examplekart") is not None


def test_update_increments_version(db: Database) -> None:
    repo = BrandsRepo(db)
    tenant_id = ObjectId()
    created = repo.create(_make_brand(tenant_id))
    assert created.version == 1

    updated = repo.update(tenant_id, created.id, {"displayName": "ExampleKart Ltd"})

    assert updated.version == 2
    assert updated.displayName == "ExampleKart Ltd"


def test_update_scoped_by_tenant_returns_none_for_other_tenant(db: Database) -> None:
    repo = BrandsRepo(db)
    tenant_id = ObjectId()
    created = repo.create(_make_brand(tenant_id))

    result = repo.update(ObjectId(), created.id, {"displayName": "Hijacked"})

    assert result is None


def test_list_by_tenant_only_returns_that_tenants_brands(db: Database) -> None:
    repo = BrandsRepo(db)
    tenant_a, tenant_b = ObjectId(), ObjectId()
    repo.create(_make_brand(tenant_a, slug="brand-a"))
    repo.create(_make_brand(tenant_b, slug="brand-b"))

    results_a = repo.list_by_tenant(tenant_a)

    assert len(results_a) == 1
    assert results_a[0].slug == "brand-a"


def test_list_by_tenant_respects_max_page_size(db: Database) -> None:
    repo = BrandsRepo(db)
    tenant_id = ObjectId()
    for i in range(5):
        repo.create(_make_brand(tenant_id, slug=f"brand-{i}"))

    results = repo.list_by_tenant(tenant_id, limit=1000)

    # Clamped to MAX_PAGE_SIZE (200), but we only created 5, so this just
    # confirms the clamp doesn't somehow truncate below what exists.
    assert len(results) == 5


def test_count_official_contacts_reflects_actual_count(db: Database) -> None:
    repo = BrandsRepo(db)
    tenant_id = ObjectId()
    created = repo.create(_make_brand(tenant_id))

    assert repo.count_official_contacts(tenant_id, created.id) == 0

    db["official_contacts"].insert_many(
        [
            {"tenantId": tenant_id, "brandId": created.id, "e164": "+919000000001"},
            {"tenantId": tenant_id, "brandId": created.id, "e164": "+919000000002"},
        ]
    )

    assert repo.count_official_contacts(tenant_id, created.id) == 2
