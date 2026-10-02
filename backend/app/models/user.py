"""`users` collection domain model.

Fields follow the design's Data Models section: `email` (lowercased, unique
index created by the repository layer in task 4.2), `passwordHash`
(argon2id, produced by `app.auth.passwords`), `name`, `status`,
`failedLogins` (default 0), and `lockedUntil` (nullable, set by
`app.auth.lockout` per Requirement 9).
"""

from datetime import datetime

from pydantic import field_validator

from app.models.common import MongoBaseModel


class User(MongoBaseModel):
    """A user document."""

    email: str
    passwordHash: str
    name: str
    status: str
    failedLogins: int = 0
    lockedUntil: datetime | None = None

    @field_validator("email")
    @classmethod
    def _lowercase_email(cls, value: str) -> str:
        return value.lower()
