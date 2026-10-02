"""`sessions` collection domain model.

Fields follow the design's Data Models section: `userId`, `tenantId`,
`refreshTokenHash` (unique index, created by the repository layer in task
4.2), `expiresAt` (TTL index), `rotatedFrom` (nullable self-reference used
to walk the rotation chain, per `app.auth.sessions.rotate_session` /
`revoke_chain`), `rotated`, and `revoked`.
"""

from datetime import datetime

from app.models.common import MongoBaseModel, PyObjectId


class Session(MongoBaseModel):
    """A session document storing only the hash of a Refresh_Token."""

    userId: PyObjectId
    tenantId: PyObjectId
    refreshTokenHash: str
    expiresAt: datetime
    rotatedFrom: PyObjectId | None = None
    rotated: bool = False
    revoked: bool = False
