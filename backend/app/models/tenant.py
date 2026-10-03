"""`tenants` collection domain model.

Fields follow the design's Data Models section / ER diagram and plan
Sec7.3: `name`, `slug` (unique index, created by the repository layer in
task 4.2), `creditPolicy` (stored per plan Sec7.3 shape but unused until a
later phase, so a loose `dict` is sufficient here), `settings`
(`publicMode`, `locale` -- the P2 Tenant_Settings surface exposed by
`GET/PATCH /tenant`), and `serpapiKeyEnc` (the Fernet-encrypted bring-
your-own SerpApi key, optional, never returned by `GET /tenant` per
Requirement 7.3 / Property 11 -- the router excludes it from the
response, it is not omitted from the model itself, since the model is
also what the P3+ SerpApi client reads the key from).
"""

from pydantic import BaseModel

from app.models.common import MongoBaseModel


class TenantSettings(BaseModel):
    """The `settings` sub-document exposed by `GET/PATCH /tenant`."""

    publicMode: bool = True
    locale: str = "en"


class Tenant(MongoBaseModel):
    """A tenant document."""

    name: str
    slug: str
    creditPolicy: dict = {}
    settings: TenantSettings = TenantSettings()
    serpapiKeyEnc: str | None = None
