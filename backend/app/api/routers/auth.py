"""Authentication routes: login, logout, refresh, switch-tenant, me.

Wires together everything tasks 4.2-7.1 built: password verification
(`app.auth.passwords`), lockout tracking (`app.auth.lockout`), access/
refresh token issuance (`app.auth.tokens`), session rotation
(`app.auth.sessions`), and tenant/role context (`app.auth.deps`).

Per the design's Error Handling section: expired, unknown, and reused
Refresh_Tokens all produce the same generic `UNAUTHENTICATED` response, so
a client (or attacker) cannot distinguish "token expired" from "token
flagged as reused" from the response alone -- the chain revocation still
happens server-side on reuse; only the externally visible signal is
unified. Login failures use a generic "Invalid email or password" message
regardless of whether the account exists, to avoid leaking which emails
are registered.
"""

import hashlib
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel
from pymongo.database import Database

from app.auth.deps import TenantContext, get_tenant_context
from app.auth.lockout import is_locked, record_failed_login, record_successful_login
from app.auth.passwords import verify_password
from app.auth.sessions import (
    create_session,
    find_by_refresh_hash,
    is_session_usable,
    revoke_chain,
    rotate_session,
)
from app.auth.tokens import generate_refresh_token, hash_refresh_token, issue_access_token
from app.config import Settings
from app.core.errors import AppError, ErrorCode
from app.core.ratelimit import enforce_login_rate_limit
from app.repos.memberships_repo import MembershipsRepo
from app.repos.sessions_repo import SessionsRepo
from app.repos.users_repo import UsersRepo

router = APIRouter(prefix="/auth", tags=["auth"])

_REFRESH_COOKIE_NAME = "refreshToken"
_REFRESH_COOKIE_MAX_AGE_SECONDS = 7 * 24 * 60 * 60

# Same message for every Access_Token/Refresh_Token failure mode, and for
# both "account not found" and "wrong password" on login, per the design's
# non-disclosure rules.
_GENERIC_AUTH_ERROR_MESSAGE = "Invalid or expired credentials."
_LOGIN_FAILURE_MESSAGE = "Invalid email or password."


class LoginRequest(BaseModel):
    email: str
    password: str


class SwitchTenantRequest(BaseModel):
    tenantId: str


def _get_db(request: Request) -> Database:
    return request.app.state.mongo_client.get_default_database()


def _hash_client_ip(request: Request, settings: Settings) -> str:
    """Salted hash of the request's client IP, never the raw IP, per plan §7.1."""
    client_ip = request.client.host if request.client else "unknown"
    salt = settings.JWT_SECRET or "no-secret-configured"
    return hashlib.sha256(f"{salt}:{client_ip}".encode()).hexdigest()


def _write_audit_log(db: Database, user_id, action: str, target: dict, ip_hash: str) -> None:
    """Append one entry to `audit_log`, per Requirement 9.1/9.2's audit trail.

    P1 wires the collection and writes it from the auth routes only (login
    success/failure, refresh-reuse detected) -- full write-coverage of
    every mutating route arrives in later phases.
    """
    db["audit_log"].insert_one(
        {
            "userId": user_id,
            "action": action,
            "target": target,
            "ipHash": ip_hash,
            "at": datetime.now(UTC),
        }
    )


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=_REFRESH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=_REFRESH_COOKIE_MAX_AGE_SECONDS,
    )


@router.post("/login")
def login(body: LoginRequest, request: Request, response: Response) -> dict:
    """Authenticate with email + password; issue an Access_Token and a Refresh_Token cookie.

    Per Requirement 9.5: rejects excess per-IP attempts with 429 before
    doing any password work.
    """
    settings: Settings = request.app.state.settings
    client_ip = request.client.host if request.client else "unknown"
    enforce_login_rate_limit(client_ip)

    db = _get_db(request)
    users_repo = UsersRepo(db)
    memberships_repo = MembershipsRepo(db)
    sessions_repo = SessionsRepo(db)
    ip_hash = _hash_client_ip(request, settings)

    user = users_repo.find_by_email(body.email)
    if user is None:
        raise AppError(ErrorCode.UNAUTHENTICATED, _LOGIN_FAILURE_MESSAGE)

    if is_locked(user):
        # Does not reveal remaining attempts or unlock time, per the
        # design's lockout non-disclosure rule.
        raise AppError(ErrorCode.UNAUTHENTICATED, _LOGIN_FAILURE_MESSAGE)

    if not verify_password(body.password, user.passwordHash):
        record_failed_login(users_repo, user.id)
        _write_audit_log(db, user.id, "login_failed", {"type": "user", "id": str(user.id)}, ip_hash)
        raise AppError(ErrorCode.UNAUTHENTICATED, _LOGIN_FAILURE_MESSAGE)

    record_successful_login(users_repo, user.id)

    memberships = memberships_repo.find_all_by_user(user.id)
    if not memberships:
        raise AppError(
            ErrorCode.UNAUTHENTICATED,
            "This account has no tenant memberships. Contact an administrator.",
        )
    membership = memberships[0]

    access_token = issue_access_token(str(user.id), str(membership.tenantId), membership.role)
    refresh_token = generate_refresh_token()
    create_session(sessions_repo, user.id, membership.tenantId, hash_refresh_token(refresh_token))

    _set_refresh_cookie(response, refresh_token)
    _write_audit_log(db, user.id, "login_succeeded", {"type": "user", "id": str(user.id)}, ip_hash)

    return {"data": {"accessToken": access_token}, "meta": {}}


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    _context: TenantContext = Depends(get_tenant_context),
) -> dict:
    """Revoke the current Refresh_Token's session and clear its cookie."""
    db = _get_db(request)
    sessions_repo = SessionsRepo(db)

    raw_token = request.cookies.get(_REFRESH_COOKIE_NAME)
    if raw_token:
        session = find_by_refresh_hash(sessions_repo, hash_refresh_token(raw_token))
        if session is not None:
            sessions_repo.mark_revoked(session.id)

    response.delete_cookie(_REFRESH_COOKIE_NAME)
    return {"data": {"status": "logged_out"}, "meta": {}}


