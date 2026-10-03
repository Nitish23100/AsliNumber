"""Route_Table registry: driven by the Permission_Matrix_Harness and Cross_Tenant_Harness.

Implements the design's `backend/app/api/route_table.py` component
(task 8.1): `RouteTableEntry`, the module-level `ROUTE_TABLE` list, and
`register_route`.

Every router module added in this phase (and, by established convention,
every router module added in later phases) calls `register_route(...)`
once per route at import time -- right after `router = APIRouter(...)`,
mirroring the P1 `auth.py` layout -- so `ROUTE_TABLE` is always in sync
with the actual routes and there is no second, hand-maintained list that
can drift from the real router code.

`Permission_Matrix_Harness` (task 15.1) parametrizes over `ROUTE_TABLE`
crossed with every `Role`, asserting a route accepts a request if and
only if the requester's role rank is at or above `minimum_role`'s rank.
`Cross_Tenant_Harness` (task 15.2) parametrizes over every entry that
carries a `resource_kind`, asserting a resource created in one tenant is
unreachable (HTTP 404) from a different tenant's authenticated request.

Both harnesses need a request body and path parameters that pass
validation for every route they call, independent of role or tenant --
otherwise a 422 from a missing body field would be indistinguishable from
a 403/404 the harness is actually testing. Each entry's `sample_request`
factory exists to isolate the one axis each harness is testing from every
other validation axis.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.models.role import Role


@dataclass(frozen=True)
class RouteTableEntry:
    """One route this phase (or a later one, by convention) registers.

    Attributes:
        method: HTTP method, e.g. "GET", "POST", "PATCH", "DELETE".
        path_template: The route's path, with `{param}`-style placeholders
            exactly as FastAPI declares them, e.g. "/brands/{brand_id}".
        minimum_role: The minimum `Role` rank required to access this
            route, per Requirement 10. `None` for a public/unauthenticated
            route (none exist in this phase).
        resource_kind: A short label identifying what kind of tenant-
            scoped resource this route addresses (e.g. "brand",
            "official_contact", "membership"), or `None` if the route
            does not address a single existing resource (e.g. a list or
            create route). Used by `Cross_Tenant_Harness` to know which
            routes it applies to.
        resource_param: The name of the path placeholder that carries the
            resource's id, or `None` if `resource_kind` is `None`.
        sample_request: A callable `(context) -> (path_params, json_body)`
            producing a request that passes every validation rule except
            the one axis (role, or tenant) the calling harness is
            exercising. `context` is supplied by the test's own fixtures
            (e.g. an already-created brand id to substitute into
            `path_params`).
    """

    method: str
    path_template: str
    minimum_role: Role | None
    resource_kind: str | None
    resource_param: str | None
    sample_request: Callable[[Any], tuple[dict, dict | None]]


ROUTE_TABLE: list[RouteTableEntry] = []


def register_route(entry: RouteTableEntry) -> None:
    """Append `entry` to `ROUTE_TABLE`, guarding against duplicate registration.

    A duplicate `(method, path_template)` pair would silently double-
    count a route in both harnesses (e.g. running it twice per role in
    the Permission_Matrix_Harness), so this raises `AssertionError`
    immediately at import time rather than letting it pass unnoticed.
    """
    for existing in ROUTE_TABLE:
        assert not (
            existing.method == entry.method and existing.path_template == entry.path_template
        ), (
            f"Duplicate route registration: {entry.method} {entry.path_template} is already "
            "in ROUTE_TABLE."
        )
    ROUTE_TABLE.append(entry)
