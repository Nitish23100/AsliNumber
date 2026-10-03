"""Unit tests for the P2 Pydantic domain models: Brand, OfficialContact, AuditLogEntry.

Confirms each model constructs successfully with valid data and rejects
at least one invalid case, per task 1.1-1.3.
"""

from datetime import UTC, datetime

import pytest
from bson import ObjectId
from pydantic import ValidationError

from app.models.audit_log_entry import AuditLogEntry, AuditTarget
from app.models.brand import Alias, Authority, Brand, ContactMethod, ContactStatus, OfficialDomain
from app.models.official_contact import ContactScope, ContactSource, OfficialContact


def _alias(text: str = "ExampleKart") -> Alias:
    return Alias(text=text, lang="en", script="latin", kind="legal")


def _official_domain(domain: str = "examplekart.test") -> OfficialDomain:
    return OfficialDomain(domain=domain, verifiedBy="admin", verifiedAt=datetime.now(UTC))


class TestBrand:
    def test_constructs_with_valid_data_and_defaults_version_to_1(self) -> None:
        brand = Brand(
            tenantId=ObjectId(),
            slug="examplekart",
            displayName="ExampleKart",
            category="ecommerce",
            aliases=[_alias()],
            officialDomains=[_official_domain()],
        )

        assert brand.version == 1
        assert brand.active is True
        assert brand.publicLookup is False
        assert brand.group is None

    def test_rejects_missing_required_field(self) -> None:
        with pytest.raises(ValidationError):
            Brand(
                tenantId=ObjectId(),
                displayName="ExampleKart",
                category="ecommerce",
                aliases=[_alias()],
                officialDomains=[_official_domain()],
            )


class TestOfficialContact:
    def test_constructs_with_valid_e164(self) -> None:
        contact = OfficialContact(
            tenantId=ObjectId(),
            brandId=ObjectId(),
            e164="+919876543210",
            display="+91 98765 43210",
            contactTypes=["customer_care"],
            authority=Authority.SUPPORTING,
            method=ContactMethod.MANUAL,
            source=ContactSource(
                url="https://examplekart.test", registeredDomain="examplekart.test"
            ),
            retrievedAt=datetime.now(UTC),
            validFrom=datetime.now(UTC),
        )

        assert contact.e164 == "+919876543210"
        assert contact.status is ContactStatus.ACTIVE
        assert contact.validTo is None

    def test_rejects_malformed_e164(self) -> None:
        with pytest.raises(ValidationError):
            OfficialContact(
                tenantId=ObjectId(),
                brandId=ObjectId(),
                e164="12345",
                display="x",
                contactTypes=[],
                authority=Authority.SUPPORTING,
                method=ContactMethod.MANUAL,
                source=ContactSource(url="https://e.test", registeredDomain="e.test"),
                retrievedAt=datetime.now(UTC),
                validFrom=datetime.now(UTC),
            )

    def test_rejects_invalid_authority_value(self) -> None:
        with pytest.raises(ValidationError):
            OfficialContact(
                tenantId=ObjectId(),
                brandId=ObjectId(),
                e164="+919876543210",
                display="x",
                contactTypes=[],
                authority="co-primary",
                method=ContactMethod.MANUAL,
                source=ContactSource(url="https://e.test", registeredDomain="e.test"),
                retrievedAt=datetime.now(UTC),
                validFrom=datetime.now(UTC),
            )

    def test_accepts_optional_scope(self) -> None:
        contact = OfficialContact(
            tenantId=ObjectId(),
            brandId=ObjectId(),
            e164="+919876543210",
            display="x",
            contactTypes=["customer_care"],
            scope=ContactScope(cities=["Delhi"], languages=["en", "hi"]),
            authority=Authority.PRIMARY,
            method=ContactMethod.MANUAL,
            source=ContactSource(url="https://e.test", registeredDomain="e.test"),
            retrievedAt=datetime.now(UTC),
            validFrom=datetime.now(UTC),
        )

        assert contact.scope.cities == ["Delhi"]


class TestAuditLogEntry:
    def test_constructs_with_valid_data(self) -> None:
        entry = AuditLogEntry(
            tenantId=ObjectId(),
            userId=ObjectId(),
            action="brand_created",
            target=AuditTarget(type="brand", id=str(ObjectId())),
            ipHash="abc123",
            at=datetime.now(UTC),
        )

        assert entry.before is None
        assert entry.after is None

    def test_rejects_missing_required_field(self) -> None:
        with pytest.raises(ValidationError):
            AuditLogEntry(
                tenantId=ObjectId(),
                userId=ObjectId(),
                action="brand_created",
                target=AuditTarget(type="brand", id=str(ObjectId())),
                at=datetime.now(UTC),
            )
