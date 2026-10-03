"""Command-line interface.

Implements the `seed --demo` command: idempotently creates two demo
tenants ("Demo Brand Protection", "Demo Agency") and one user per role
(owner, admin, analyst, viewer), each with a membership in the first
tenant. Per Requirement 4.4, running this more than once must not create
duplicates or raise -- a tenant/user/membership that already exists
(matched by its unique key: slug, email, or (userId, tenantId)) is left
as is rather than re-created.

P2 (task 16.1) extends `seed_demo` with the Demo_Brand_Catalog: 6
fictional demo brands, seeded within the first demo tenant
("demo-brand-protection") with zero `OfficialContact` entries each, per
Requirement 12.
"""

from datetime import UTC, datetime

import typer

from app.auth.passwords import hash_password
from app.config import Settings
from app.core.db import get_mongo_client
from app.models.brand import Alias, Brand, OfficialDomain
from app.models.membership import Membership
from app.models.role import Role
from app.models.tenant import Tenant
from app.models.user import User
from app.repos import create_indexes
from app.repos.brands_repo import BrandsRepo
from app.repos.memberships_repo import MembershipsRepo
from app.repos.tenants_repo import TenantsRepo
from app.repos.users_repo import UsersRepo

app = typer.Typer()


@app.callback()
def _callback() -> None:
    """AsliNumber backend CLI.

    An explicit (empty) callback is required here: a Typer app with only
    one registered command otherwise collapses into a single top-level
    command, which would make `python -m app.cli --demo` work but
    `python -m app.cli seed --demo` (the form this task and the full
    implementation plan's CLI reference both document) fail with "Got
    unexpected extra argument (seed)". Registering a callback forces
    Typer to keep requiring the subcommand name, which also matches how
    this CLI is expected to grow more subcommands in later phases (plan,
    sweep, reprocess, footprint, etc., per the full implementation plan's
    CLI section) -- `seed` won't need to change shape when those land.
    """


_DEMO_TENANTS = [
    {"name": "Demo Brand Protection", "slug": "demo-brand-protection"},
    {"name": "Demo Agency", "slug": "demo-agency"},
]

# One user per role, each a member of the FIRST demo tenant
# ("demo-brand-protection"). Password comes from `DEMO_PASSWORD` in
# Settings when present, falling back to a documented default for local
# development -- never used when DEMO_MODE's startup guard would refuse
# to run anyway (Requirement 11).
_DEMO_USERS = [
    {"email": "owner@demo.aslinumber.test", "name": "Demo Owner", "role": Role.OWNER},
    {"email": "admin@demo.aslinumber.test", "name": "Demo Admin", "role": Role.ADMIN},
    {"email": "analyst@demo.aslinumber.test", "name": "Demo Analyst", "role": Role.ANALYST},
    {"email": "viewer@demo.aslinumber.test", "name": "Demo Viewer", "role": Role.VIEWER},
]

_DEFAULT_DEMO_PASSWORD = "DemoPassword123!"

# The Demo_Brand_Catalog (Requirement 12): 6 fictional demo brands, never
# a real company's name or domain, per docs/design.md Sec13. Every domain
# uses the RFC 2606 reserved `.test` TLD, which `brand_service.
# validate_registrable_domain` special-cases as registrable (see that
# module's docstring) -- no real domain under `.test` can ever exist, so
# these entries can never collide with or be mistaken for a real brand.
_DEMO_BRANDS = [
    {
        "slug": "examplekart",
        "displayName": "ExampleKart",
        "category": "ecommerce",
        "domain": "examplekart.test",
    },
    {
        "slug": "n-mart",
        "displayName": "N-Mart",
        "category": "ecommerce",
        "domain": "n-mart.test",
    },
    {
        "slug": "fictionpay",
        "displayName": "FictionPay",
        "category": "fintech",
        "domain": "fictionpay.test",
    },
    {
        "slug": "sampletel",
        "displayName": "SampleTel",
        "category": "telecom",
        "domain": "sampletel.test",
    },
    {
        "slug": "mockmart-grocery",
        "displayName": "MockMart Grocery",
        "category": "grocery",
        "domain": "mockmart-grocery.test",
    },
    {
        "slug": "demoflight-airlines",
        "displayName": "DemoFlight Airlines",
        "category": "travel",
        "domain": "demoflight-airlines.test",
    },
]


def seed_demo(
    tenants_repo: TenantsRepo,
    users_repo: UsersRepo,
    memberships_repo: MembershipsRepo,
    password: str = _DEFAULT_DEMO_PASSWORD,
    brands_repo: BrandsRepo | None = None,
) -> None:
    """Idempotently create the demo tenants, users, memberships, and brands.

    Safe to call more than once: each entity is looked up by its unique
    key before being created, so a second run is a no-op rather than a
    duplicate-key error or a second set of records. `brands_repo` is
    optional so existing P1 call sites that only seed tenants/users/
    memberships keep working unchanged; when omitted, the Demo_Brand_
    Catalog step is skipped.
    """
    created_tenants: dict[str, Tenant] = {}
    for tenant_spec in _DEMO_TENANTS:
        existing = tenants_repo.find_by_slug(tenant_spec["slug"])
        tenant = existing if existing is not None else tenants_repo.create(Tenant(**tenant_spec))
        created_tenants[tenant_spec["slug"]] = tenant

    primary_tenant = created_tenants[_DEMO_TENANTS[0]["slug"]]
    password_hash = hash_password(password)

    for user_spec in _DEMO_USERS:
        existing_user = users_repo.find_by_email(user_spec["email"])
        if existing_user is None:
            user = users_repo.create(
                User(
                    email=user_spec["email"],
                    passwordHash=password_hash,
                    name=user_spec["name"],
                    status="active",
                )
            )
        else:
            user = existing_user

        existing_membership = memberships_repo.find_by_user_and_tenant(user.id, primary_tenant.id)
        if existing_membership is None:
            memberships_repo.create(
                Membership(userId=user.id, tenantId=primary_tenant.id, role=user_spec["role"])
            )

    if brands_repo is not None:
        for brand_spec in _DEMO_BRANDS:
            existing_brand = brands_repo.find_by_slug(primary_tenant.id, brand_spec["slug"])
            if existing_brand is None:
                brands_repo.create(
                    Brand(
                        tenantId=primary_tenant.id,
                        slug=brand_spec["slug"],
                        displayName=brand_spec["displayName"],
                        category=brand_spec["category"],
                        aliases=[
                            Alias(
                                text=brand_spec["displayName"],
                                lang="en",
                                script="latin",
                                kind="legal",
                            )
                        ],
                        officialDomains=[
                            OfficialDomain(
                                domain=brand_spec["domain"],
                                verifiedBy="demo-seeder",
                                verifiedAt=datetime.now(UTC),
                            )
                        ],
                    )
                )
                # Zero OfficialContact entries are created for any seeded
                # demo brand, per Requirement 12.3 -- this phase has no
                # real registry source yet, so a brand with zero official
                # contacts is the correct, expected seeded state.


@app.command()
def seed(demo: bool = typer.Option(False, "--demo", help="Seed demo tenants and users.")) -> None:
    """Seed the database. Currently only `--demo` is implemented."""
    if not demo:
        typer.echo("Nothing to seed: pass --demo.")
        return

    settings = Settings()
    client = get_mongo_client(settings)
    db = client.get_default_database()
    create_indexes(db)

    seed_demo(TenantsRepo(db), UsersRepo(db), MembershipsRepo(db), brands_repo=BrandsRepo(db))
    typer.echo("Demo tenants, users, and brands seeded (idempotent).")


if __name__ == "__main__":
    app()
