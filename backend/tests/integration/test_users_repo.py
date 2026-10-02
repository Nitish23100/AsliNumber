"""Integration tests for `app.repos.users_repo`.

Covers the create+find round trip, the unique index on `email`, and the
atomicity of `increment_failed_logins`/`reset_failed_logins`, per task
4.2's testing checklist. Runs against the in-memory `mongomock` database
fixture (see `conftest.py` for why).
"""

from datetime import UTC, datetime

import pytest
from bson import ObjectId
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from app.models.user import User
from app.repos.users_repo import UsersRepo


def _make_user(email: str = "jane.doe@example.com") -> User:
    return User(email=email, passwordHash="argon2idhash", name="Jane Doe", status="active")


def test_create_and_find_by_email_round_trip(db: Database) -> None:
    repo = UsersRepo(db)
    user = _make_user()

    created = repo.create(user)
    found = repo.find_by_email("jane.doe@example.com")

    assert found is not None
    assert found.id == created.id
    assert found.name == "Jane Doe"


def test_find_by_email_is_case_insensitive(db: Database) -> None:
    repo = UsersRepo(db)
    repo.create(_make_user("Jane.Doe@Example.com"))

    found = repo.find_by_email("JANE.DOE@EXAMPLE.COM")

    assert found is not None
    assert found.email == "jane.doe@example.com"


def test_create_and_find_by_id_round_trip(db: Database) -> None:
    repo = UsersRepo(db)
    created = repo.create(_make_user())

    found = repo.find_by_id(created.id)

    assert found is not None
    assert found.id == created.id


def test_find_by_email_returns_none_when_absent(db: Database) -> None:
    repo = UsersRepo(db)

    assert repo.find_by_email("nobody@example.com") is None


def test_duplicate_email_raises_duplicate_key_error(db: Database) -> None:
    repo = UsersRepo(db)
    repo.create(_make_user("duplicate@example.com"))

    with pytest.raises(DuplicateKeyError):
        repo.create(_make_user("duplicate@example.com"))


def test_increment_failed_logins_increments_atomically(db: Database) -> None:
    repo = UsersRepo(db)
    created = repo.create(_make_user())

    first = repo.increment_failed_logins(created.id)
    second = repo.increment_failed_logins(created.id)
    third = repo.increment_failed_logins(created.id)

    assert (first, second, third) == (1, 2, 3)
    assert repo.find_by_id(created.id).failedLogins == 3


def test_increment_failed_logins_raises_for_unknown_user(db: Database) -> None:
    repo = UsersRepo(db)

    with pytest.raises(ValueError):
        repo.increment_failed_logins(ObjectId())


def test_reset_failed_logins_sets_count_to_zero(db: Database) -> None:
    repo = UsersRepo(db)
    created = repo.create(_make_user())
    repo.increment_failed_logins(created.id)
    repo.increment_failed_logins(created.id)

    repo.reset_failed_logins(created.id)

    assert repo.find_by_id(created.id).failedLogins == 0


def test_set_locked_until_stores_and_clears_value(db: Database) -> None:
    repo = UsersRepo(db)
    created = repo.create(_make_user())
    locked_until = datetime(2030, 1, 1, tzinfo=UTC)

    repo.set_locked_until(created.id, locked_until)
    assert repo.find_by_id(created.id).lockedUntil == locked_until

    repo.set_locked_until(created.id, None)
    assert repo.find_by_id(created.id).lockedUntil is None
