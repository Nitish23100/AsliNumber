"""Shared fixtures for repository integration tests (task 4.2).

Testing-approach note: a real local MongoDB instance was not reachable in
this environment (checked with a short-timeout `ping` against
`mongodb://localhost:27017` before writing these tests), so these tests
run against `mongomock.MongoClient()`, an in-memory fake that implements
enough of PyMongo's `Database`/`Collection` surface -- including unique
(and unique-compound) index enforcement via `DuplicateKeyError`, and
accepting the `expireAfterSeconds` index option -- to exercise the real
repository code paths without a network dependency. `mongomock` was added
as a `dev` extra in `backend/pyproject.toml`.

If a real MongoDB becomes available in CI or local dev, these tests still
pass unmodified against it: the fixture only needs to swap
`mongomock.MongoClient()` for a real `pymongo.MongoClient(...)`, since both
expose the same `Database`/`Collection` API that the repositories are
written against.
"""

import mongomock
import pytest
from pymongo.database import Database

from app.repos import create_indexes


@pytest.fixture
def db() -> Database:
    """A fresh in-memory MongoDB database with every repo index created.

    A new `mongomock.MongoClient()` per test gives each test an isolated,
    empty database -- no cross-test state leakage -- while still exercising
    the same `create_indexes` entry point the real app factory calls on
    startup.
    """
    client = mongomock.MongoClient()
    database = client["aslinumber_test"]
    create_indexes(database)
    return database
