"""Session creation, rotation, and reuse-chain revocation.

Implements the design's `backend/app/auth/sessions.py` component:
`create_session`, `rotate_session`, `revoke_chain`, `find_by_refresh_hash`.
Builds on `app.repos.sessions_repo.SessionsRepo` (task 4.2) for storage and
`app.auth.tokens` (task 5.3) for the raw/hashed Refresh_Token values.

Per Requirement 8 and design Property 5 (refresh rotation chain integrity
and reuse detection): a Session_Record stores only `hash_refresh_token`'s
output, never the raw Refresh_Token (Property 4). Rotating a session marks
the prior record `rotated=True` and inserts a new one pointing
`rotatedFrom` at it. Reusing an already-rotated token revokes every
Session_Record in that token's rotation chain.
"""

from datetime import UTC, datetime, timedelta

from app.models.session import Session
from app.repos.sessions_repo import SessionsRepo

# Per Requirement 8.1 and plan §9.6: Refresh_Tokens are valid for 7 days.
_REFRESH_TOKEN_TTL = timedelta(days=7)


def create_session(
    repo: SessionsRepo,
    user_id,
    tenant_id,
    refresh_token_hash: str,
    *,
    rotated_from=None,
) -> Session:
    """Insert a new Session_Record for a fresh or rotated Refresh_Token.

    Args:
        repo: The sessions repository to persist through.
        user_id: The session's owning user id.
        tenant_id: The tenant this session is scoped to.
        refresh_token_hash: The output of
            :func:`app.auth.tokens.hash_refresh_token` -- never the raw
            token (design Property 4).
        rotated_from: The prior Session_Record's id this one replaces, if
            any. `None` for a session created at login.

    Returns:
        The persisted :class:`Session`, with its `_id` populated.
    """
    session = Session(
        userId=user_id,
        tenantId=tenant_id,
        refreshTokenHash=refresh_token_hash,
        expiresAt=datetime.now(UTC) + _REFRESH_TOKEN_TTL,
        rotatedFrom=rotated_from,
    )
    return repo.create(session)


def find_by_refresh_hash(repo: SessionsRepo, refresh_token_hash: str) -> Session | None:
    """Look up a Session_Record by its Refresh_Token's hash, or `None`."""
    return repo.find_by_refresh_hash(refresh_token_hash)


def rotate_session(
    repo: SessionsRepo,
    old_session: Session,
    new_refresh_token_hash: str,
) -> Session:
    """Mark `old_session` rotated and insert its replacement.

    Per Requirement 8.3: using the current (most recently issued)
    Refresh_Token to refresh marks the prior Session_Record `rotated=True`
    and inserts a new Session_Record linked to it via `rotatedFrom`.

    Args:
        repo: The sessions repository to persist through.
        old_session: The Session_Record being rotated away from.
        new_refresh_token_hash: The hash of the newly issued Refresh_Token.

    Returns:
        The newly created :class:`Session`.
    """
    repo.mark_rotated(old_session.id)
    return create_session(
        repo,
        user_id=old_session.userId,
        tenant_id=old_session.tenantId,
        refresh_token_hash=new_refresh_token_hash,
        rotated_from=old_session.id,
    )


def revoke_chain(repo: SessionsRepo, session_id) -> None:
    """Revoke every Session_Record in `session_id`'s rotation chain.

    Per Requirement 8.4: reusing an already-rotated Refresh_Token means a
    stolen/replayed token, so the entire lineage -- every ancestor and
    descendant reachable through `rotatedFrom`, not just the one record
    that was reused -- is marked `revoked=True`, so none of them can be
    used to refresh again even if a legitimate user's browser still holds
    one of the earlier, not-yet-rotated tokens in the chain.
    """
    chain = repo.find_rotation_chain(session_id)
    for session in chain:
        repo.mark_revoked(session.id)


def is_session_usable(session: Session) -> bool:
    """Whether `session` can still be used to refresh.

    `False` if revoked, already rotated (a stale copy, superseded by a
    newer Session_Record), or past its `expiresAt`.
    """
    if session.revoked or session.rotated:
        return False
    return session.expiresAt > datetime.now(UTC)
