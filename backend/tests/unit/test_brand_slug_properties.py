"""Property-based tests for brand slug format and uniqueness (Properties 1, 2).

Validates: Requirements 2.1, 2.2.
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
from app.services.brand_service import SLUG_PATTERN, validate_brand_create, validate_slug


def _fresh_db():
    client = mongomock.MongoClient("mongodb://localhost:27017/aslinumber_test", tz_aware=True)
    db = client.get_default_database()
    create_indexes(db)
    return db


def _make_brand(tenant_id: ObjectId, slug: str) -> Brand:
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


# Valid slugs: 2-40 chars from [a-z0-9-].
_valid_slug = st.from_regex(SLUG_PATTERN, fullmatch=True)

# Arbitrary strings, which may or may not happen to match the pattern --
# used for the "accepted if and only if it matches" direction.
_arbitrary_slug_candidate = st.text(min_size=0, max_size=50)


# Feature: aslinumber-p2-tenancy-brands, Property 1: Brand slug format
# gates creation
@settings(max_examples=100)
@given(candidate=_arbitrary_slug_candidate)
def test_slug_validation_matches_pattern_exactly(candidate: str) -> None:
    """A candidate slug is accepted by validate_slug if and only if it

    matches SLUG_PATTERN; every non-matching string is rejected with
    HTTP 422.
    """
    should_match = bool(SLUG_PATTERN.match(candidate))

    if should_match:
        validate_slug(candidate)  # must not raise
    else:
        try:
            validate_slug(candidate)
            raised = False
        except AppError as exc:
            raised = True
            assert exc.code == ErrorCode.VALIDATION_ERROR
            assert exc.status_code == 422
        assert raised


# Feature: aslinumber-p2-tenancy-brands, Property 2: Brand slug uniqueness
# within a tenant
@settings(max_examples=100)
@given(slug=_valid_slug)
def test_slug_uniqueness_is_scoped_per_tenant(slug: str) -> None:
    """For any valid slug, the first brand created with that slug within a

    tenant succeeds; a second creation with the identical slug in the
    same tenant is rejected with HTTP 409; a brand with that same slug in
    a different tenant succeeds independently of the first tenant's
    state.
    """
    db = _fresh_db()
    repo = BrandsRepo(db)
    tenant_a = ObjectId()
    tenant_b = ObjectId()

    first = _make_brand(tenant_a, slug)
    validate_brand_create(tenant_a, first, repo)
    repo.create(first)

    second = _make_brand(tenant_a, slug)
    try:
        validate_brand_create(tenant_a, second, repo)
        raised = False
    except AppError as exc:
        raised = True
        assert exc.code == ErrorCode.CONFLICT
        assert exc.status_code == 409
    assert raised

    other_tenant_brand = _make_brand(tenant_b, slug)
    validate_brand_create(tenant_b, other_tenant_brand, repo)  # must not raise
