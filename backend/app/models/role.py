"""Role enum and the fixed role ordering used for RBAC comparisons.

Per the design's Correctness Properties (Property 7: "Role ordering
determines access"), role comparison must not rely on enum declaration
order alone. `Role.rank` gives each member an explicit, testable integer
rank so `require_role` (task 7.1) can compare a requester's role against a
route's configured minimum with a simple `>=` on `rank`.

Also defines `AccessTokenClaims`, the decoded shape of an Access_Token's
payload (`sub`, `tid`, `role`, `jti`, `iat`, `exp`), per the design's
`backend/app/auth/tokens.py` component:
`decode_access_token(token: str) -> AccessTokenClaims`.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class Role(StrEnum):
    """A membership's role within a tenant.

    Ordering is fixed per the design: owner > admin > analyst > viewer.
    """

    OWNER = "owner"
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"

    @property
    def rank(self) -> int:
        """Return this role's rank in the fixed ordering.

        Higher rank means more access. `owner` is the highest rank, `viewer`
        the lowest. `require_role` compares ranks with `>=` rather than
        relying on `Enum` member declaration order, so the ordering stays
        explicit and independently testable.
        """
        return _ROLE_RANK[self]


# Module-level ordering list, lowest to highest access. `Role.rank` derives
# from this list so there is exactly one place that defines the ordering.
ROLE_ORDER: list[Role] = [Role.VIEWER, Role.ANALYST, Role.ADMIN, Role.OWNER]

_ROLE_RANK: dict[Role, int] = {role: index for index, role in enumerate(ROLE_ORDER)}


class AccessTokenClaims(BaseModel):
    """Decoded claims of an Access_Token, per Requirement 7.1.

    `sub` is the user id, `tid` the tenant id, `role` the membership role
    scoped by this token, `jti` a unique token id, `iat`/`exp` the issued-at
    and expiry timestamps.
    """

    sub: str
    tid: str
    role: Role
    jti: str
    iat: datetime
    exp: datetime
