"""Tenant context extraction and role-based route guards.

Implements the design's `backend/app/auth/deps.py` component:
`TenantContext` (a FastAPI dependency decoding the Access_Token from the
`Authorization` header, exposing `tenant_id`/`user_id`/`role`) and
`require_role(minimum)` (a dependency factory comparing the requester's
role rank against a route's configured minimum, per Requirement 10 and
design Property 7).

Per Requirement 7.2 and the design's indistinguishability rule: a missing,
malformed, invalid-signature, or expired Access_Token all produce the same
generic `UNAUTHENTICATED` / 401 response -- the client cannot tell which
case occurred from the response alone.
"""

import jwt
from fastapi import Depends, Request

from app.auth.tokens import decode_access_token
from app.core.errors import AppError, ErrorCode
from app.models.role import AccessTokenClaims, Role

_GENERIC_AUTH_ERROR_MESSAGE = "Invalid or expired credentials."


class TenantContext:
    """The authenticated requester's identity, scoped to one tenant.

    Built from a validated Access_Token's claims. `tenant_id`, `user_id`,
    and `role` are the request-scoped values every tenant-scoped
    repository call (per plan §9.2's repository convention) and every
    `require_role` check reads.
    """

    def __init__(self, claims: AccessTokenClaims) -> None:
        self.user_id = claims.sub
        self.tenant_id = claims.tid
        self.role = claims.role
        self.token_id = claims.jti


def _extract_bearer_token(request: Request) -> str:
    """Pull the raw token out of a `Authorization: Bearer <token>` header.

    Raises the same generic `UNAUTHENTICATED` error as every other
    Access_Token failure mode when the header is missing or malformed, so
    "no token" is indistinguishable from "bad token" to the client.
    """
    header = request.headers.get("Authorization")
    if not header or not header.startswith("Bearer "):
        raise AppError(ErrorCode.UNAUTHENTICATED, _GENERIC_AUTH_ERROR_MESSAGE)
    return header.removeprefix("Bearer ")


def get_tenant_context(request: Request) -> TenantContext:
    """FastAPI dependency: decode the request's Access_Token into a `TenantContext`.

    Per Requirement 7.2: an expired, invalidly-signed, or otherwise
    malformed token raises the same generic `UNAUTHENTICATED` / 401 error
    PyJWT's various `InvalidTokenError` subclasses are caught together,
    rather than individually, so the response never reveals which failure
    mode occurred.
    """
    token = _extract_bearer_token(request)
    try:
        claims = decode_access_token(token)
    except jwt.InvalidTokenError as exc:
        raise AppError(ErrorCode.UNAUTHENTICATED, _GENERIC_AUTH_ERROR_MESSAGE) from exc
    return TenantContext(claims)


def require_role(minimum: Role):
    """Dependency factory: require the requester's role to rank at or above `minimum`.

    Per Requirement 10.2/10.3 and design Property 7: compares
    `TenantContext.role`'s rank (fixed ordering `owner > admin > analyst >
    viewer`, see `app.models.role.Role.rank`) against `minimum`'s rank
    with `>=`. Raises `FORBIDDEN` / 403 when the requester's rank is below
    `minimum`; otherwise returns the `TenantContext` unchanged, so a route
    can depend on `require_role(Role.ANALYST)` and still receive the
    `TenantContext` to use.
    """

    def _check(context: TenantContext = Depends(get_tenant_context)) -> TenantContext:
        if context.role.rank < minimum.rank:
            raise AppError(
                ErrorCode.FORBIDDEN,
                f"This action requires at least the {minimum.value!r} role.",
            )
        return context

    return _check
