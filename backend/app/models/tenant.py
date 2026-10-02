"""`tenants` collection domain model.

Fields follow the design's Data Models section / ER diagram: `name`, `slug`
(unique index, created by the repository layer in task 4.2), and
`creditPolicy` (stored per plan §7.3 shape but unused until a later phase,
so a loose `dict` is sufficient here).
"""

from app.models.common import MongoBaseModel


class Tenant(MongoBaseModel):
    """A tenant document."""

    name: str
    slug: str
    creditPolicy: dict = {}
