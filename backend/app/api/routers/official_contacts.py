"""Official-contacts router: registry entry create/list/patch, no delete.

Implements the design's `backend/app/api/routers/official_contacts.py`
component (tasks 10.1, 10.2):
`POST/GET /brands/{brand_id}/official-contacts`,
`PATCH /official-contacts/{contact_id}`. Deliberately has no `DELETE`
route, per Requirement 6.4 -- entries are deprecated, never deleted
(`OfficialContactsRepo` itself has no `delete` method either, so a hard
delete is structurally unreachable, not merely unrouted here).
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from pymongo.database import Database

from app.api.route_table import RouteTableEntry, register_route
from app.auth.deps import TenantContext, require_role
from app.core.errors import AppError, ErrorCode
from app.models.audit_log_entry import AuditTarget
from app.models.brand import Authority
from app.models.official_contact import OfficialContact
from app.models.role import Role
from app.repos.audit_log_repo import AuditLogRepo, hash_client_ip
from app.repos.brands_repo import BrandsRepo
from app.repos.official_contacts_repo import OfficialContactsRepo
from app.services.brand_service import prepare_official_contact_create

router = APIRouter(tags=["official-contacts"])


class ContactSourceBody(BaseModel):
    url: str
    registeredDomain: str
    evidenceId: str | None = None
    observedText: str | None = None


class ContactScopeBody(BaseModel):
    cities: list[str] = []
    languages: list[str] = []


class OfficialContactCreateRequest(BaseModel):
    e164: str
    display: str
    contactTypes: list[str]
    scope: ContactScopeBody | None = None
    source: ContactSourceBody
    authority: Authority | None = None


class OfficialContactUpdateRequest(BaseModel):
    display: str | None = None
    contactTypes: list[str] | None = None
    scope: ContactScopeBody | None = None
    status: str | None = None
    validTo: datetime | None = None


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


def _contact_response(contact: OfficialContact) -> dict:
    return contact.model_dump(mode="json")


@router.post("/brands/{brand_id}/official-contacts", status_code=201)
def create_official_contact(
    brand_id: str,
    body: OfficialContactCreateRequest,
    request: Request,
    context: TenantContext = Depends(require_role(Role.ADMIN)),
) -> dict:
    """Create an Official_Contact for a brand's registry, per Requirement 4."""
    db = _get_db(request)
    brands_repo = BrandsRepo(db)
    contacts_repo = OfficialContactsRepo(db)

    brand = brands_repo.find_by_id(context.tenant_id, brand_id)
    if brand is None:
        raise AppError(ErrorCode.NOT_FOUND, "No brand found with this id.")

    contact = prepare_official_contact_create(context.tenant_id, brand, body)
    created = contacts_repo.create(contact)

    _write_audit_log(
        db,
        context,
        "official_contact_created",
        AuditTarget(type="official_contact", id=str(created.id)),
        _hash_client_ip(request),
    )

    return {"data": _contact_response(created), "meta": {}}


@router.get("/brands/{brand_id}/official-contacts")
def list_official_contacts(
    brand_id: str,
    request: Request,
    context: TenantContext = Depends(require_role(Role.VIEWER)),
) -> dict:
    """List every Official_Contact for a brand, including deprecated entries."""
    db = _get_db(request)
    brands_repo = BrandsRepo(db)
    contacts_repo = OfficialContactsRepo(db)

    brand = brands_repo.find_by_id(context.tenant_id, brand_id)
    if brand is None:
        raise AppError(ErrorCode.NOT_FOUND, "No brand found with this id.")

    contacts = contacts_repo.list_by_brand(context.tenant_id, brand.id)
    return {"data": [_contact_response(c) for c in contacts], "meta": {}}


@router.patch("/official-contacts/{contact_id}")
def update_official_contact(
    contact_id: str,
    body: OfficialContactUpdateRequest,
    request: Request,
    context: TenantContext = Depends(require_role(Role.ADMIN)),
) -> dict:
    """Update an Official_Contact's display/contactTypes/scope/status/validTo.

    Per Requirement 6.5: defaults `validTo` to now when `status` is set
    to `deprecated` and `validTo` is omitted. Writes one audit_log entry.
    """
    db = _get_db(request)
    contacts_repo = OfficialContactsRepo(db)

    existing = contacts_repo.find_by_id(context.tenant_id, contact_id)
    if existing is None:
        raise AppError(ErrorCode.NOT_FOUND, "No official contact found with this id.")

    changes = body.model_dump(exclude_unset=True)
    if changes.get("status") == "deprecated" and "validTo" not in changes:
        changes["validTo"] = datetime.now(UTC)

    updated = contacts_repo.update(context.tenant_id, contact_id, changes)

    _write_audit_log(
        db,
        context,
        "official_contact_updated",
        AuditTarget(type="official_contact", id=str(updated.id)),
        _hash_client_ip(request),
    )

    return {"data": _contact_response(updated), "meta": {}}


def _create_contact_sample_request(ctx):
    return {"brand_id": ctx["brand_id"]}, {
        "e164": ctx["unique_e164"](),
        "display": "Support",
        "contactTypes": ["support"],
        "source": {
            "url": "https://sample-brand.test/contact",
            "registeredDomain": "sample-brand.test",
        },
    }


def _list_contacts_sample_request(ctx):
    return {"brand_id": ctx["brand_id"]}, None


def _update_contact_sample_request(ctx):
    return {"contact_id": ctx["contact_id"]}, {"display": "Updated Support"}


register_route(
    RouteTableEntry(
        "POST",
        "/brands/{brand_id}/official-contacts",
        Role.ADMIN,
        "brand",
        "brand_id",
        _create_contact_sample_request,
    )
)
register_route(
    RouteTableEntry(
        "GET",
        "/brands/{brand_id}/official-contacts",
        Role.VIEWER,
        "brand",
        "brand_id",
        _list_contacts_sample_request,
    )
)
register_route(
    RouteTableEntry(
        "PATCH",
        "/official-contacts/{contact_id}",
        Role.ADMIN,
        "official_contact",
        "contact_id",
        _update_contact_sample_request,
    )
)
