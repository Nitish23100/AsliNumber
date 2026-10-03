"""Tenant_Service: the owner-protection and last-owner membership rules.

Implements the design's ``backend/app/services/tenant_service.py``
component: ``assert_can_modify_membership`` (task 6.1, the
Owner_Protection_Rule) and ``assert_retains_an_owner`` (task 6.3, the
Last_Owner_Rule).

Per the design's Error Handling section, the Owner_Protection_Rule check
runs before the Last_Owner_Rule check at the call site (the tenant
router), so an admin attempting to touch an owner membership always sees
403 regardless of how many owners currently exist -- the two rules answer
different questions ("may this requester touch this target at all" vs.
"would this leave zero owners") and this fixed evaluation order keeps the
response deterministic for a request that could technically trigger
either.
"""

from bson import ObjectId

from app.core.errors import AppError, ErrorCode
from app.models.membership import Membership
from app.models.role import Role
from app.repos.memberships_repo import MembershipsRepo


def assert_can_modify_membership(requester_role: Role, target_membership: Membership) -> None:
    """Implement the Owner_Protection_Rule (Requirement 8.6 / Property 13).

    Only a requester with ``role=owner`` may modify or remove a
    membership whose own ``role`` is ``owner``. Raises
    ``AppError(FORBIDDEN)`` if ``requester_role != Role.OWNER`` and
    ``target_membership.role == Role.OWNER``.
    """
    if requester_role != Role.OWNER and target_membership.role == Role.OWNER:
        raise AppError(
            ErrorCode.FORBIDDEN,
            "Only an owner may modify or remove another owner's membership.",
        )


def assert_retains_an_owner(
    memberships_repo: MembershipsRepo,
    tenant_id: ObjectId | str,
    excluding_membership_id: ObjectId | str,
    new_role: Role | None,
) -> None:
    """Implement the Last_Owner_Rule (Requirement 8.5 / Property 12).

    A tenant must retain at least one membership with ``role=owner`` at
    all times. ``excluding_membership_id`` is the membership being
    changed or removed; ``new_role`` is the role it would hold afterward
    (``None`` for a removal). Raises ``AppError(CONFLICT, status_code=409)``
    if, after excluding ``excluding_membership_id`` from the current
    owner count and adding it back only when ``new_role == Role.OWNER``,
    the resulting owner count would be zero.
    """
    current_owner_count = memberships_repo.count_by_tenant_and_role(tenant_id, Role.OWNER)

    target_membership = memberships_repo.find_by_id(tenant_id, excluding_membership_id)
    target_was_owner = target_membership is not None and target_membership.role == Role.OWNER

    resulting_owner_count = current_owner_count
    if target_was_owner:
        resulting_owner_count -= 1
    if new_role == Role.OWNER:
        resulting_owner_count += 1

    if resulting_owner_count <= 0:
        raise AppError(
            ErrorCode.CONFLICT,
            "This tenant must retain at least one membership with role=owner.",
        )
