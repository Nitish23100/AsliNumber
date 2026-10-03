"""Property-based test for brand version monotonic increment (Property 6).

Validates: Requirements 3.5.
"""

from datetime import UTC, datetime

import mongomock
from bson import ObjectId
from hypothesis import given, settings
from hypothesis import strategies as st

from app.models.brand import Alias, Brand, OfficialDomain
from app.repos import create_indexes
from app.repos.brands_repo import BrandsRepo


def _fresh_db():
    client = mongomock.MongoClient("mongodb://localhost:27017/aslinumber_test", tz_aware=True)
    db = client.get_default_database()
    create_indexes(db)
    return db


def _make_brand(tenant_id: ObjectId) -> Brand:
    return Brand(
        tenantId=tenant_id,
        slug="examplekart",
        displayName="ExampleKart",
        category="ecommerce",
        aliases=[Alias(text="ExampleKart", lang="en", script="latin", kind="legal")],
        officialDomains=[
            OfficialDomain(
                domain="examplekart.test", verifiedBy="admin", verifiedAt=datetime.now(UTC)
            )
        ],
    )


# Feature: aslinumber-p2-tenancy-brands, Property 6: Version increments
# monotonically with accepted updates
@settings(max_examples=100)
@given(num_updates=st.integers(min_value=0, max_value=20))
def test_version_increments_by_exactly_n_after_n_updates(num_updates: int) -> None:
    """For a brand starting at version 1, N consecutively accepted PATCH

    requests result in version == 1 + N.
    """
    db = _fresh_db()
    repo = BrandsRepo(db)
    created = repo.create(_make_brand(ObjectId()))
    assert created.version == 1

    current_id = created.id
    tenant_id = created.tenantId
    for i in range(num_updates):
        updated = repo.update(tenant_id, current_id, {"displayName": f"ExampleKart v{i}"})
        assert updated is not None

    final = repo.find_by_id(tenant_id, current_id)
    assert final.version == 1 + num_updates
