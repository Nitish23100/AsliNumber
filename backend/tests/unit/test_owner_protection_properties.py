"""Property-based test for the owner-protection rule (Property 13).

Validates: Requirements 8.6.
"""

from bson import ObjectId
from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.errors import AppError, ErrorCode
from app.models.membership import Membership
from app.models.role import Role
from app.services.tenant_service import assert_can_modify_membership

_any_role = st.sampled_from(list(Role))


def _make_membership(role: Role) -> Membership:
    return Membership(userId=ObjectId(), tenantId=ObjectId(), role=role)


# Feature: aslinumber-p2-tenancy-brands, Property 13: The owner-protection
# rule
@settings(max_examples=100)
@given(requester_role=_any_role, target_role=_any_role)
def test_owner_protection_rule_across_roles(requester_role: Role, target_role: Role) -> None:
    """A requester whose role is not owner, acting against a target

    membership whose current role is owner, is rejected with HTTP 403,
    regardless of the specific change requested -- this includes, but is
    not limited to, Requirement 8.6's admin case, since the RBAC guard
    already restricts these routes to admin-and-above before this rule
    ever runs; every other combination succeeds.
    """
    target_membership = _make_membership(target_role)

    should_reject = requester_role != Role.OWNER and target_role == Role.OWNER

    if should_reject:
        try:
            assert_can_modify_membership(requester_role, target_membership)
            raised = False
        except AppError as exc:
            raised = True
            assert exc.code == ErrorCode.FORBIDDEN
            assert exc.status_code == 403
        assert raised
    else:
        assert_can_modify_membership(requester_role, target_membership)  # must not raise
