"""Property-based test for audit log filters returning exactly the matching subset (Property 15).

Validates: Requirements 9.2.
"""

import mongomock
from bson import ObjectId
from hypothesis import given, settings
from hypothesis import strategies as st
from pymongo.database import Database

from app.models.audit_log_entry import AuditTarget
from app.repos import create_indexes
from app.repos.audit_log_repo import AuditLogRepo

_actions = st.sampled_from(["brand_created", "brand_updated", "member_added"])


def _fresh_db() -> Database:
    client = mongomock.MongoClient("mongodb://localhost:27017/aslinumber_test", tz_aware=True)
    db = client.get_default_database()
    create_indexes(db)
    return db


# Feature: aslinumber-p2-tenancy-brands, Property 15: Audit log filters
# return exactly the matching subset
@settings(max_examples=100)
@given(
    entries=st.lists(
        st.tuples(
            _actions, st.integers(min_value=0, max_value=3), st.integers(min_value=0, max_value=3)
        ),
        min_size=0,
        max_size=15,
    )
)
def test_filtering_by_action_returns_exactly_the_matching_subset(
    entries: list[tuple[str, int, int]],
) -> None:
    """Filtering GET /audit-log's underlying query by action returns

    exactly the tenant-scoped entries whose action equals the filter
    value -- no more, no fewer.
    """
    db = _fresh_db()
    repo = AuditLogRepo(db)
    tenant_id = ObjectId()
    user_ids = [ObjectId() for _ in range(4)]

    expected_count_by_action: dict[str, int] = {}
    for action, user_index, _target_index in entries:
        repo.write_entry(
            tenant_id,
            user_ids[user_index],
            action,
            AuditTarget(type="brand", id=str(ObjectId())),
            "iphash",
        )
        expected_count_by_action[action] = expected_count_by_action.get(action, 0) + 1

    for action in {"brand_created", "brand_updated", "member_added"}:
        results = repo.list_by_tenant(tenant_id, action=action, limit=1000)
        assert len(results) == expected_count_by_action.get(action, 0)
        assert all(r.action == action for r in results)


@settings(max_examples=100)
@given(
    entries=st.lists(
        st.tuples(_actions, st.integers(min_value=0, max_value=3)),
        min_size=0,
        max_size=15,
    )
)
def test_filtering_by_user_id_returns_exactly_the_matching_subset(
    entries: list[tuple[str, int]],
) -> None:
    """Filtering by userId returns exactly the entries whose userId

    equals the filter value.
    """
    db = _fresh_db()
    repo = AuditLogRepo(db)
    tenant_id = ObjectId()
    user_ids = [ObjectId() for _ in range(4)]

    expected_count_by_user: dict[int, int] = {}
    for action, user_index in entries:
        repo.write_entry(
            tenant_id,
            user_ids[user_index],
            action,
            AuditTarget(type="brand", id=str(ObjectId())),
            "iphash",
        )
        expected_count_by_user[user_index] = expected_count_by_user.get(user_index, 0) + 1

    for user_index, user_id in enumerate(user_ids):
        results = repo.list_by_tenant(tenant_id, user_id=user_id, limit=1000)
        assert len(results) == expected_count_by_user.get(user_index, 0)
        assert all(r.userId == user_id for r in results)
