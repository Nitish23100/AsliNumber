"""`memberships` collection domain model.

Fields follow the design's Data Models section: `userId`, `tenantId`, and
`role` (one of `owner | admin | analyst | viewer`, see `app.models.role`).
A unique index on `(userId, tenantId)` is created by the repository layer
in task 4.2.
"""

from app.models.common import MongoBaseModel, PyObjectId
from app.models.role import Role


class Membership(MongoBaseModel):
    """A membership document linking one user to one tenant with a role."""

    userId: PyObjectId
    tenantId: PyObjectId
    role: Role
