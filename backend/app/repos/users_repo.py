"""`users` collection repository.

Scoping convention: every method takes an explicit scope parameter -- the
user's own `email` or `_id` -- that narrows the operation to at most one
document. There is no method that lists or scans every user. (`users` is
not itself tenant-scoped per the design's Data Models section -- a user
account can hold memberships across multiple tenants -- so its natural
scope key is the user's own identity, mirroring `tenants_repo`.)
"""

from datetime import datetime

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.database import Database

from app.models.user import User

COLLECTION_NAME = "users"


def create_indexes(db: Database) -> None:
    """Create this collection's indexes idempotently.

    Unique index on `email`, per the design's Data Models section.
    """
    db[COLLECTION_NAME].create_index("email", unique=True)


class UsersRepo:
    """Repository for the `users` collection."""

    def __init__(self, db: Database) -> None:
        self._db = db

    @property
    def _collection(self):
        return self._db[COLLECTION_NAME]

    def create(self, user: User) -> User:
        """Insert `user` and return it with its persisted `_id`.

        Raises `pymongo.errors.DuplicateKeyError` if `user.email` (already
        lowercased by the `User` model's validator) already exists, per
        the unique index on `email`.
        """
        document = user.model_dump(by_alias=True)
        self._collection.insert_one(document)
        return user

    def find_by_email(self, email: str) -> User | None:
        """Look up a user by email, or `None` if absent.

        Lowercases `email` before querying so lookups match the model's
        own lowercasing convention (`User._lowercase_email`), regardless
        of the case the caller passes in.
        """
        document = self._collection.find_one({"email": email.lower()})
        return User(**document) if document is not None else None

    def find_by_id(self, user_id: ObjectId | str) -> User | None:
        """Look up a user by `_id`, or `None` if absent."""
        document = self._collection.find_one({"_id": ObjectId(user_id)})
        return User(**document) if document is not None else None

    def increment_failed_logins(self, user_id: ObjectId | str) -> int:
        """Atomically increment `failedLogins` for `user_id` and return the new count.

        Used by `app.auth.lockout.record_failed_login` (task 6.4) to decide
        whether the increment just reached the lockout threshold. The
        increment and the read of the resulting value happen as a single
        atomic `$inc` + `find_one_and_update`, so concurrent failed logins
        for the same account can never under-count.

        Raises `ValueError` if `user_id` does not match any document.
        """
        document = self._collection.find_one_and_update(
            {"_id": ObjectId(user_id)},
            {"$inc": {"failedLogins": 1}},
            return_document=ReturnDocument.AFTER,
        )
        if document is None:
            raise ValueError(f"No user found with id {user_id!r}")
        return document["failedLogins"]

    def set_locked_until(self, user_id: ObjectId | str, locked_until: datetime | None) -> None:
        """Set (or clear, with `None`) `lockedUntil` for `user_id`."""
        self._collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"lockedUntil": locked_until}},
        )

    def reset_failed_logins(self, user_id: ObjectId | str) -> None:
        """Reset `failedLogins` to 0 for `user_id`, per a successful login."""
        self._collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"failedLogins": 0}},
        )
