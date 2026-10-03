"""Account lockout tracking.

Implements the design's `backend/app/auth/lockout.py` component:
`record_failed_login`, `record_successful_login`, `is_locked`. Builds on
`app.repos.users_repo.UsersRepo` (task 4.2) for the `failedLogins` counter
and `lockedUntil` timestamp.

Per Requirement 9 and design Property 6 (lockout state machine): an
account locks for 15 minutes after its 5th consecutive failed login since
the last successful one; while locked, every login attempt is rejected
regardless of password correctness; a successful login resets the
consecutive-failure count to zero.
"""

from datetime import UTC, datetime, timedelta

from app.models.user import User
from app.repos.users_repo import UsersRepo

# Per Requirement 9.1 and plan §9.6: 5 consecutive failures lock the
# account for 15 minutes.
_FAILURE_THRESHOLD = 5
_LOCKOUT_DURATION = timedelta(minutes=15)


def record_failed_login(repo: UsersRepo, user_id) -> None:
    """Record one failed login attempt for `user_id`.

    Increments `failedLogins` atomically. When the increment reaches the
    threshold (5), sets `lockedUntil` to 15 minutes from now.
    """
    new_count = repo.increment_failed_logins(user_id)
    if new_count >= _FAILURE_THRESHOLD:
        repo.set_locked_until(user_id, datetime.now(UTC) + _LOCKOUT_DURATION)


def record_successful_login(repo: UsersRepo, user_id) -> None:
    """Record one successful login for `user_id`.

    Resets `failedLogins` to zero and clears `lockedUntil`, per
    Requirement 9.3.
    """
    repo.reset_failed_logins(user_id)
    repo.set_locked_until(user_id, None)


def is_locked(user: User) -> bool:
    """Whether `user`'s account is currently locked.

    `True` only while `lockedUntil` is set and still in the future -- once
    the lockout period elapses, this returns `False` again without any
    separate "unlock" write (per Requirement 9.4), and the next successful
    login clears `lockedUntil` via :func:`record_successful_login`.
    """
    return user.lockedUntil is not None and user.lockedUntil > datetime.now(UTC)
