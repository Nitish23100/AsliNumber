"""`tenants` collection repository.

Scoping convention (per the design's repository layout note, adapted for
this phase since `TenantContext` -- the full project plan's dependency for
scoping repo calls -- doesn't exist until task 7.1): every method here
takes an explicit id that narrows its query to a single document or a
single owner. There is no method that lists or scans the whole
collection unscoped.

`tenants` is the scope root itself (there is no "tenant of a tenant"), so
its own lookups are scoped by the tenant's own identity -- `slug` or
`_id` -- rather than by a *different* tenant/user id the way
`users_repo`/`memberships_repo`/`sessions_repo` are scoped by `userId`/
`tenantId`. Both `slug` and `_id` are unique keys that identify at most
one document, so neither lookup is an unscoped scan.
"""

from bson import ObjectId
from pymongo.database import Database

from app.models.tenant import Tenant

COLLECTION_NAME = "tenants"


def create_indexes(db: Database) -> None:
    """Create this collection's indexes idempotently.

    Unique index on `slug`, per the design's Data Models section. Mongo's
    `create_index` is itself idempotent for an identical spec, so calling
    this on every app startup (see `app/repos/__init__.py:create_indexes`)
    is safe and never duplicates or errors on an already-present index.
    """
    db[COLLECTION_NAME].create_index("slug", unique=True)


class TenantsRepo:
    """Repository for the `tenants` collection."""

    def __init__(self, db: Database) -> None:
        self._db = db

    @property
    def _collection(self):
        return self._db[COLLECTION_NAME]

    def create(self, tenant: Tenant) -> Tenant:
        """Insert `tenant` and return it with its persisted `_id`.

        Raises `pymongo.errors.DuplicateKeyError` if `tenant.slug` already
        exists, per the unique index on `slug`.
        """
        document = tenant.model_dump(by_alias=True)
        self._collection.insert_one(document)
        return tenant

    def find_by_slug(self, slug: str) -> Tenant | None:
        """Look up a tenant by its unique `slug`, or `None` if absent."""
        document = self._collection.find_one({"slug": slug})
        return Tenant(**document) if document is not None else None

    def find_by_id(self, tenant_id: ObjectId | str) -> Tenant | None:
        """Look up a tenant by its `_id`, or `None` if absent."""
        document = self._collection.find_one({"_id": ObjectId(tenant_id)})
        return Tenant(**document) if document is not None else None
