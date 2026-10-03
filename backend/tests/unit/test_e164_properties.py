"""Property-based test for E.164 validation and verbatim storage (Property 8).

Validates: Requirements 5.1, 5.2.
"""

from datetime import UTC, datetime

import mongomock
import pytest
from bson import ObjectId
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from app.models.brand import Authority, ContactMethod
from app.models.official_contact import E164_PATTERN, ContactSource, OfficialContact
from app.repos import create_indexes
from app.repos.official_contacts_repo import OfficialContactsRepo


def _fresh_db():
    client = mongomock.MongoClient("mongodb://localhost:27017/aslinumber_test", tz_aware=True)
    db = client.get_default_database()
    create_indexes(db)
    return db


def _build_contact(e164: str) -> OfficialContact:
    return OfficialContact(
        tenantId=ObjectId(),
        brandId=ObjectId(),
        e164=e164,
        display=e164,
        contactTypes=[],
        authority=Authority.SUPPORTING,
        method=ContactMethod.MANUAL,
        source=ContactSource(url="https://e.test", registeredDomain="e.test"),
        retrievedAt=datetime.now(UTC),
        validFrom=datetime.now(UTC),
    )


# Valid E.164: a '+', a digit 1-9, then 6 to 14 more digits.
_valid_e164 = st.from_regex(E164_PATTERN, fullmatch=True)

# Arbitrary strings, which may or may not happen to match the pattern --
# used for the "accepted if and only if it matches" direction.
_arbitrary_string = st.text(min_size=1, max_size=20)


# Feature: aslinumber-p2-tenancy-brands, Property 8: E.164 validation and
# verbatim storage
@settings(max_examples=100)
@given(e164=_valid_e164)
def test_valid_e164_is_accepted_and_stored_verbatim(e164: str) -> None:
    """For any string matching E164_PATTERN, it is accepted and the

    persisted value is identical, character for character, to the
    submitted string.
    """
    db = _fresh_db()
    repo = OfficialContactsRepo(db)
    contact = _build_contact(e164)

    created = repo.create(contact)
    found = repo.find_by_id(contact.tenantId, created.id)

    assert found is not None
    assert found.e164 == e164


# Feature: aslinumber-p2-tenancy-brands, Property 8: E.164 validation and
# verbatim storage
@settings(max_examples=100)
@given(candidate=_arbitrary_string)
def test_e164_acceptance_matches_pattern_exactly(candidate: str) -> None:
    """A candidate string is accepted if and only if it matches E164_PATTERN."""
    should_match = bool(E164_PATTERN.match(candidate))

    if should_match:
        contact = _build_contact(candidate)
        assert contact.e164 == candidate
    else:
        with pytest.raises(ValidationError):
            _build_contact(candidate)
