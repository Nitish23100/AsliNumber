"""Access token issuance/decoding and refresh token generation/hashing.

Implements the design's `backend/app/auth/tokens.py` component:

- `issue_access_token` / `decode_access_token` — a 15-minute JSON Web Token
  carrying `sub` (user id), `tid` (tenant id), `role`, and `jti` (a unique
  token id), signed with `Settings.JWT_SECRET` via HS256, per Requirement
  7.1-7.3 and design Property 2 (access token claim round-trip).
- `generate_refresh_token` / `hash_refresh_token` — an opaque, high-entropy
  Refresh_Token and its SHA-256 digest for storage, per Requirement 8.2 and
  design Property 4 (refresh token storage never retains the raw token).
  `app.auth.sessions` (task 6.1) stores only `hash_refresh_token`'s output
  in a `Session_Record`, never the raw token.

`Settings` is instantiated internally rather than threaded through as a
parameter, matching the design's exact `issue_access_token(user_id,
tenant_id, role) -> str` / `decode_access_token(token) -> AccessTokenClaims`
signatures (no `settings` argument). `app.core.db.get_mongo_client` takes
`settings` explicitly because it is wired once at app-startup time (task
2.6) and reused for the client's lifetime; token issuance/decoding happens
on every request instead, so each call reads `Settings()` fresh -- this
also means a `JWT_SECRET` rotated via the environment takes effect
immediately, without requiring a settings object to be threaded through
every auth call site.
"""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt

from app.config import Settings
from app.models.role import AccessTokenClaims, Role

# Per Requirement 7.1 and the design's `tokens.py` component: Access_Tokens
# are valid for 15 minutes.
_ACCESS_TOKEN_TTL = timedelta(minutes=15)

_JWT_ALGORITHM = "HS256"

# Length (in bytes, before URL-safe base64 encoding) of the random value
# backing a Refresh_Token. 32 bytes (256 bits) of CSPRNG output is far
# beyond brute-forceable, consistent with the design's "cryptographically
# random opaque string" requirement for `generate_refresh_token`.
_REFRESH_TOKEN_BYTES = 32


def issue_access_token(user_id: str, tenant_id: str, role: Role) -> str:
    """Issue a signed Access_Token for `user_id` scoped to `tenant_id`.

    Builds the claim set per Requirement 7.1 and design Property 2: `sub`
    (user id), `tid` (tenant id), `role` (the membership role this token is
    scoped to), `jti` (a fresh UUID4, unique from any previously issued
    token), `iat` (now, UTC), and `exp` (`iat` + 15 minutes). The payload is
    signed with HS256 using `Settings.JWT_SECRET`.

    Args:
        user_id: The authenticated user's id (becomes the `sub` claim).
        tenant_id: The tenant this token is scoped to (becomes the `tid`
            claim).
        role: The requesting user's role within `tenant_id` (becomes the
            `role` claim, stored as its string value).

    Returns:
        An encoded, signed JWT string.
    """
    settings = Settings()
    issued_at = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "tid": tenant_id,
        "role": role.value,
        "jti": str(uuid4()),
        "iat": issued_at,
        "exp": issued_at + _ACCESS_TOKEN_TTL,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=_JWT_ALGORITHM)


def decode_access_token(token: str) -> AccessTokenClaims:
    """Decode and verify `token`, returning its claims.

    Verifies the HS256 signature against `Settings.JWT_SECRET` and that the
    token has not expired. Per the design ("raises on bad signature or
    expiry"), this function deliberately does NOT catch
    `jwt.InvalidSignatureError` or `jwt.ExpiredSignatureError` (both
    subclasses of `jwt.InvalidTokenError`) -- they propagate to the caller
    unchanged. The intended caller is `TenantContext` (task 7.1), a FastAPI
    dependency that catches `jwt.InvalidTokenError` and raises the generic
    `UNAUTHENTICATED` / HTTP 401 error, per Requirement 7.2 and the design's
    rule that invalid, expired, and unknown tokens all look the same to the
    client.

    Args:
        token: An encoded JWT string, as returned by
            :func:`issue_access_token`.

    Returns:
        The decoded claims as an :class:`AccessTokenClaims` instance.

    Raises:
        jwt.InvalidSignatureError: If `token`'s signature does not match
            `Settings.JWT_SECRET`.
        jwt.ExpiredSignatureError: If `token`'s `exp` claim has passed.
        jwt.InvalidTokenError: For any other malformed-token case PyJWT
            detects (e.g. missing required claims, malformed structure).
    """
    settings = Settings()
    payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[_JWT_ALGORITHM])
    return AccessTokenClaims(**payload)


def generate_refresh_token() -> str:
    """Generate a fresh, cryptographically random opaque Refresh_Token.

    Uses `secrets.token_urlsafe`, backed by the OS's CSPRNG, so each call
    returns a value no attacker can feasibly predict or reproduce. Per
    Requirement 8.1, the caller (`app.auth.sessions.create_session`, task
    6.1) sets this value in an `httpOnly`, `Secure`, `SameSite=Strict`
    cookie and never persists the raw value itself -- only
    :func:`hash_refresh_token`'s output is stored, in a `Session_Record`.

    Returns:
        A URL-safe, random opaque token string. Different on every call.
    """
    return secrets.token_urlsafe(_REFRESH_TOKEN_BYTES)


def hash_refresh_token(token: str) -> str:
    """Hash `token` for storage/lookup in a `Session_Record`.

    Uses a plain SHA-256 hex digest -- deliberately NOT a slow/memory-hard
    hash like `app.auth.passwords`'s argon2id. That distinction is
    intentional, not an oversight: argon2id exists to slow down brute-force
    guessing of a *low-entropy, human-chosen* secret (a password). A
    Refresh_Token (from :func:`generate_refresh_token`) is a 256-bit CSPRNG
    value with no guessable structure, so there is nothing for a slow hash
    to usefully protect against -- an attacker who doesn't already have the
    raw token cannot feasibly guess it regardless of hash speed. SHA-256
    here only needs to (a) be deterministic, so the same raw token always
    looks up the same `Session_Record` by `refreshTokenHash`, and (b) keep
    the raw token out of the database, so a database read alone never
    discloses a usable credential, per Requirement 8.2 and design Property
    4. A slow hash would only add needless latency to every refresh
    request.

    Args:
        token: The raw Refresh_Token to hash.

    Returns:
        The lowercase hex-encoded SHA-256 digest of `token`. Never equal to
        `token` itself.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
