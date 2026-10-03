"""`audit_log` collection domain model.

Fields follow the design's Data Models section / plan Sec7.3: `tenantId`,
`userId`, `action`, `target`, `before`/`after` (optional, for config
changes), `ipHash` (a salted hash of the request's client IP, never the
raw IP), `at`. Append-only: no repository method in this phase updates
or deletes an existing entry.
"""

from datetime import datetime

from pydantic import BaseModel

from app.models.common import MongoBaseModel, PyObjectId


class AuditTarget(BaseModel):
    """What an audit entry's action was taken against."""

    type: str
    id: str


class AuditLogEntry(MongoBaseModel):
    """One append-only record of a mutating action taken by an authenticated user."""

    tenantId: PyObjectId
    userId: PyObjectId
    action: str
    target: AuditTarget
    before: dict | None = None
    after: dict | None = None
    ipHash: str
    at: datetime


# Co-located with the model, same convention as app.models.brand.JSON_SCHEMA.
JSON_SCHEMA: dict = {
    "bsonType": "object",
    "required": ["tenantId", "userId", "action", "target", "ipHash", "at"],
    "properties": {
        "tenantId": {"bsonType": "objectId"},
        "userId": {"bsonType": "objectId"},
        "action": {"bsonType": "string"},
        "target": {"bsonType": "object"},
        "before": {"bsonType": ["object", "null"]},
        "after": {"bsonType": ["object", "null"]},
        "ipHash": {"bsonType": "string"},
        "at": {"bsonType": "date"},
    },
}
