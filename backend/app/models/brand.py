"""`brands` collection domain model, plus the small shared registry vocabulary.

`Authority`, `ContactMethod`, and `ContactStatus` are declared here rather
than in `official_contact.py` since all three are small, closely related
vocabulary for the registry as a whole; `official_contact.py` imports
them. `ContactMethod` includes the three phase-P7 values
(`OFFICIAL_SITE_SNIPPET`, `OFFICIAL_PAGE_FETCH`, `KNOWLEDGE_GRAPH`) for
forward schema compatibility per plan Sec7.2's full enum, even though only
`MANUAL` is reachable from any P2 endpoint -- this avoids a breaking
schema migration when P7 adds the fetcher.

Fields follow the design's Data Models section / plan Sec7.2: `tenantId`,
`slug` (unique per tenant, created by the repository layer in task 2.1),
`displayName`, `category`, `group` (optional), `aliases` (at least 1 at
creation, enforced by `app.services.brand_service`), `officialDomains`
(at least 1, each a registrable domain), `publicLookup`, `active`,
`version` (starts at 1, incremented by every accepted `PATCH`).
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel

from app.models.common import MongoBaseModel, PyObjectId


class Authority(StrEnum):
    """Whether an Official_Contact is the brand's main line or a secondary one."""

    PRIMARY = "primary"
    SUPPORTING = "supporting"


class ContactMethod(StrEnum):
    """How an Official_Contact entry was sourced.

    Only `MANUAL` is reachable from any P2 endpoint. The other three
    values are declared now for forward schema compatibility with phase
    P7's official-page fetcher and Knowledge-Graph-derived entries.
    """

    MANUAL = "manual"
    OFFICIAL_SITE_SNIPPET = "official_site_snippet"
    OFFICIAL_PAGE_FETCH = "official_page_fetch"
    KNOWLEDGE_GRAPH = "knowledge_graph"


class ContactStatus(StrEnum):
    """An Official_Contact's lifecycle state. Deprecated, never deleted."""

    ACTIVE = "active"
    DEPRECATED = "deprecated"


class Alias(BaseModel):
    """One alternate name a brand is known by (for later brand-resolution phases)."""

    text: str
    lang: str
    script: str
    kind: str


class OfficialDomain(BaseModel):
    """A registered domain a human operator has attested belongs to a brand."""

    domain: str
    verifiedBy: str
    verifiedAt: datetime


class Brand(MongoBaseModel):
    """A tenant-scoped brand configuration document."""

    tenantId: PyObjectId
    slug: str
    displayName: str
    category: str
    group: str | None = None
    aliases: list[Alias]
    officialDomains: list[OfficialDomain]
    publicLookup: bool = False
    active: bool = True
    version: int = 1


# Co-located with the model per the design's convention: the Pydantic
# model and the MongoDB $jsonSchema validator for the same collection
# live in the same file, so they are easy to keep in sync (and the
# enum-drift test in task 1.5 checks they do not silently diverge).
# validationLevel: moderate (applied in app.core.validators) means this
# validator is a second line of defense, not the sole source of truth --
# minItems on aliases/officialDomains is NOT enforced here, matching
# design.md's own note that the application layer (brand_service) owns
# the non-empty-list rule; this schema only pins down types and enums.
JSON_SCHEMA: dict = {
    "bsonType": "object",
    "required": ["tenantId", "slug", "displayName", "category", "version"],
    "properties": {
        "tenantId": {"bsonType": "objectId"},
        "slug": {"bsonType": "string"},
        "displayName": {"bsonType": "string"},
        "category": {"bsonType": "string"},
        "group": {"bsonType": ["string", "null"]},
        "aliases": {"bsonType": "array"},
        "officialDomains": {"bsonType": "array"},
        "publicLookup": {"bsonType": "bool"},
        "active": {"bsonType": "bool"},
        "version": {"bsonType": "int"},
    },
}
