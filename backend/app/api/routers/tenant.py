"""Tenant router: tenant settings and member management.

Implements the design's `backend/app/api/routers/tenant.py` component
(tasks 11.1, 11.4): `GET/PATCH /tenant`,
`GET/POST /tenant/members`, `PATCH/DELETE /tenant/members/{membership_id}`.

Requirement-10 note on `GET /tenant/members`'s minimum role: Requirement
10.1 lists `GET /tenant/members` at `viewer` alongside the other GET
routes; Requirement 10.2 separately lists it at `admin` alongside the
mutating member-management routes. These two acceptance criteria
conflict for this one route. This implementation resolves the conflict
in favor of Requirement 10.1 (`viewer`), consistent with every other GET
route in this phase being readable by any tenant member and only
mutations requiring `admin` -- a tenant member viewing their own team
roster is normal, read-only information, not a privileged action.
"""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from pymongo.database import Database

from app.api.route_table import RouteTableEntry, register_route
from app.auth.deps import TenantContext, require_role
from app.auth.passwords import hash_password
from app.core.errors import AppError, ErrorCode
from app.models.audit_log_entry import AuditTarget
from app.models.membership import Membership
from app.models.role import Role
from app.models.tenant import Tenant, TenantSettings
from app.models.user import User
from app.repos.audit_log_repo import AuditLogRepo, hash_client_ip
from app.repos.memberships_repo import MembershipsRepo
from app.repos.tenants_repo import TenantsRepo
from app.repos.users_repo import UsersRepo
from app.services.tenant_service import assert_can_modify_membership, assert_retains_an_owner

router = APIRouter(tags=["tenant"])


class TenantSettingsBody(BaseModel):
    publicMode: bool | None = None
    locale: str | None = None


class TenantUpdateRequest(BaseModel):
    name: str | None = None
    settings: TenantSettingsBody | None = None


class MemberCreateRequest(BaseModel):
    email: str
    name: str | None = None
    role: Role


class MemberUpdateRequest(BaseModel):
    role: Role


def _get_db(request: Request) -> Database:
    return request.app.state.mongo_client.get_default_database()


def _hash_client_ip(request: Request) -> str:
    settings = request.app.state.settings
    client_ip = request.client.host if request.client else "unknown"
    salt = settings.JWT_SECRET or "no-secret-configured"
    return hash_client_ip(salt, client_ip)


def _write_audit_log(
    db: Database, context: TenantContext, action: str, target: AuditTarget, ip_hash: str
) -> None:
    AuditLogRepo(db).write_entry(context.tenant_id, context.user_id, action, target, ip_hash)


def _tenant_response(tenant: Tenant) -> dict:
    """Serialize a Tenant for `GET`/`PATCH /tenant`, excluding `serpapiKeyEnc`.

    Per Requirement 7.3 / Property 11: `serpapiKeyEnc` is never present in
    the returned body, regardless of whether it is populated or absent on
    the stored document.
    """
    data = tenant.model_dump(mode="json", exclude={"serpapiKeyEnc"})
    return data


def _membership_response(membership: Membership, user: User | None) -> dict:
    return {
        "id": str(membership.id),
        "userId": str(membership.userId),
        "tenantId": str(membership.tenantId),
        "role": membership.role.value,
        "email": user.email if user else None,
        "name": user.name if user else None,
    }


@router.get("/tenant")
def get_tenant(
    request: Request,
    context: TenantContext = Depends(require_role(Role.VIEWER)),
) -> dict:
    """Return the requester's Tenant_Settings, excluding `serpapiKeyEnc`."""
    db = _get_db(request)
    tenants_repo = TenantsRepo(db)

    tenant = tenants_repo.find_by_id(context.tenant_id)
    if tenant is None:
        raise AppError(ErrorCode.NOT_FOUND, "No tenant found with this id.")

    return {"data": _tenant_response(tenant), "meta": {}}


@router.patch("/tenant")
def update_tenant(
    body: TenantUpdateRequest,
    request: Request,
    context: TenantContext = Depends(require_role(Role.OWNER)),
) -> dict:
    """Update the tenant's `name` and/or `settings`. Writes one audit_log entry."""
    db = _get_db(request)
    tenants_repo = TenantsRepo(db)

    tenant = tenants_repo.find_by_id(context.tenant_id)
    if tenant is None:
        raise AppError(ErrorCode.NOT_FOUND, "No tenant found with this id.")

    changes = body.model_dump(exclude_unset=True)
    update_doc: dict = {}
    if "name" in changes:
        update_doc["name"] = changes["name"]
    if "settings" in changes:
        merged_settings = tenant.settings.model_dump()
        merged_settings.update(changes["settings"])
        update_doc["settings"] = TenantSettings(**merged_settings).model_dump()

    db["tenants"].update_one({"_id": tenant.id}, {"$set": update_doc})
    updated = tenants_repo.find_by_id(context.tenant_id)

    _write_audit_log(
        db,
        context,
        "tenant_updated",
        AuditTarget(type="tenant", id=str(updated.id)),
        _hash_client_ip(request),
    )

    return {"data": _tenant_response(updated), "meta": {}}


