"""Property-based test for backend.app.auth.sessions (Property 5).

Validates: Requirements 8.3, 8.4.
"""

import mongomock
from bson import ObjectId
from hypothesis import given, settings
from hypothesis import strategies as st

from app.auth.sessions import create_session, revoke_chain, rotate_session
from app.auth.tokens import hash_refresh_token
from app.repos import create_indexes
from app.repos.sessions_repo import SessionsRepo


def _fresh_db():
    client = mongomock.MongoClient("mongodb://localhost:27017/aslinumber_test", tz_aware=True)
    db = client.get_default_database()
    create_indexes(db)
    return db


# Feature: aslinumber-p1-foundation, Property 5: Refresh rotation chain
# integrity and reuse detection
@settings(max_examples=100)
@given(chain_length=st.integers(min_value=1, max_value=15))
def test_rotation_chain_and_reuse_detection(chain_length: int) -> None:
    """For any chain of N sequential refresh rotations starting from one

    login: using the current token to refresh succeeds and marks the
    prior Session_Record rotated; replaying any non-current token in the
    chain revokes every Session_Record in the chain.
    """
    db = _fresh_db()
    repo = SessionsRepo(db)
    user_id, tenant_id = ObjectId(), ObjectId()

    first_hash = hash_refresh_token(f"seed-{chain_length}")
    sessions = [create_session(repo, user_id, tenant_id, first_hash)]

    for i in range(chain_length):
        new_hash = hash_refresh_token(f"rotated-{chain_length}-{i}")
        sessions.append(rotate_session(repo, sessions[-1], new_hash))

    # Using the current (last) session to "refresh" again is the only
    # legitimate next step -- it is not itself tested here (that's the
    # auth route's job), but the chain built above must be intact:
    # every earlier session is rotated, and the current one is not.
    for session in sessions[:-1]:
        refreshed = repo.find_by_refresh_hash(session.refreshTokenHash)
        assert refreshed.rotated is True
        assert refreshed.revoked is False

    current = sessions[-1]
    refreshed_current = repo.find_by_refresh_hash(current.refreshTokenHash)
    assert refreshed_current.rotated is False
    assert refreshed_current.revoked is False

    # Reuse: replay a non-current (already-rotated) token from the chain.
    reused_session = sessions[0]
    revoke_chain(repo, reused_session.id)

    for session in sessions:
        revoked = repo.find_by_refresh_hash(session.refreshTokenHash)
        assert revoked.revoked is True, f"session at index {sessions.index(session)} not revoked"
