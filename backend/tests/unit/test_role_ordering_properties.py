"""Property-based test for backend.app.auth.deps.require_role (Property 7).

Validates: Requirements 10.2, 10.3.
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.auth.deps import TenantContext, require_role
from app.core.errors import AppError
from app.models.role import AccessTokenClaims, Role

_role = st.sampled_from(list(Role))


def _make_context(role: Role) -> TenantContext:
    claims = AccessTokenClaims(
        sub="user-1",
        tid="tenant-1",
        role=role,
        jti="jti-1",
        iat="2026-01-01T00:00:00Z",
        exp="2026-01-01T00:15:00Z",
    )
    return TenantContext(claims)


# Feature: aslinumber-p1-foundation, Property 7: Role ordering determines access
@settings(max_examples=100)
@given(requester_role=_role, minimum_role=_role)
def test_role_ordering_determines_access(requester_role: Role, minimum_role: Role) -> None:
    """For any requester role and any route's configured minimum role, the

    RBAC_Guard (the real `require_role`-produced check function) allows
    the request iff the requester's rank is greater than or equal to the
    minimum's rank.
    """
    should_allow = requester_role.rank >= minimum_role.rank
    check = require_role(minimum_role)
    context = _make_context(requester_role)

    if should_allow:
        result = check(context=context)
        assert result is context
    else:
        with pytest.raises(AppError) as exc_info:
            check(context=context)
        assert exc_info.value.status_code == 403
