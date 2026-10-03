"""Property-based test for the last-owner rule (Property 12).

Validates: Requirements 8.5.
"""

import mongomock
from bson import ObjectId
from hypothesis import given, settings
from hypothesis import strategies as st
from pymongo.database import Database

from app.core.errors import AppError, ErrorCode
from app.models.membership import Membership
from app.models.role import Role
from app.repos import create_indexes
from app.repos.memberships_repo import MembershipsRepo
from app.services.tenant_service import assert_retains_an_owner


def _fresh_db() -> Database:
    client = mongomock.MongoClient("mongodb://localhost:27017/aslinumber_test", tz_aware=True)
    db = client.get_default_database()
    create_indexes(db)
    return db


_other_role = st.sampled_from([Role.ADMIN, Role.ANALYST, Role.VIEWER])


# Feature: aslinumber-p2-tenancy-brands, Property 12: The last-owner rule
@settings(max_examples=100)
@given(num_owners=st.integers(min_value=1, max_value=5), demote_to=_other_role)
def test_last_owner_rule_across_owner_counts(num_owners: int, demote_to: Role) -> None:
    """For a tenant with exactly one owner, demoting or removing that

    owner is rejected with HTTP 409; for a tenant with two or more
    owners, demoting or removing any one of them succeeds and leaves at
    least one owner remaining.
    """
    db = _fresh_db()
    repo = MembershipsRepo(db)
    tenant_id = ObjectId()

    owner_memberships = [
        repo.create(Membership(userId=ObjectId(), tenantId=tenant_id, role=Role.OWNER))
        for _ in range(num_owners)
    ]
    # One non-owner membership present too, to confirm it never counts
    # toward the owner tally.
    repo.create(Membership(userId=ObjectId(), tenantId=tenant_id, role=Role.VIEWER))

    target = owner_memberships[0]

    if num_owners == 1:
        try:
            assert_retains_an_owner(repo, tenant_id, target.id, demote_to)
            raised = False
        except AppError as exc:
            raised = True
            assert exc.code == ErrorCode.CONFLICT
            assert exc.status_code == 409
        assert raised

        try:
            assert_retains_an_owner(repo, tenant_id, target.id, None)
            raised_delete = False
        except AppError as exc:
            raised_delete = True
            assert exc.code == ErrorCode.CONFLICT
        assert raised_delete
    else:
        assert_retains_an_owner(repo, tenant_id, target.id, demote_to)  # must not raise
        repo.update_role(tenant_id, target.id, demote_to)
        remaining_owners = repo.count_by_tenant_and_role(tenant_id, Role.OWNER)
        assert remaining_owners >= 1