@router.post("/refresh")
def refresh(request: Request, response: Response) -> dict:
    """Rotate the Refresh_Token cookie and issue a new Access_Token.

    Per Requirement 8.4: reusing an already-rotated token revokes its
    entire chain and is rejected with the same generic error as an
    expired or unknown token.
    """
    db = _get_db(request)
    sessions_repo = SessionsRepo(db)
    users_repo = UsersRepo(db)
    memberships_repo = MembershipsRepo(db)

    raw_token = request.cookies.get(_REFRESH_COOKIE_NAME)
    if not raw_token:
        raise AppError(ErrorCode.UNAUTHENTICATED, _GENERIC_AUTH_ERROR_MESSAGE)

    session = find_by_refresh_hash(sessions_repo, hash_refresh_token(raw_token))
    if session is None:
        raise AppError(ErrorCode.UNAUTHENTICATED, _GENERIC_AUTH_ERROR_MESSAGE)

    if session.rotated or session.revoked:
        revoke_chain(sessions_repo, session.id)
        _write_audit_log(
            db,
            session.userId,
            "refresh_reuse_detected",
            {"type": "session", "id": str(session.id)},
            _hash_client_ip(request, request.app.state.settings),
        )
        raise AppError(ErrorCode.UNAUTHENTICATED, _GENERIC_AUTH_ERROR_MESSAGE)

    if not is_session_usable(session):
        raise AppError(ErrorCode.UNAUTHENTICATED, _GENERIC_AUTH_ERROR_MESSAGE)

    user = users_repo.find_by_id(session.userId)
    membership = memberships_repo.find_by_user_and_tenant(session.userId, session.tenantId)
    if user is None or membership is None:
        raise AppError(ErrorCode.UNAUTHENTICATED, _GENERIC_AUTH_ERROR_MESSAGE)

    new_refresh_token = generate_refresh_token()
    rotate_session(sessions_repo, session, hash_refresh_token(new_refresh_token))
    access_token = issue_access_token(str(user.id), str(membership.tenantId), membership.role)

    _set_refresh_cookie(response, new_refresh_token)
    return {"data": {"accessToken": access_token}, "meta": {}}


@router.post("/switch-tenant")
def switch_tenant(
    body: SwitchTenantRequest,
    request: Request,
    context: TenantContext = Depends(get_tenant_context),
) -> dict:
    """Issue a new Access_Token scoped to a different membership of the current user."""
    db = _get_db(request)
    memberships_repo = MembershipsRepo(db)

    membership = memberships_repo.find_by_user_and_tenant(context.user_id, body.tenantId)
    if membership is None:
        raise AppError(ErrorCode.FORBIDDEN, "You are not a member of this tenant.")

    access_token = issue_access_token(context.user_id, str(membership.tenantId), membership.role)
    return {"data": {"accessToken": access_token}, "meta": {}}


@router.get("/me")
def get_me(request: Request, context: TenantContext = Depends(get_tenant_context)) -> dict:
    """Return the authenticated user's id, memberships, and current role."""
    db = _get_db(request)
    users_repo = UsersRepo(db)
    memberships_repo = MembershipsRepo(db)

    user = users_repo.find_by_id(context.user_id)
    memberships = memberships_repo.find_all_by_user(context.user_id)

    return {
        "data": {
            "id": str(user.id) if user else context.user_id,
            "email": user.email if user else None,
            "memberships": [
                {"tenantId": str(m.tenantId), "role": m.role.value} for m in memberships
            ],
            "role": context.role.value,
        },
        "meta": {},
    }
