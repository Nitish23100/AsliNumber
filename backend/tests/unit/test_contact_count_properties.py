"""Property-based test for official-contact count reflecting registry size (Property 5).

Validates: Requirements 3.2.
"""

from datetime import UTC, datetime

import mongomock
from bson import ObjectId
from hypothesis import given, settings
from hypothesis import strategies as st

from app.models.brand import Alias, Authority, Brand, ContactMethod, ContactStatus, OfficialDomain
from app.models.official_contact import ContactSource, OfficialContact
from app.repos import create_indexes
from app.repos.brands_repo import BrandsRepo
from app.repos.official_contacts_repo import OfficialContactsRepo


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


def _make_contact(
    tenant_id: ObjectId, brand_id: ObjectId, index: int, deprecated: bool
) -> OfficialContact:
    return OfficialContact(
        tenantId=tenant_id,
        brandId=brand_id,
        e164=f"+9198765{index:05d}",
        display=f"+9198765{index:05d}",
        contactTypes=[],
        authority=Authority.SUPPORTING,
        method=ContactMethod.MANUAL,
        source=ContactSource(url="https://e.test", registeredDomain="e.test"),
        retrievedAt=datetime.now(UTC),
        validFrom=datetime.now(UTC),
        status=ContactStatus.DEPRECATED if deprecated else ContactStatus.ACTIVE,
    )


# Feature: aslinumber-p2-tenancy-brands, Property 5: Official-contact
# count reflects actual registry size
@settings(max_examples=100)
@given(statuses=st.lists(st.booleans(), min_size=0, max_size=15))
def test_count_reflects_n_contacts_regardless_of_status(statuses: list[bool]) -> None:
    """For N official contacts created for a brand (any mix of

    active/deprecated), the reported count equals N.
    """
    db = _fresh_db()
    brands_repo = BrandsRepo(db)
    contacts_repo = OfficialContactsRepo(db)
    tenant_id = ObjectId()
    brand = brands_repo.create(_make_brand(tenant_id))

    for i, is_deprecated in enumerate(statuses):
        contacts_repo.create(_make_contact(tenant_id, brand.id, i, is_deprecated))

    assert brands_repo.count_official_contacts(tenant_id, brand.id) == len(statuses)
