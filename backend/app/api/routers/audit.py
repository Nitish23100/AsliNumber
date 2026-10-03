"""Audit router: `GET /audit-log`.

Implements the design's `backend/app/api/routers/audit.py` component
(task 12.1): a listing route filterable by `action`, `userId`, and
`target.id`, scoped to the requester's TenantContext.
"""

from fastapi import APIRouter, Depends, Request
from pymongo.database import Database

from app.api.route_table import RouteTableEntry, register_route
from app.auth.deps import TenantContext, require_role
from app.models.audit_log_entry import AuditLogEntry
from app.models.role import Role
from app.repos.audit_log_repo import AuditLogRepo

router = APIRouter(tags=["audit"])


def _get_db(request: Request) -> Database:
    return request.app.state.mongo_client.get_default_database()


def _entry_response(entry: AuditLogEntry) -> dict:
    return entry.model_dump(mode="json")


@router.get("/audit-log")
def list_audit_log(
    request: Request,
    action: str | None = None,
    userId: str | None = None,  # noqa: N803 -- matches the query-param name per Requirement 9.2
    targetId: str | None = None,  # noqa: N803 -- matches the query-param name per Requirement 9.2
    context: TenantContext = Depends(require_role(Role.ADMIN)),
) -> dict:
    """List Audit_Log_Entry records for this tenant, filterable by action/userId/target.id."""
    db = _get_db(request)
    repo = AuditLogRepo(db)

    entries = repo.list_by_tenant(
        context.tenant_id, action=action, user_id=userId, target_id=targetId
    )
    return {"data": [_entry_response(entry) for entry in entries], "meta": {}}


def _list_audit_log_sample_request(_ctx):
    return {}, None


register_route(
    RouteTableEntry("GET", "/audit-log", Role.ADMIN, None, None, _list_audit_log_sample_request)
)
