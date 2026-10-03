"""Integration test for backend.app.cli's demo seeder idempotency.

Per Requirement 4.4: running `seed_demo` twice against the same database
must not create duplicates or raise -- exactly 2 tenants, 4 users, and 4
memberships exist afterward, whether seeded once or twice.

P2 (tasks 16.2, 16.3, 16.4) extends this file with the Demo_Brand_
Catalog's own idempotency, fictional-content, and zero-official-contacts
checks (Requirement 12).
"""

from app.cli import _DEMO_BRANDS, seed_demo
from app.repos.brands_repo import BrandsRepo
from app.repos.memberships_repo import MembershipsRepo
from app.repos.tenants_repo import TenantsRepo
from app.repos.users_repo import UsersRepo

# A short denylist of well-known real companies/domains the Demo_Brand_
# Catalog's fictional names/domains must never match, per Requirement
# 12.2 and docs/design.md Sec13.
_REAL_COMPANY_DENYLIST = {
    "amazon",
    "flipkart",
    "paytm",
    "airtel",
    "jio",
    "reliance",
    "google",
    "apple",
    "microsoft",
    "swiggy",
    "zomato",
    "myntra",
    "bigbasket",
    "ola",
    "uber",
}


def test_seed_demo_run_twice_creates_no_duplicates(db) -> None:
    tenants_repo = TenantsRepo(db)
    users_repo = UsersRepo(db)
    memberships_repo = MembershipsRepo(db)

    seed_demo(tenants_repo, users_repo, memberships_repo)
    seed_demo(tenants_repo, users_repo, memberships_repo)

    assert db["tenants"].count_documents({}) == 2
    assert db["users"].count_documents({}) == 4
    assert db["memberships"].count_documents({}) == 4


def test_seed_demo_creates_one_membership_per_user_in_the_primary_tenant(db) -> None:
    tenants_repo = TenantsRepo(db)
    users_repo = UsersRepo(db)
    memberships_repo = MembershipsRepo(db)

    seed_demo(tenants_repo, users_repo, memberships_repo)

    primary_tenant = tenants_repo.find_by_slug("demo-brand-protection")
    assert primary_tenant is not None
    memberships = memberships_repo.find_all_by_user(
        users_repo.find_by_email("owner@demo.aslinumber.test").id
    )
    assert len(memberships) == 1
    assert memberships[0].tenantId == primary_tenant.id
    assert memberships[0].role.value == "owner"


def test_seed_demo_brand_catalog_idempotent_across_two_runs(db) -> None:
    """Running `cli seed --demo` twice leaves exactly 6 brands, with the

    same `_id` set after the second run as after the first (task 16.2).
    """
    tenants_repo = TenantsRepo(db)
    users_repo = UsersRepo(db)
    memberships_repo = MembershipsRepo(db)
    brands_repo = BrandsRepo(db)

    seed_demo(tenants_repo, users_repo, memberships_repo, brands_repo=brands_repo)
    primary_tenant = tenants_repo.find_by_slug("demo-brand-protection")
    first_run_ids = {doc["_id"] for doc in db["brands"].find({"tenantId": primary_tenant.id})}

    seed_demo(tenants_repo, users_repo, memberships_repo, brands_repo=brands_repo)
    second_run_ids = {doc["_id"] for doc in db["brands"].find({"tenantId": primary_tenant.id})}

    assert len(first_run_ids) == 6
    assert first_run_ids == second_run_ids


def test_demo_brand_catalog_uses_only_fictional_names_and_test_tld_domains() -> None:
    """None of the 6 hardcoded brand names or domains match a denylist of

    well-known real companies/domains, and every domain uses the `.test`
    reserved TLD (task 16.3).
    """
    assert len(_DEMO_BRANDS) == 6
    for brand_spec in _DEMO_BRANDS:
        name_lower = brand_spec["displayName"].lower()
        domain_lower = brand_spec["domain"].lower()
        for real_name in _REAL_COMPANY_DENYLIST:
            assert real_name not in name_lower
            assert real_name not in domain_lower
        assert domain_lower.endswith(".test")


def test_seeded_demo_brands_have_zero_official_contacts(db) -> None:
    """After `cli seed --demo`, `count_official_contacts` is 0 for each of

    the 6 seeded demo brands (task 16.4).
    """
    tenants_repo = TenantsRepo(db)
    users_repo = UsersRepo(db)
    memberships_repo = MembershipsRepo(db)
    brands_repo = BrandsRepo(db)

    seed_demo(tenants_repo, users_repo, memberships_repo, brands_repo=brands_repo)

    primary_tenant = tenants_repo.find_by_slug("demo-brand-protection")
    seeded_brands = brands_repo.list_by_tenant(primary_tenant.id, limit=10)

    assert len(seeded_brands) == 6
    for brand in seeded_brands:
        assert brands_repo.count_official_contacts(primary_tenant.id, brand.id) == 0
