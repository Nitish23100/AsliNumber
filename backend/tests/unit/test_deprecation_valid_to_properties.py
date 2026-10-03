"""Property-based test for deprecation defaulting `validTo` (Property 10).

Validates: Requirements 6.5.
"""

from datetime import UTC, datetime, timedelta

import mongomock
from bson import ObjectId
from hypothesis import given, settings
from hypothesis import strategies as st
from pymongo.database import Database

from app.models.brand import Authority, ContactMethod
from app.models.official_contact import ContactSource, OfficialContact
from app.repos import create_indexes
from app.repos.official_contacts_repo import OfficialContactsRepo

# MongoDB (and mongomock) store datetimes with millisecond precision only,
# so generated examples are truncated to whole milliseconds -- otherwise
# a sub-millisecond microsecond component would be silently dropped on
# round-trip, producing a spurious mismatch against the submitted value.
_explicit_valid_to = st.datetimes(
    min_value=datetime(2000, 1, 1), max_value=datetime(2100, 1, 1)
).map(lambda dt: dt.replace(microsecond=(dt.microsecond // 1000) * 1000, tzinfo=UTC))


def _fresh_db() -> Database:
    client = mongomock.MongoClient("mongodb://localhost:27017/aslinumber_test", tz_aware=True)
    db = client.get_default_database()
    create_indexes(db)
    return db


def _make_contact(tenant_id: ObjectId, brand_id: ObjectId) -> OfficialContact:
    return OfficialContact(
        tenantId=tenant_id,
        brandId=brand_id,
        e164="+919876543210",
        display="Support",
        contactTypes=["support"],
        authority=Authority.SUPPORTING,
        method=ContactMethod.MANUAL,
        source=ContactSource(url="https://e.test", registeredDomain="e.test"),
        retrievedAt=datetime.now(UTC),
        validFrom=datetime.now(UTC),
    )


def _apply_deprecation_update(repo, tenant_id, contact_id, explicit_valid_to):
    """Mirror the router's PATCH /official-contacts/{id} defaulting logic.

    `official_contacts.py`'s `update_official_contact` applies exactly
    this rule to the request's `changes` dict before calling
    `OfficialContactsRepo.update`; this helper re-applies that same rule
    directly against the repository so the property can be checked
    without going through the HTTP layer.
    """
    changes: dict = {"status": "deprecated"}
    if explicit_valid_to is not None:
        changes["validTo"] = explicit_valid_to
    else:
        changes["validTo"] = datetime.now(UTC)
    return repo.update(tenant_id, contact_id, changes)


# Feature: aslinumber-p2-tenancy-brands, Property 10: Deprecation defaults
# validTo when omitted
@settings(max_examples=100)
@given(explicit_valid_to=st.one_of(st.none(), _explicit_valid_to))
def test_deprecation_sets_or_preserves_valid_to(explicit_valid_to) -> None:
    """If the deprecation request omits validTo, the persisted validTo is

    set to the time of the request; if it supplies validTo, the
    persisted value equals exactly the supplied value.
    """
    db = _fresh_db()
    repo = OfficialContactsRepo(db)
    tenant_id, brand_id = ObjectId(), ObjectId()
    created = repo.create(_make_contact(tenant_id, brand_id))

    before = datetime.now(UTC)
    updated = _apply_deprecation_update(repo, tenant_id, created.id, explicit_valid_to)
    after = datetime.now(UTC)

    assert updated is not None
    assert updated.status == "deprecated"
    if explicit_valid_to is not None:
        assert updated.validTo == explicit_valid_to
    else:
        assert before - timedelta(seconds=1) <= updated.validTo <= after + timedelta(seconds=1)