@router.get("/tenant/members")
def list_members(
    request: Request,
    context: TenantContext = Depends(require_role(Role.VIEWER)),
) -> dict:
    """List every Membership in the tenant, with each member's email/name."""
    db = _get_db(request)
    memberships_repo = MembershipsRepo(db)
    users_repo = UsersRepo(db)

    memberships = memberships_repo.list_by_tenant(context.tenant_id)
    data = []
    for membership in memberships:
        user = users_repo.find_by_id(membership.userId)
        data.append(_membership_response(membership, user))

    return {"data": data, "meta": {}}


@router.post("/tenant/members", status_code=201)
def create_member(
    body: MemberCreateRequest,
    request: Request,
    context: TenantContext = Depends(require_role(Role.ADMIN)),
) -> dict:
    """Create a Membership for an existing or newly-invited user.

    If `body.email` matches an existing user, only a new Membership is
    created for that user; otherwise a new User is created (with a
    random, unusable-until-reset password hash -- actual invite/password-
    set flows are out of scope for this phase) plus the Membership.
    """
    db = _get_db(request)
    users_repo = UsersRepo(db)
    memberships_repo = MembershipsRepo(db)

    user = users_repo.find_by_email(body.email)
    if user is None:
        import secrets

        user = users_repo.create(
            User(
                email=body.email,
                passwordHash=hash_password(secrets.token_urlsafe(32)),
                name=body.name or body.email,
                status="active",
            )
        )

    membership = memberships_repo.create(
        Membership(userId=user.id, tenantId=context.tenant_id, role=body.role)
    )

    _write_audit_log(
        db,
        context,
        "member_added",
        AuditTarget(type="membership", id=str(membership.id)),
        _hash_client_ip(request),
    )

    return {"data": _membership_response(membership, user), "meta": {}}


@router.patch("/tenant/members/{membership_id}")
def update_member(
    membership_id: str,
    body: MemberUpdateRequest,
    request: Request,
    context: TenantContext = Depends(require_role(Role.ADMIN)),
) -> dict:
    """Change a Membership's role, enforcing the owner-protection and last-owner rules."""
    db = _get_db(request)
    memberships_repo = MembershipsRepo(db)
    users_repo = UsersRepo(db)

    target = memberships_repo.find_by_id(context.tenant_id, membership_id)
    if target is None:
        raise AppError(ErrorCode.NOT_FOUND, "No membership found with this id.")

    assert_can_modify_membership(context.role, target)
    assert_retains_an_owner(memberships_repo, context.tenant_id, membership_id, body.role)

    updated = memberships_repo.update_role(context.tenant_id, membership_id, body.role)

    _write_audit_log(
        db,
        context,
        "member_role_changed",
        AuditTarget(type="membership", id=str(updated.id)),
        _hash_client_ip(request),
    )

    user = users_repo.find_by_id(updated.userId)
    return {"data": _membership_response(updated, user), "meta": {}}


@router.delete("/tenant/members/{membership_id}", status_code=204)
def delete_member(
    membership_id: str,
    request: Request,
    context: TenantContext = Depends(require_role(Role.ADMIN)),
) -> None:
    """Remove a Membership, enforcing the owner-protection and last-owner rules."""
    db = _get_db(request)
    memberships_repo = MembershipsRepo(db)

    target = memberships_repo.find_by_id(context.tenant_id, membership_id)
    if target is None:
        raise AppError(ErrorCode.NOT_FOUND, "No membership found with this id.")

    assert_can_modify_membership(context.role, target)
    assert_retains_an_owner(memberships_repo, context.tenant_id, membership_id, None)

    memberships_repo.delete(context.tenant_id, membership_id)

    _write_audit_log(
        db,
        context,
        "member_removed",
        AuditTarget(type="membership", id=membership_id),
        _hash_client_ip(request),
    )


def _get_tenant_sample_request(_ctx):
    return {}, None


def _update_tenant_sample_request(_ctx):
    return {}, {"name": "Updated Tenant Name"}


def _list_members_sample_request(_ctx):
    return {}, None


def _create_member_sample_request(ctx):
    return {}, {"email": ctx["unique_email"](), "name": "Sample Member", "role": "viewer"}


def _update_member_sample_request(ctx):
    return {"membership_id": ctx["non_owner_membership_id"]}, {"role": "analyst"}


def _delete_member_sample_request(ctx):
    return {"membership_id": ctx["non_owner_membership_id"]}, None


register_route(
    RouteTableEntry("GET", "/tenant", Role.VIEWER, None, None, _get_tenant_sample_request)
)
register_route(
    RouteTableEntry("PATCH", "/tenant", Role.OWNER, None, None, _update_tenant_sample_request)
)
register_route(
    RouteTableEntry("GET", "/tenant/members", Role.VIEWER, None, None, _list_members_sample_request)
)
register_route(
    RouteTableEntry(
        "POST", "/tenant/members", Role.ADMIN, None, None, _create_member_sample_request
    )
)
register_route(
    RouteTableEntry(
        "PATCH",
        "/tenant/members/{membership_id}",
        Role.ADMIN,
        "membership",
        "membership_id",
        _update_member_sample_request,
    )
)
register_route(
    RouteTableEntry(
        "DELETE",
        "/tenant/members/{membership_id}",
        Role.ADMIN,
        "membership",
        "membership_id",
        _delete_member_sample_request,
    )
)
