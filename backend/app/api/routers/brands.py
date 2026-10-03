"""Brands router: `POST/GET /brands`, `GET/PATCH /brands/{brand_id}`.

Implements the design's `backend/app/api/routers/brands.py` component
(tasks 9.1, 9.2). Follows the existing P1 `auth.py` pattern: a module-
level `router = APIRouter(...)`, route handlers depending on
`require_role(minimum)`, pulling a `Database` from
`request.app.state.mongo_client`, constructing repositories inline per
request. Each route calls `register_route(...)` at import time so the
Permission_Matrix_Harness and Cross_Tenant_Harness (task 15) cover these
routes automatically.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from pymongo.database import Database

from app.api.route_table import RouteTableEntry, register_route
from app.auth.deps import TenantContext, require_role
from app.core.errors import AppError, ErrorCode
from app.models.audit_log_entry import AuditTarget
from app.models.brand import Alias, Brand, OfficialDomain
from app.models.role import Role
from app.repos.audit_log_repo import AuditLogRepo, hash_client_ip
from app.repos.brands_repo import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, BrandsRepo
from app.services.brand_service import validate_brand_create, validate_registrable_domain

router = APIRouter(tags=["brands"])


class AliasBody(BaseModel):
    text: str
    lang: str
    script: str
    kind: str


class OfficialDomainBody(BaseModel):
    domain: str
    verifiedBy: str
    verifiedAt: datetime


class BrandCreateRequest(BaseModel):
    slug: str
    displayName: str
    category: str
    group: str | None = None
    aliases: list[AliasBody]
    officialDomains: list[OfficialDomainBody]
    publicLookup: bool = False


class BrandUpdateRequest(BaseModel):
    slug: str | None = None
    displayName: str | None = None
    category: str | None = None
    group: str | None = None
    aliases: list[AliasBody] | None = None
    officialDomains: list[OfficialDomainBody] | None = None
    publicLookup: bool | None = None
    active: bool | None = None


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


def _brand_response(brand: Brand, official_contacts_count: int | None = None) -> dict:
    data = brand.model_dump(mode="json")
    if official_contacts_count is not None:
        data["officialContacts"] = official_contacts_count
    return data


@router.post("/brands", status_code=201)
def create_brand(
    body: BrandCreateRequest,
    request: Request,
    context: TenantContext = Depends(require_role(Role.ADMIN)),
) -> dict:
    """Create a Brand, per Requirement 2. Writes one audit_log entry."""
    db = _get_db(request)
    brands_repo = BrandsRepo(db)

    brand = Brand(
        tenantId=context.tenant_id,
        slug=body.slug,
        displayName=body.displayName,
        category=body.category,
        group=body.group,
        aliases=[Alias(**a.model_dump()) for a in body.aliases],
        officialDomains=[OfficialDomain(**d.model_dump()) for d in body.officialDomains],
        publicLookup=body.publicLookup,
    )

    validate_brand_create(context.tenant_id, brand, brands_repo)
    created = brands_repo.create(brand)

    _write_audit_log(
        db,
        context,
        "brand_created",
        AuditTarget(type="brand", id=str(created.id)),
        _hash_client_ip(request),
    )

    return {"data": _brand_response(created, official_contacts_count=0), "meta": {}}


@router.get("/brands")
def list_brands(
    request: Request,
    cursor: str | None = None,
    limit: int = DEFAULT_PAGE_SIZE,
    context: TenantContext = Depends(require_role(Role.VIEWER)),
) -> dict:
    """List every Brand scoped to the requester's tenant, cursor-paginated."""
    db = _get_db(request)
    brands_repo = BrandsRepo(db)

    effective_limit = min(limit, MAX_PAGE_SIZE)
    brands = brands_repo.list_by_tenant(context.tenant_id, cursor=cursor, limit=effective_limit)

    return {
        "data": [_brand_response(brand) for brand in brands],
        "meta": {"limit": effective_limit},
    }


