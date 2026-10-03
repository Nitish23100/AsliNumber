"""Property-based test for non-empty alias/domain requirements (Property 4).

Validates: Requirements 2.3, 2.4, 2.6.
"""

from datetime import UTC, datetime

import mongomock
from bson import ObjectId
from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.errors import AppError, ErrorCode
from app.models.brand import Alias, Brand, OfficialDomain
from app.repos import create_indexes
from app.repos.brands_repo import BrandsRepo
from app.services.brand_service import validate_brand_create


def _fresh_db():
    client = mongomock.MongoClient("mongodb://localhost:27017/aslinumber_test", tz_aware=True)
    db = client.get_default_database()
    create_indexes(db)
    return db


def _make_brand(tenant_id: ObjectId, slug: str, num_aliases: int, num_domains: int) -> Brand:
    return Brand(
        tenantId=tenant_id,
        slug=slug,
        displayName="ExampleKart",
        category="ecommerce",
        aliases=[
            Alias(text=f"Alias{i}", lang="en", script="latin", kind="legal")
            for i in range(num_aliases)
        ],
        officialDomains=[
            OfficialDomain(
                domain=f"examplekart{i}.test", verifiedBy="admin", verifiedAt=datetime.now(UTC)
            )
            for i in range(num_domains)
        ],
    )


# Feature: aslinumber-p2-tenancy-brands, Property 4: Non-empty alias and
# domain lists are required for creation
@settings(max_examples=100)
@given(
    num_aliases=st.integers(min_value=0, max_value=5),
    num_domains=st.integers(min_value=0, max_value=5),
)
def test_empty_aliases_or_domains_reject_otherwise_valid_creation(
    num_aliases: int, num_domains: int
) -> None:
    """A brand-creation payload is rejected with HTTP 422 whenever

    aliases is empty or officialDomains is empty; when every rule is
    satisfied, creation succeeds with version == 1.
    """
    db = _fresh_db()
    repo = BrandsRepo(db)
    tenant_id = ObjectId()
    brand = _make_brand(tenant_id, "examplekart", num_aliases, num_domains)

    if num_aliases == 0 or num_domains == 0:
        try:
            validate_brand_create(tenant_id, brand, repo)
            raised = False
        except AppError as exc:
            raised = True
            assert exc.code == ErrorCode.VALIDATION_ERROR
            assert exc.status_code == 422
        assert raised
    else:
        validate_brand_create(tenant_id, brand, repo)  # must not raise
        created = repo.create(brand)
        assert created.version == 1
