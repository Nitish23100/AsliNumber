"""`sessions` collection repository.

Scoping convention: every method takes an explicit `session_id`,
`refresh_token_hash`, or similarly unique scope parameter that narrows the
operation to one record or one record's rotation chain. There is no
method that lists or scans every session.
"""

from bson import ObjectId
from pymongo.database import Database

from app.models.session import Session

COLLECTION_NAME = "sessions"


def create_indexes(db: Database) -> None:
    """Create this collection's indexes idempotently.

    - Unique index on `refreshTokenHash`, per the design's Data Models
      section.
    - TTL index on `expiresAt` (`expireAfterSeconds=0`): MongoDB's TTL
      monitor deletes a document once its `expiresAt` value is in the
      past, so expired Refresh_Token sessions are reaped automatically
      without any application-level cleanup job.
    """
    collection = db[COLLECTION_NAME]
    collection.create_index("refreshTokenHash", unique=True)
    collection.create_index("expiresAt", expireAfterSeconds=0)


class SessionsRepo:
    """Repository for the `sessions` collection."""

    def __init__(self, db: Database) -> None:
        self._db = db

    @property
    def _collection(self):
        return self._db[COLLECTION_NAME]

    def create(self, session: Session) -> Session:
        """Insert `session` and return it with its persisted `_id`.

        Raises `pymongo.errors.DuplicateKeyError` if `session.refreshTokenHash`
        already exists, per the unique index.
        """
        document = session.model_dump(by_alias=True)
        self._collection.insert_one(document)
        return session

    def find_by_refresh_hash(self, refresh_token_hash: str) -> Session | None:
        """Look up a session by its unique `refreshTokenHash`, or `None`."""
        document = self._collection.find_one({"refreshTokenHash": refresh_token_hash})
        return Session(**document) if document is not None else None

    def mark_rotated(self, session_id: ObjectId | str) -> None:
        """Mark the session identified by `session_id` as `rotated=True`."""
        self._collection.update_one(
            {"_id": ObjectId(session_id)},
            {"$set": {"rotated": True}},
        )

    def mark_revoked(self, session_id: ObjectId | str) -> None:
        """Mark the session identified by `session_id` as `revoked=True`."""
        self._collection.update_one(
            {"_id": ObjectId(session_id)},
            {"$set": {"revoked": True}},
        )

    def find_rotation_chain(self, session_id: ObjectId | str) -> list[Session]:
        """Return every session reachable from `session_id` via `rotatedFrom`.

        A rotation chain is, in practice, the linear linked list formed by
        `rotatedFrom` references (per the design: each rotation inserts one
        new Session_Record pointing `rotatedFrom` at the one it replaced).
        This walk doesn't assume linearity, though, since that's cheap
        insurance against any future case where more than one new session
        ends up pointing at the same `rotatedFrom` (a race, a bug, or a
        future feature): it is a full graph walk from `session_id`,
        covering

        1. backward: `session_id` and every ancestor reachable by
           following `rotatedFrom` pointers up to the chain's root (the
           session created at login, which has `rotatedFrom=None`), and
        2. forward: every descendant of every node found in step 1,
           i.e. every session whose `rotatedFrom` points at any node
           already visited, transitively.

        Used by `app.auth.sessions.revoke_chain` (task 6.1) to mark every
        record in the lineage `revoked=True` on refresh-token reuse,
        regardless of whether the reused token was near the root or
        somewhere in the middle of the chain.

        Returns the sessions in no particular guaranteed order. Returns an
        empty list if `session_id` does not match any document.
        """
        start_id = ObjectId(session_id)
        documents_by_id: dict[ObjectId, dict] = {}

        # Step 1: walk backward from start_id to the chain's root.
        current_id: ObjectId | None = start_id
        while current_id is not None and current_id not in documents_by_id:
            document = self._collection.find_one({"_id": current_id})
            if document is None:
                break
            documents_by_id[current_id] = document
            current_id = document.get("rotatedFrom")

        # Step 2: walk forward (BFS) from every node found so far, picking
        # up every descendant reachable by `rotatedFrom` pointing back at
        # an already-visited node. Repeat until a full pass finds nothing
        # new, so branching chains (more than one child per node) are
        # covered, not just the common linear case.
        frontier = list(documents_by_id.keys())
        while frontier:
            children_cursor = self._collection.find({"rotatedFrom": {"$in": frontier}})
            next_frontier: list[ObjectId] = []
            for child in children_cursor:
                child_id = child["_id"]
                if child_id not in documents_by_id:
                    documents_by_id[child_id] = child
                    next_frontier.append(child_id)
            frontier = next_frontier

        return [Session(**document) for document in documents_by_id.values()]
