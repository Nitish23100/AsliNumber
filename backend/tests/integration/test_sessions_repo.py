"""Integration tests for `app.repos.sessions_repo`.

Covers the create+find round trip, the unique index on `refreshTokenHash`,
the TTL index configuration on `expiresAt`, and the rotation-chain walk
used by `revoke_chain` (task 6.1), per task 4.2's testing checklist. Runs
against the in-memory `mongomock` database fixture (see `conftest.py` for
why).
"""

from datetime import UTC, datetime, timedelta

import pytest
from bson import ObjectId
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from app.models.session import Session
from app.repos.sessions_repo import COLLECTION_NAME, SessionsRepo


def _make_session(
    refresh_token_hash: str, rotated_from: ObjectId | None = None, **overrides
) -> Session:
    defaults = dict(
        userId=ObjectId(),
        tenantId=ObjectId(),
        refreshTokenHash=refresh_token_hash,
        expiresAt=datetime.now(UTC) + timedelta(days=7),
        rotatedFrom=rotated_from,
    )
    defaults.update(overrides)
    return Session(**defaults)


def test_create_and_find_by_refresh_hash_round_trip(db: Database) -> None:
    repo = SessionsRepo(db)
    session = _make_session("hash-1")

    created = repo.create(session)
    found = repo.find_by_refresh_hash("hash-1")

    assert found is not None
    assert found.id == created.id
    assert found.rotated is False
    assert found.revoked is False


def test_find_by_refresh_hash_returns_none_when_absent(db: Database) -> None:
    repo = SessionsRepo(db)

    assert repo.find_by_refresh_hash("does-not-exist") is None


def test_duplicate_refresh_token_hash_raises_duplicate_key_error(db: Database) -> None:
    repo = SessionsRepo(db)
    repo.create(_make_session("duplicate-hash"))

    with pytest.raises(DuplicateKeyError):
        repo.create(_make_session("duplicate-hash"))


def test_mark_rotated_sets_rotated_flag(db: Database) -> None:
    repo = SessionsRepo(db)
    created = repo.create(_make_session("hash-rotate"))

    repo.mark_rotated(created.id)

    assert repo.find_by_refresh_hash("hash-rotate").rotated is True


def test_mark_revoked_sets_revoked_flag(db: Database) -> None:
    repo = SessionsRepo(db)
    created = repo.create(_make_session("hash-revoke"))

    repo.mark_revoked(created.id)

    assert repo.find_by_refresh_hash("hash-revoke").revoked is True


def test_find_rotation_chain_walks_a_linear_chain_in_both_directions(db: Database) -> None:
    repo = SessionsRepo(db)
    root = repo.create(_make_session("hash-root"))
    middle = repo.create(_make_session("hash-middle", rotated_from=root.id))
    tip = repo.create(_make_session("hash-tip", rotated_from=middle.id))

    # Querying from the middle of the chain must still find both the root
    # (backward) and the tip (forward).
    chain = repo.find_rotation_chain(middle.id)

    assert {s.id for s in chain} == {root.id, middle.id, tip.id}


def test_find_rotation_chain_from_root_finds_whole_chain(db: Database) -> None:
    repo = SessionsRepo(db)
    root = repo.create(_make_session("hash-root-2"))
    tip = repo.create(_make_session("hash-tip-2", rotated_from=root.id))

    chain = repo.find_rotation_chain(root.id)

    assert {s.id for s in chain} == {root.id, tip.id}


def test_find_rotation_chain_single_session_returns_itself(db: Database) -> None:
    repo = SessionsRepo(db)
    only = repo.create(_make_session("hash-lonely"))

    chain = repo.find_rotation_chain(only.id)

    assert {s.id for s in chain} == {only.id}


def test_find_rotation_chain_unknown_id_returns_empty_list(db: Database) -> None:
    repo = SessionsRepo(db)

    assert repo.find_rotation_chain(ObjectId()) == []


def test_ttl_index_configured_on_expires_at(db: Database) -> None:
    index_info = db[COLLECTION_NAME].index_information()
    expires_at_index = next(
        spec for name, spec in index_info.items() if spec["key"] == [("expiresAt", 1)]
    )

    assert expires_at_index.get("expireAfterSeconds") == 0
