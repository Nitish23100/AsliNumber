"""Property-based test for tenant-scoped list fidelity (Property 9).

Validates: Requirements 3.1, 6.1, 6.2, 8.1.
"""

from datetime import UTC, datetime

import mongomock
from bson import ObjectId
from hypothesis import given, settings
from hypothesis import strategies as st

from app.models.brand import Alias, Brand, OfficialDomain
from app.repos import create_indexes
from app.repos.brands_repo import MAX_PAGE_SIZE, BrandsRepo


def _fresh_db():
    client = mongomock.MongoClient("mongodb://localhost:27017/aslinumber_test", tz_aware=True)
    db = client.get_default_database()
    create_indexes(db)
    return db


def _make_brand(tenant_id: ObjectId, slug: str) -> Brand:
    return Brand(
        tenantId=tenant_id,
        slug=slug,
        displayName=slug,
        category="ecommerce",
        aliases=[Alias(text=slug, lang="en", script="latin", kind="legal")],
        officialDomains=[
            OfficialDomain(domain=f"{slug}.test", verifiedBy="admin", verifiedAt=datetime.now(UTC))
        ],
    )


# Feature: aslinumber-p2-tenancy-brands, Property 9: Tenant-scoped list
# endpoints reflect exactly what exists, within pagination bounds
@settings(max_examples=50)
@given(
    count_a=st.integers(min_value=0, max_value=10),
    count_b=st.integers(min_value=0, max_value=10),
)
def test_brands_list_returns_exactly_this_tenants_brands(count_a: int, count_b: int) -> None:
    """For any set of brands created in two tenants, GET-equivalent

    listing for tenant A returns exactly tenant A's brands -- never
    fewer, never tenant B's.
    """
    db = _fresh_db()
    repo = BrandsRepo(db)
    tenant_a, tenant_b = ObjectId(), ObjectId()

    for i in range(count_a):
        repo.create(_make_brand(tenant_a, f"brand-a-{i}"))
    for i in range(count_b):
        repo.create(_make_brand(tenant_b, f"brand-b-{i}"))

    results_a = repo.list_by_tenant(tenant_a, limit=MAX_PAGE_SIZE)

    assert len(results_a) == count_a
    assert all(b.tenantId == tenant_a for b in results_a)


# Feature: aslinumber-p2-tenancy-brands, Property 9: Tenant-scoped list
# endpoints reflect exactly what exists, within pagination bounds
@settings(max_examples=50)
@given(requested_limit=st.integers(min_value=1, max_value=500))
def test_page_size_never_exceeds_max_page_size(requested_limit: int) -> None:
    """The number of items returned per page never exceeds the lesser of

    the requested page size and MAX_PAGE_SIZE (200).
    """
    db = _fresh_db()
    repo = BrandsRepo(db)
    tenant_id = ObjectId()
    # Create more brands than any reasonable page size, so the clamp (not
    # a lack of data) is what's actually being exercised.
    for i in range(min(requested_limit, MAX_PAGE_SIZE) + 5):
        repo.create(_make_brand(tenant_id, f"brand-{i}"))

    results = repo.list_by_tenant(tenant_id, limit=requested_limit)

    assert len(results) <= min(requested_limit, MAX_PAGE_SIZE)
