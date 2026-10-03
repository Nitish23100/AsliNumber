"""Property-based test for backend.app.auth.lockout (Property 6).

Validates: Requirements 9.1, 9.2, 9.3.
"""

import mongomock
from hypothesis import given, settings
from hypothesis import strategies as st

from app.auth.lockout import is_locked, record_failed_login, record_successful_login
from app.models.user import User
from app.repos import create_indexes
from app.repos.users_repo import UsersRepo


def _fresh_db():
    client = mongomock.MongoClient("mongodb://localhost:27017/aslinumber_test", tz_aware=True)
    db = client.get_default_database()
    create_indexes(db)
    return db


# Feature: aslinumber-p1-foundation, Property 6: Lockout state machine over an attempt sequence
@settings(max_examples=100)
@given(attempts=st.lists(st.booleans(), min_size=1, max_size=30))
def test_lockout_state_machine_over_attempt_sequence(attempts: list[bool]) -> None:
    """For any sequence of login attempts (True = correct password), the

    account is locked iff the count of consecutive incorrect attempts
    since the most recent correct attempt (or account creation) has
    reached 5; a correct attempt resets the count to zero.
    """
    db = _fresh_db()
    repo = UsersRepo(db)
    user = repo.create(
        User(email="attempt-seq@example.com", passwordHash="hash", name="Test", status="active")
    )

    consecutive_failures = 0
    for correct in attempts:
        current_user = repo.find_by_id(user.id)
        locked_before = is_locked(current_user)

        if locked_before:
            # Per Requirement 9.2: every attempt is rejected while locked,
            # regardless of correctness -- simulate that by not even
            # processing the attempt (the real login route would stop
            # here too). The expected locked state going into (and
            # coming out of) this iteration is unchanged.
            continue

        if correct:
            record_successful_login(repo, user.id)
            consecutive_failures = 0
        else:
            record_failed_login(repo, user.id)
            consecutive_failures += 1

        current_user = repo.find_by_id(user.id)
        expected_locked = consecutive_failures >= 5
        assert is_locked(current_user) == expected_locked
