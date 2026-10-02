"""Integration tests for `app.repos.create_indexes`.

Confirms the consolidated entry point creates every index listed in the
design's Data Models section, and that calling it twice (simulating two
app startups against the same database) doesn't raise -- `create_index`
is idempotent for an identical spec.
"""

from pymongo.database import Database

from app.repos import create_indexes


def test_create_indexes_creates_every_expected_index(db: Database) -> None:
    # `db` fixture already calls `create_indexes` once; call it again here
    # to assert on the resulting state and to prove idempotency in one go.
    create_indexes(db)

    tenant_indexes = db["tenants"].index_information()
    user_indexes = db["users"].index_information()
    membership_indexes = db["memberships"].index_information()
    session_indexes = db["sessions"].index_information()

    assert any(
        spec["key"] == [("slug", 1)] and spec.get("unique") for spec in tenant_indexes.values()
    )
    assert any(
        spec["key"] == [("email", 1)] and spec.get("unique") for spec in user_indexes.values()
    )
    assert any(
        spec["key"] == [("userId", 1), ("tenantId", 1)] and spec.get("unique")
        for spec in membership_indexes.values()
    )
    assert any(
        spec["key"] == [("refreshTokenHash", 1)] and spec.get("unique")
        for spec in session_indexes.values()
    )
    assert any(
        spec["key"] == [("expiresAt", 1)] and spec.get("expireAfterSeconds") == 0
        for spec in session_indexes.values()
    )


def test_create_indexes_is_idempotent_when_called_repeatedly(db: Database) -> None:
    # Calling it a third/fourth time (first two calls happened in the
    # fixture and the test above) must not raise.
    create_indexes(db)
    create_indexes(db)
