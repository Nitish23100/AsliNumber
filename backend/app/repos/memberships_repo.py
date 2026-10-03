"""`memberships` collection repository.

Scoping convention: every method takes an explicit `userId` and/or
`tenantId` parameter that narrows the query to one user's memberships,
one (user, tenant) pair, or similarly bounded scope. There is no method
that lists every membership across all users and tenants.
"""

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.database import Database

from app.models.membership import Membership
from app.models.role import Role

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

    def list_by_tenant(self, tenant_id: ObjectId | str) -> list[Membership]:
        """List every membership within `tenant_id`.

        Scoped by `tenantId` -- used by `GET /tenant/members`
        (P2 task 11.4), never an unscoped cross-tenant scan.
        """
        cursor = self._collection.find({"tenantId": ObjectId(tenant_id)})
        return [Membership(**document) for document in cursor]

    def find_by_id(
        self, tenant_id: ObjectId | str, membership_id: ObjectId | str
    ) -> Membership | None:
        """Look up a membership by `_id`, scoped by `tenantId`, or `None`.

        The `tenantId` filter is part of the query itself (not a
        post-fetch check), so a membership id that belongs to a
        different tenant can never match -- this is what makes
        cross-tenant references behave as 404s rather than leaking
        another tenant's membership.
        """
        document = self._collection.find_one(
            {"_id": ObjectId(membership_id), "tenantId": ObjectId(tenant_id)}
        )
        return Membership(**document) if document is not None else None

    def update_role(
        self, tenant_id: ObjectId | str, membership_id: ObjectId | str, role: Role
    ) -> Membership | None:
        """Change a membership's `role`, scoped by `(tenantId, _id)`.

        Returns the updated `Membership`, or `None` if no membership
        matches that `(tenantId, _id)` pair.
        """
        document = self._collection.find_one_and_update(
            {"_id": ObjectId(membership_id), "tenantId": ObjectId(tenant_id)},
            {"$set": {"role": role.value}},
            return_document=ReturnDocument.AFTER,
        )
        return Membership(**document) if document is not None else None

    def delete(self, tenant_id: ObjectId | str, membership_id: ObjectId | str) -> bool:
        """Remove a membership, scoped by `(tenantId, _id)`.

        Returns whether a document was actually deleted.
        """
        result = self._collection.delete_one(
            {"_id": ObjectId(membership_id), "tenantId": ObjectId(tenant_id)}
        )
        return result.deleted_count > 0

    def count_by_tenant_and_role(self, tenant_id: ObjectId | str, role: Role) -> int:
        """Count memberships in `tenant_id` currently holding `role`.

        Used by `app.services.tenant_service.assert_retains_an_owner`
        (the Last_Owner_Rule) to confirm a change would not leave the
        tenant with zero owners.
        """
        return self._collection.count_documents(
            {"tenantId": ObjectId(tenant_id), "role": role.value}
        )
