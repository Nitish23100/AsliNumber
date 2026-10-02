"""Integration tests for `app.repos.memberships_repo`.

Covers the create+find round trip and the unique compound index on
`(userId, tenantId)`, per task 4.2's testing checklist. Runs against the
in-memory `mongomock` database fixture (see `conftest.py` for why).
"""

import pytest
from bson import ObjectId
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from app.models.membership import Membership
from app.repos.memberships_repo import MembershipsRepo


def test_create_and_find_by_user_and_tenant_round_trip(db: Database) -> None:
    repo = MembershipsRepo(db)
    user_id, tenant_id = ObjectId(), ObjectId()
    membership = Membership(userId=user_id, tenantId=tenant_id, role="admin")

    created = repo.create(membership)
    found = repo.find_by_user_and_tenant(user_id, tenant_id)

    assert found is not None
    assert found.id == created.id
    assert found.role == "admin"


def test_find_by_user_and_tenant_returns_none_when_absent(db: Database) -> None:
    repo = MembershipsRepo(db)

    assert repo.find_by_user_and_tenant(ObjectId(), ObjectId()) is None


def test_find_all_by_user_returns_every_membership_for_that_user(db: Database) -> None:
    repo = MembershipsRepo(db)
    user_id = ObjectId()
    other_user_id = ObjectId()
    tenant_a, tenant_b = ObjectId(), ObjectId()

    repo.create(Membership(userId=user_id, tenantId=tenant_a, role="owner"))
    repo.create(Membership(userId=user_id, tenantId=tenant_b, role="viewer"))
    repo.create(Membership(userId=other_user_id, tenantId=tenant_a, role="admin"))

    found = repo.find_all_by_user(user_id)

    assert len(found) == 2
    assert {m.tenantId for m in found} == {tenant_a, tenant_b}


def test_duplicate_user_tenant_pair_raises_duplicate_key_error(db: Database) -> None:
    repo = MembershipsRepo(db)
    user_id, tenant_id = ObjectId(), ObjectId()
    repo.create(Membership(userId=user_id, tenantId=tenant_id, role="owner"))

    with pytest.raises(DuplicateKeyError):
        repo.create(Membership(userId=user_id, tenantId=tenant_id, role="viewer"))
