"""`memberships` collection repository.

Scoping convention: every method takes an explicit `userId` and/or
`tenantId` parameter that narrows the query to one user's memberships,
one (user, tenant) pair, or similarly bounded scope. There is no method
that lists every membership across all users and tenants.
"""

from bson import ObjectId
from pymongo.database import Database

from app.models.membership import Membership

COLLECTION_NAME = "memberships"


def create_indexes(db: Database) -> None:
    """Create this collection's indexes idempotently.

    Unique compound index on `(userId, tenantId)`, per the design's Data
    Models section -- a user can hold at most one membership (and
    therefore one role) per tenant.
    """
    db[COLLECTION_NAME].create_index([("userId", 1), ("tenantId", 1)], unique=True)


class MembershipsRepo:
    """Repository for the `memberships` collection."""

    def __init__(self, db: Database) -> None:
        self._db = db

    @property
    def _collection(self):
        return self._db[COLLECTION_NAME]

    def create(self, membership: Membership) -> Membership:
        """Insert `membership` and return it with its persisted `_id`.

        Raises `pymongo.errors.DuplicateKeyError` if a membership already
        exists for `(membership.userId, membership.tenantId)`, per the
        unique compound index.
        """
        document = membership.model_dump(by_alias=True)
        self._collection.insert_one(document)
        return membership

    def find_by_user_and_tenant(
        self, user_id: ObjectId | str, tenant_id: ObjectId | str
    ) -> Membership | None:
        """Look up the membership for one (user, tenant) pair, or `None`."""
        document = self._collection.find_one(
            {"userId": ObjectId(user_id), "tenantId": ObjectId(tenant_id)}
        )
        return Membership(**document) if document is not None else None

    def find_all_by_user(self, user_id: ObjectId | str) -> list[Membership]:
        """List every membership (and therefore every tenant) for `user_id`.

        Scoped by `userId`, not an unscoped scan -- used by the future
        `/auth/me` (returns a user's memberships) and `/auth/switch-tenant`
        (needs to confirm the requested tenant is among the user's
        memberships) routes, task 9.3.
        """
        cursor = self._collection.find({"userId": ObjectId(user_id)})
        return [Membership(**document) for document in cursor]
