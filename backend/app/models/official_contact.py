"""`official_contacts` collection domain model.

Fields follow the design's Data Models section / plan Sec7.2: `tenantId`,
`brandId`, `e164` (validated against E164_PATTERN at the model layer, so
no malformed number can ever be constructed, not just rejected by the
API layer), `display`, `contactTypes`, `scope` (optional), `authority`
(set by `app.services.brand_service.resolve_authority`'s Authority_Rule),
`method` (always `manual` for anything created through this phase's
endpoints), `source`, `retrievedAt`, `status` (deprecated, never
deleted), `validFrom`, `validTo` (optional).

`E164_PATTERN` is defined once here and imported by `brand_service` and
by the Hypothesis property tests, so there is exactly one place the
pattern is written, per plan Sec7.1.
"""

import re
from datetime import datetime

from pydantic import BaseModel, field_validator

from app.models.brand import Authority, ContactMethod, ContactStatus
from app.models.common import MongoBaseModel, PyObjectId

E164_PATTERN = re.compile(r"^\+[1-9]\d{6,14}$")


class ContactScope(BaseModel):
    """Where/in which languages an Official_Contact applies, if restricted."""

    cities: list[str] = []
    languages: list[str] = []


class ContactSource(BaseModel):
    """Where a manually-entered Official_Contact's number was found."""

    url: str
    registeredDomain: str
    evidenceId: PyObjectId | None = None
    observedText: str | None = None


class OfficialContact(MongoBaseModel):
    """A tenant-scoped registry entry linking a brand to a phone number."""

    tenantId: PyObjectId
    brandId: PyObjectId
    e164: str
    display: str
    contactTypes: list[str]
    scope: ContactScope | None = None
    authority: Authority
    method: ContactMethod
    source: ContactSource
    retrievedAt: datetime
    status: ContactStatus = ContactStatus.ACTIVE
    validFrom: datetime
    validTo: datetime | None = None

    @field_validator("e164")
    @classmethod
    def _validate_e164(cls, value: str) -> str:
        if not E164_PATTERN.match(value):
            raise ValueError(f"{value!r} is not a valid E.164 number")
        return value


# Co-located with the model, same convention as app.models.brand.JSON_SCHEMA.
# Enforces the Authority/ContactMethod/ContactStatus enum value sets and
# the e164 regex pattern -- the two places this pattern and these enums
# are written (here and in the Pydantic model above) are checked for
# drift by the task 1.5 unit test.
JSON_SCHEMA: dict = {
    "bsonType": "object",
    "required": [
        "tenantId",
        "brandId",
        "e164",
        "display",
        "authority",
        "method",
        "status",
        "validFrom",
    ],
    "properties": {
        "tenantId": {"bsonType": "objectId"},
        "brandId": {"bsonType": "objectId"},
        "e164": {"bsonType": "string", "pattern": E164_PATTERN.pattern},
        "display": {"bsonType": "string"},
        "contactTypes": {"bsonType": "array"},
        "scope": {"bsonType": ["object", "null"]},
        "authority": {"bsonType": "string", "enum": [a.value for a in Authority]},
        "method": {"bsonType": "string", "enum": [m.value for m in ContactMethod]},
        "source": {"bsonType": "object"},
        "retrievedAt": {"bsonType": "date"},
        "status": {"bsonType": "string", "enum": [s.value for s in ContactStatus]},
        "validFrom": {"bsonType": "date"},
        "validTo": {"bsonType": ["date", "null"]},
    },
}
