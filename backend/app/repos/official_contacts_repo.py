"""`official_contacts` collection repository.

Scoping convention: every method takes an explicit `tenantId`. There is
no `delete` method on this repository, per plan Sec7.2's "entries are
deprecated, never deleted" rule -- a hard delete is structurally
unreachable from the API, not merely unrouted.
"""

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.database import Database

from app.models.official_contact import OfficialContact

COLLECTION_NAME = "official_contacts"


def create_indexes(db: Database) -> None:
    """Create this collection's indexes idempotently.

    Unique compound index on `(tenantId, brandId, e164)` -- extends plan
    Sec7.2's `(brandId, e164)` uniqueness with the mandatory `tenantId`
    prefix per plan Sec7.1's indexing convention. A secondary index on
    `(tenantId, e164)` supports a future reverse lookup (a number ->
    which brands it's registered against).
    """
    collection = db[COLLECTION_NAME]
    collection.create_index([("tenantId", 1), ("brandId", 1), ("e164", 1)], unique=True)
    collection.create_index([("tenantId", 1), ("e164", 1)])


class OfficialContactsRepo:
    """Repository for the `official_contacts` collection."""

    def __init__(self, db: Database) -> None:
        self._db = db

    @property
    def _collection(self):
        return self._db[COLLECTION_NAME]

    def create(self, contact: OfficialContact) -> OfficialContact:
        """Insert `contact` and return it with its persisted `_id`.

        Raises `pymongo.errors.DuplicateKeyError` if an entry with the
        same `(tenantId, brandId, e164)` already exists.
        """
        document = contact.model_dump(by_alias=True)
        self._collection.insert_one(document)
        return contact

    def find_by_id(
        self, tenant_id: ObjectId | str, contact_id: ObjectId | str
    ) -> OfficialContact | None:
        """Look up an official contact by `_id`, scoped by `tenantId`, or `None`."""
        document = self._collection.find_one(
            {"_id": ObjectId(contact_id), "tenantId": ObjectId(tenant_id)}
        )
        return OfficialContact(**document) if document is not None else None

    def list_by_brand(
        self, tenant_id: ObjectId | str, brand_id: ObjectId | str
    ) -> list[OfficialContact]:
        """List every official contact for one brand, including deprecated entries.

        The router does not filter by `status` -- callers that only want
        active entries filter the returned list themselves, since the
        registry's full history (including deprecated entries) is
        legitimate information a tenant member can see.
        """
        cursor = self._collection.find(
            {"tenantId": ObjectId(tenant_id), "brandId": ObjectId(brand_id)}
        )
        return [OfficialContact(**document) for document in cursor]

    def update(
        self, tenant_id: ObjectId | str, contact_id: ObjectId | str, changes: dict
    ) -> OfficialContact | None:
        """Apply `changes` to an official contact, scoped by `(tenantId, _id)`.

        Returns the updated `OfficialContact`, or `None` if no entry
        matches that pair. There is no `delete` method on this class.
        """
        document = self._collection.find_one_and_update(
            {"_id": ObjectId(contact_id), "tenantId": ObjectId(tenant_id)},
            {"$set": changes},
            return_document=ReturnDocument.AFTER,
        )
        return OfficialContact(**document) if document is not None else None
