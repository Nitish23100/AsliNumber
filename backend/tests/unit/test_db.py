"""Unit tests for backend.app.core.db.

Covers `is_reachable` returning False (never raising) against a
deliberately unreachable MongoDB URI, using a short server-selection
timeout so the test runs quickly and entirely offline -- no actual
MongoDB instance is required for this test to pass.
"""

from pymongo import MongoClient

from app.config import Settings
from app.core.db import get_mongo_client, is_reachable

# 192.0.2.0/24 is reserved by RFC 5737 ("TEST-NET-1") for documentation and
# example use. It is guaranteed non-routable, so connection attempts fail
# fast (or time out) without depending on any real network condition.
_UNREACHABLE_MONGO_URI = "mongodb://192.0.2.1:27017/aslinumber"

# Short enough that the test suite doesn't stall waiting on server
# selection against an address that will never respond.
_SHORT_TIMEOUT_MS = 200


def test_get_mongo_client_returns_a_mongo_client() -> None:
    settings = Settings(MONGO_URI=_UNREACHABLE_MONGO_URI)

    client = get_mongo_client(settings, server_selection_timeout_ms=_SHORT_TIMEOUT_MS)

    assert isinstance(client, MongoClient)
    client.close()


def test_is_reachable_returns_false_for_unreachable_uri_without_raising() -> None:
    settings = Settings(MONGO_URI=_UNREACHABLE_MONGO_URI)
    client = get_mongo_client(settings, server_selection_timeout_ms=_SHORT_TIMEOUT_MS)

    try:
        result = is_reachable(client)
    finally:
        client.close()

    assert result is False


def test_is_reachable_returns_bool_type() -> None:
    settings = Settings(MONGO_URI=_UNREACHABLE_MONGO_URI)
    client = get_mongo_client(settings, server_selection_timeout_ms=_SHORT_TIMEOUT_MS)

    try:
        result = is_reachable(client)
    finally:
        client.close()

    assert result is False
    assert isinstance(result, bool)