@router.get("/brands/{brand_id}")
def get_brand(
    brand_id: str,
    request: Request,
    context: TenantContext = Depends(require_role(Role.VIEWER)),
) -> dict:
    """Return a Brand's full detail, including its officialContacts count."""
    db = _get_db(request)
    brands_repo = BrandsRepo(db)

    brand = brands_repo.find_by_id(context.tenant_id, brand_id)
    if brand is None:
        raise AppError(ErrorCode.NOT_FOUND, "No brand found with this id.")

    count = brands_repo.count_official_contacts(context.tenant_id, brand.id)
    return {"data": _brand_response(brand, official_contacts_count=count), "meta": {}}


@router.patch("/brands/{brand_id}")
def update_brand(
    brand_id: str,
    body: BrandUpdateRequest,
    request: Request,
    context: TenantContext = Depends(require_role(Role.ADMIN)),
) -> dict:
    """Update a Brand, re-validating changed slug/aliases/officialDomains.

    Increments `version` by 1 on acceptance (via `BrandsRepo.update`).
    Writes one audit_log entry.
    """
    db = _get_db(request)
    brands_repo = BrandsRepo(db)

    existing = brands_repo.find_by_id(context.tenant_id, brand_id)
    if existing is None:
        raise AppError(ErrorCode.NOT_FOUND, "No brand found with this id.")

    changes = body.model_dump(exclude_unset=True)

    if "slug" in changes and changes["slug"] != existing.slug:
        from app.services.brand_service import validate_slug

        validate_slug(changes["slug"])
        if brands_repo.find_by_slug(context.tenant_id, changes["slug"]) is not None:
            raise AppError(
                ErrorCode.CONFLICT,
                f"A brand with slug {changes['slug']!r} already exists for this tenant.",
            )

    if "aliases" in changes and len(changes["aliases"]) == 0:
        raise AppError(ErrorCode.VALIDATION_ERROR, "aliases must contain at least one entry.")

    if "officialDomains" in changes:
        if len(changes["officialDomains"]) == 0:
            raise AppError(
                ErrorCode.VALIDATION_ERROR, "officialDomains must contain at least one entry."
            )
        for domain_entry in changes["officialDomains"]:
            validate_registrable_domain(domain_entry["domain"])

    updated = brands_repo.update(context.tenant_id, brand_id, changes)

    _write_audit_log(
        db,
        context,
        "brand_updated",
        AuditTarget(type="brand", id=str(updated.id)),
        _hash_client_ip(request),
    )

    count = brands_repo.count_official_contacts(context.tenant_id, updated.id)
    return {"data": _brand_response(updated, official_contacts_count=count), "meta": {}}


def _create_brand_sample_request(ctx):
    """sample_request factory for POST /brands: a minimally valid body."""
    return {}, {
        "slug": ctx["unique_slug"](),
        "displayName": "Sample Brand",
        "category": "ecommerce",
        "aliases": [{"text": "Sample", "lang": "en", "script": "latin", "kind": "legal"}],
        "officialDomains": [
            {
                "domain": "sample-brand.test",
                "verifiedBy": "tester",
                "verifiedAt": "2024-01-01T00:00:00Z",
            }
        ],
    }


def _list_brands_sample_request(_ctx):
    return {}, None


def _get_brand_sample_request(ctx):
    return {"brand_id": ctx["brand_id"]}, None


def _update_brand_sample_request(ctx):
    return {"brand_id": ctx["brand_id"]}, {"displayName": "Updated Name"}


register_route(
    RouteTableEntry("POST", "/brands", Role.ADMIN, None, None, _create_brand_sample_request)
)
register_route(
    RouteTableEntry("GET", "/brands", Role.VIEWER, None, None, _list_brands_sample_request)
)
register_route(
    RouteTableEntry(
        "GET", "/brands/{brand_id}", Role.VIEWER, "brand", "brand_id", _get_brand_sample_request
    )
)
register_route(
    RouteTableEntry(
        "PATCH",
        "/brands/{brand_id}",
        Role.ADMIN,
        "brand",
        "brand_id",
        _update_brand_sample_request,
    )
)
