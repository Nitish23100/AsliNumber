"""Integration tests for `app.repos.tenants_repo`.

Covers the create+find round trip and the unique index on `slug`, per
task 4.2's testing checklist. Runs against the in-memory `mongomock`
database fixture (see `conftest.py` for why).
"""

import pytest
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from app.models.tenant import Tenant
from app.repos.tenants_repo import TenantsRepo


def test_create_and_find_by_slug_round_trip(db: Database) -> None:
    repo = TenantsRepo(db)
    tenant = Tenant(name="Demo Brand Protection", slug="demo-brand-protection")

    created = repo.create(tenant)
    found = repo.find_by_slug("demo-brand-protection")

    assert found is not None
    assert found.id == created.id
    assert found.name == "Demo Brand Protection"
    assert found.slug == "demo-brand-protection"


def test_create_and_find_by_id_round_trip(db: Database) -> None:
    repo = TenantsRepo(db)
    tenant = Tenant(name="Demo Agency", slug="demo-agency")

    created = repo.create(tenant)
    found = repo.find_by_id(created.id)

    assert found is not None
    assert found.id == created.id
    assert found.name == "Demo Agency"


def test_find_by_slug_returns_none_when_absent(db: Database) -> None:
    repo = TenantsRepo(db)

    assert repo.find_by_slug("does-not-exist") is None


def test_find_by_id_returns_none_when_absent(db: Database) -> None:
    from bson import ObjectId

    repo = TenantsRepo(db)

    assert repo.find_by_id(ObjectId()) is None


def test_duplicate_slug_raises_duplicate_key_error(db: Database) -> None:
    repo = TenantsRepo(db)
    repo.create(Tenant(name="Demo Brand Protection", slug="demo-brand-protection"))

    with pytest.raises(DuplicateKeyError):
        repo.create(Tenant(name="A Different Name", slug="demo-brand-protection"))
