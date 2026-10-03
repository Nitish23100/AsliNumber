"""`audit_log` collection repository.

Append-only: no method on this repository updates or deletes an existing
entry. `hash_client_ip` is shared by every P2 router rather than each
router duplicating its own copy, matching the existing pattern in
`backend/app/api/routers/auth.py` (which has its own private
`_hash_client_ip` helper P2 does not touch) but centralized here since
multiple P2 routers need the identical logic.
"""

import hashlib
from datetime import UTC, datetime

from bson import ObjectId
from pymongo.database import Database

from app.models.audit_log_entry import AuditLogEntry, AuditTarget

COLLECTION_NAME = "audit_log"


def create_indexes(db: Database) -> None:
    """Create this collection's indexes idempotently.

    Index on `(tenantId, at desc)` for the common "recent activity for
    this tenant" query; index on `(tenantId, target.id)` for "every
    change made to this specific resource."
    """
    collection = db[COLLECTION_NAME]
    collection.create_index([("tenantId", 1), ("at", -1)])
    collection.create_index([("tenantId", 1), ("target.id", 1)])


def hash_client_ip(salt: str, ip: str) -> str:
    """Salted hash of a client IP, never the raw IP, per Requirement 9.3."""
    return hashlib.sha256(f"{salt}:{ip}".encode()).hexdigest()


class AuditLogRepo:
    """Repository for the append-only `audit_log` collection."""

    def __init__(self, db: Database) -> None:
        self._db = db

    @property
    def _collection(self):
        return self._db[COLLECTION_NAME]

    def write_entry(
        self,
        tenant_id: ObjectId | str,
        user_id: ObjectId | str,
        action: str,
        target: AuditTarget,
        ip_hash: str,
        *,
        before: dict | None = None,
        after: dict | None = None,
    ) -> AuditLogEntry:
        """Append one audit entry. Never updates or deletes an existing one."""
        entry = AuditLogEntry(
            tenantId=ObjectId(tenant_id),
            userId=ObjectId(user_id),
            action=action,
            target=target,
            before=before,
            after=after,
            ipHash=ip_hash,
            at=datetime.now(UTC),
        )
        document = entry.model_dump(by_alias=True)
        self._collection.insert_one(document)
        return entry

    def list_by_tenant(
        self,
        tenant_id: ObjectId | str,
        *,
        action: str | None = None,
        user_id: ObjectId | str | None = None,
        target_id: str | None = None,
        cursor: ObjectId | str | None = None,
        limit: int = 50,
    ) -> list[AuditLogEntry]:
        """List audit entries for one tenant, filterable by action/userId/target.id.

        Scoped by `tenantId`; every additional filter is optional and
        combined with AND. Newest-first (`at` descending), cursor-
        paginated by `_id` of the last item from a previous page.
        """
        query: dict = {"tenantId": ObjectId(tenant_id)}
        if action is not None:
            query["action"] = action
        if user_id is not None:
            query["userId"] = ObjectId(user_id)
        if target_id is not None:
            query["target.id"] = target_id
        if cursor is not None:
            query["_id"] = {"$lt": ObjectId(cursor)}

        found = self._collection.find(query).sort([("at", -1), ("_id", -1)]).limit(limit)
        return [AuditLogEntry(**document) for document in found]
