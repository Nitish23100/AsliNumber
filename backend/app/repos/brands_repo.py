"""`brands` collection repository.

Scoping convention: every method takes an explicit `tenantId` that
narrows the operation to one tenant's brands. `find_by_id` scopes
`tenantId` inside the query filter itself (not a post-fetch check), so a
brand id belonging to a different tenant can never match -- this is what
makes a cross-tenant brand reference behave as a 404 instead of leaking
another tenant's data.
"""

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.database import Database

from app.models.brand import Brand

COLLECTION_NAME = "brands"
OFFICIAL_CONTACTS_COLLECTION_NAME = "official_contacts"

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200


def create_indexes(db: Database) -> None:
    """Create this collection's indexes idempotently.

    Unique compound index on `(tenantId, slug)`, per the design's Data
    Models section -- a slug is unique within a tenant, but the same slug
    may exist independently in a different tenant. A secondary index on
    `(tenantId, officialDomains.domain)` supports future domain-based
    lookups (e.g. matching an observed source domain back to a brand).
    """
    collection = db[COLLECTION_NAME]
    collection.create_index([("tenantId", 1), ("slug", 1)], unique=True)
    collection.create_index([("tenantId", 1), ("officialDomains.domain", 1)])


class BrandsRepo:
    """Repository for the `brands` collection."""

    def __init__(self, db: Database) -> None:
        self._db = db

    @property
    def _collection(self):
        return self._db[COLLECTION_NAME]

    def create(self, brand: Brand) -> Brand:
        """Insert `brand` and return it with its persisted `_id`.

        Raises `pymongo.errors.DuplicateKeyError` if a brand with
        `brand.slug` already exists for `brand.tenantId`, per the unique
        compound index.
        """
        document = brand.model_dump(by_alias=True)
        self._collection.insert_one(document)
        return brand

    def find_by_slug(self, tenant_id: ObjectId | str, slug: str) -> Brand | None:
        """Look up a brand by its unique-per-tenant `slug`, or `None`."""
        document = self._collection.find_one({"tenantId": ObjectId(tenant_id), "slug": slug})
        return Brand(**document) if document is not None else None

    def find_by_id(self, tenant_id: ObjectId | str, brand_id: ObjectId | str) -> Brand | None:
        """Look up a brand by `_id`, scoped by `tenantId`, or `None`."""
        document = self._collection.find_one(
            {"_id": ObjectId(brand_id), "tenantId": ObjectId(tenant_id)}
        )
        return Brand(**document) if document is not None else None

    def list_by_tenant(
        self,
        tenant_id: ObjectId | str,
        *,
        cursor: ObjectId | str | None = None,
        limit: int = DEFAULT_PAGE_SIZE,
    ) -> list[Brand]:
        """List brands within `tenant_id`, newest-id-last, cursor-paginated.

        `limit` is clamped to `MAX_PAGE_SIZE`. `cursor`, when given, is the
        `_id` of the last item from a previous page -- only brands with a
        strictly greater `_id` are returned, so pages do not overlap or
        skip entries as long documents are only ever appended, never
        reordered.
        """
        effective_limit = min(limit, MAX_PAGE_SIZE)
        query: dict = {"tenantId": ObjectId(tenant_id)}
        if cursor is not None:
            query["_id"] = {"$gt": ObjectId(cursor)}
        found = self._collection.find(query).sort("_id", 1).limit(effective_limit)
        return [Brand(**document) for document in found]

    def update(
        self, tenant_id: ObjectId | str, brand_id: ObjectId | str, changes: dict
    ) -> Brand | None:
        """Apply `changes` to a brand and increment its `version`, atomically.

        Scoped by `(tenantId, _id)`. Returns the updated `Brand`, or
        `None` if no brand matches that pair. `changes` must not include
        `version` -- the increment is applied by this method, not the
        caller, so every accepted update increments by exactly 1.
        """
        document = self._collection.find_one_and_update(
            {"_id": ObjectId(brand_id), "tenantId": ObjectId(tenant_id)},
            {"$set": changes, "$inc": {"version": 1}},
            return_document=ReturnDocument.AFTER,
        )
        return Brand(**document) if document is not None else None

    def count_official_contacts(self, tenant_id: ObjectId | str, brand_id: ObjectId | str) -> int:
        """Count every Official_Contact (any status) for one brand.

        Delegates to the `official_contacts` collection directly rather
        than importing `OfficialContactsRepo`, avoiding a circular import
        between the two repository modules; both operate on the same
        `(tenantId, brandId)` scope.
        """
        return self._db[OFFICIAL_CONTACTS_COLLECTION_NAME].count_documents(
            {"tenantId": ObjectId(tenant_id), "brandId": ObjectId(brand_id)}
        )
