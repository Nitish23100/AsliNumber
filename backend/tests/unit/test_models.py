"""Unit tests for the Pydantic domain models in `app.models`.

Confirms each model (`Tenant`, `User`, `Membership`, `Session`, `Role`,
`AccessTokenClaims`) constructs successfully with valid data and rejects at
least one invalid case, per task 4.1.
"""

from datetime import UTC, datetime

import pytest
from bson import ObjectId
from pydantic import ValidationError

from app.models import AccessTokenClaims, Membership, Role, Session, Tenant, User


class TestRole:
    def test_rank_ordering_is_owner_admin_analyst_viewer(self) -> None:
        assert Role.OWNER.rank > Role.ADMIN.rank > Role.ANALYST.rank > Role.VIEWER.rank

    def test_rejects_invalid_role_value(self) -> None:
        with pytest.raises(ValueError):
            Role("superadmin")


class TestTenant:
    def test_constructs_with_valid_data(self) -> None:
        tenant = Tenant(name="Demo Brand Protection", slug="demo-brand-protection")

        assert tenant.name == "Demo Brand Protection"
        assert tenant.slug == "demo-brand-protection"
        assert tenant.creditPolicy == {}
        assert isinstance(tenant.id, ObjectId)

    def test_rejects_missing_required_field(self) -> None:
        with pytest.raises(ValidationError):
            Tenant(slug="demo-brand-protection")


class TestUser:
    def test_constructs_with_valid_data_and_lowercases_email(self) -> None:
        user = User(
            email="Jane.Doe@Example.com",
            passwordHash="argon2idhash",
            name="Jane Doe",
            status="active",
        )

        assert user.email == "jane.doe@example.com"
        assert user.failedLogins == 0
        assert user.lockedUntil is None

    def test_rejects_missing_required_field(self) -> None:
        with pytest.raises(ValidationError):
            User(passwordHash="argon2idhash", name="Jane Doe", status="active")


class TestMembership:
    def test_constructs_with_valid_data(self) -> None:
        membership = Membership(userId=ObjectId(), tenantId=ObjectId(), role="admin")

        assert membership.role is Role.ADMIN

    def test_rejects_invalid_role_string(self) -> None:
        with pytest.raises(ValidationError):
            Membership(userId=ObjectId(), tenantId=ObjectId(), role="superadmin")


class TestSession:
    def test_constructs_with_valid_data(self) -> None:
        session = Session(
            userId=ObjectId(),
            tenantId=ObjectId(),
            refreshTokenHash="deadbeef",
            expiresAt=datetime.now(UTC),
        )

        assert session.rotatedFrom is None
        assert session.rotated is False
        assert session.revoked is False

    def test_rejects_missing_required_field(self) -> None:
        with pytest.raises(ValidationError):
            Session(userId=ObjectId(), tenantId=ObjectId(), refreshTokenHash="deadbeef")


class TestAccessTokenClaims:
    def test_constructs_with_valid_data(self) -> None:
        now = datetime.now(UTC)
        claims = AccessTokenClaims(
            sub=str(ObjectId()),
            tid=str(ObjectId()),
            role="viewer",
            jti="11111111-1111-1111-1111-111111111111",
            iat=now,
            exp=now,
        )

        assert claims.role is Role.VIEWER

    def test_rejects_invalid_role_value(self) -> None:
        now = datetime.now(UTC)
        with pytest.raises(ValidationError):
            AccessTokenClaims(
                sub=str(ObjectId()),
                tid=str(ObjectId()),
                role="superadmin",
                jti="11111111-1111-1111-1111-111111111111",
                iat=now,
                exp=now,
            )
