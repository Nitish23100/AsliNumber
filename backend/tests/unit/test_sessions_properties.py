"""Property-based test for backend.app.auth.sessions (Property 4).

Validates: Requirement 8.2.
"""

import mongomock
from bson import ObjectId
from hypothesis import given, settings
from hypothesis import strategies as st

from app.auth.sessions import create_session
from app.auth.tokens import hash_refresh_token
from app.repos import create_indexes
from app.repos.sessions_repo import SessionsRepo

_token_text = st.text(min_size=1, max_size=200)


def _fresh_db():
    client = mongomock.MongoClient("mongodb://localhost:27017/aslinumber_test", tz_aware=True)
    db = client.get_default_database()
    create_indexes(db)
    return db


# Feature: aslinumber-p1-foundation, Property 4: Refresh token storage never retains the raw token
@settings(max_examples=100)
@given(raw_token=_token_text)
def test_session_record_never_stores_the_raw_refresh_token(raw_token: str) -> None:
    """For any generated Refresh_Token value, the Session_Record persisted

    for it stores a value that never equals the raw token string, and
    re-hashing the raw token with the same hash function equals the
    stored value.
    """
    db = _fresh_db()
    repo = SessionsRepo(db)
    token_hash = hash_refresh_token(raw_token)

    session = create_session(
        repo, user_id=ObjectId(), tenant_id=ObjectId(), refresh_token_hash=token_hash
    )

    stored = repo.find_by_refresh_hash(token_hash)
    assert stored is not None
    assert stored.id == session.id
    assert stored.refreshTokenHash != raw_token
    assert stored.refreshTokenHash == hash_refresh_token(raw_token)
