"""Tenant-scoped MongoDB repositories for users, tenants, memberships, and sessions.

Each submodule (`tenants_repo`, `users_repo`, `memberships_repo`,
`sessions_repo`) owns its own `create_indexes(db)` function next to the
repository class it belongs to, so the index spec lives beside the model
it indexes. `create_indexes` here is the single consolidated entry point
that calls all four -- the app factory (task 2.6) or any startup/seed path
calls this one function rather than importing every submodule itself.

`create_index` is idempotent for an identical spec (MongoDB only creates
the index once; repeat calls are no-ops), so calling this on every app
startup is safe and never raises or duplicates an index.
"""

from pymongo.database import Database

from app.repos import memberships_repo, sessions_repo, tenants_repo, users_repo


def create_indexes(db: Database) -> None:
    """Create every index listed in the design's Data Models section.

    Covers: unique `tenants.slug`, unique `users.email`, unique compound
    `memberships.(userId, tenantId)`, unique `sessions.refreshTokenHash`,
    and the TTL index on `sessions.expiresAt`.
    """
    tenants_repo.create_indexes(db)
    users_repo.create_indexes(db)
    memberships_repo.create_indexes(db)
    sessions_repo.create_indexes(db)
