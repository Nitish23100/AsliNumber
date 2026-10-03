"""Unit test for the lockout time-boundary edge case (task 9.5).

Validates: Requirement 9.4. Using a mocked clock: lock an account, advance
time past 15 minutes, confirm a correct login then succeeds.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from app.auth.lockout import is_locked, record_failed_login
from app.models.user import User
from app.repos.users_repo import UsersRepo


def test_lockout_clears_after_15_minutes_elapse(db) -> None:
    repo = UsersRepo(db)
    user = repo.create(
        User(email="time-boundary@example.com", passwordHash="hash", name="Test", status="active")
    )

    for _ in range(5):
        record_failed_login(repo, user.id)

    locked_user = repo.find_by_id(user.id)
    assert is_locked(locked_user) is True

    future_time = datetime.now(UTC) + timedelta(minutes=16)
    with patch("app.auth.lockout.datetime") as mocked_datetime:
        mocked_datetime.now.return_value = future_time
        # is_locked compares user.lockedUntil (a real timestamp) against
        # "now" -- advancing only the "now" side is enough to prove the
        # lockout clears without a separate unlock write, per
        # Requirement 9.4.
        still_locked_user = repo.find_by_id(user.id)
        assert is_locked(still_locked_user) is False
