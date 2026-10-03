"""MongoDB client wrapper and reachability check.

Wraps :class:`pymongo.MongoClient`, constructed from
:class:`app.config.Settings`'s ``MONGO_URI``. The ``/health`` route (task
2.6) and the ``worker``/``scheduler`` idle loops (task 2.6,
``app/roles.py``) depend on :func:`is_reachable` to report MongoDB
connectivity without ever raising, per Requirement 3.1/3.2 and the design's
Health_Endpoint behavior: "IF the Backend_API cannot reach MongoDB, THEN
THE Health_Endpoint SHALL respond with HTTP 200 and a JSON body reporting
MongoDB connectivity as unavailable" -- i.e. an unreachable Mongo is a
*reportable state*, never an unhandled exception.

A short ``serverSelectionTimeoutMS`` is used so a reachability check against
an unreachable host fails fast instead of hanging for PyMongo's default
30-second server selection window.
"""

from pymongo import MongoClient
from pymongo.errors import PyMongoError

from app.config import Settings

# PyMongo's default server selection timeout (30s) would make an
# unreachable Mongo hang the /health route and startup seeding far longer
# than useful. 2 seconds is enough for a local or same-network Mongo to
# answer, while still failing fast against an unroutable host.
_DEFAULT_SERVER_SELECTION_TIMEOUT_MS = 2000


def get_mongo_client(
    settings: Settings, *, server_selection_timeout_ms: int = _DEFAULT_SERVER_SELECTION_TIMEOUT_MS
) -> MongoClient:
    """Build a :class:`pymongo.MongoClient` from ``settings.MONGO_URI``.

    Construction itself never blocks on a network round-trip -- PyMongo
    connects lazily on first operation -- so this never raises due to the
    target server being unreachable. ``server_selection_timeout_ms`` bounds
    how long any later operation (including :func:`is_reachable`'s ping)
    will wait before giving up on finding a usable server.

    Args:
        settings: Application settings carrying ``MONGO_URI``.
        server_selection_timeout_ms: Milliseconds PyMongo will spend trying
            to select a server before raising a server-selection timeout.

    Returns:
        A configured, not-yet-connected ``MongoClient``.
    """
    return MongoClient(
        settings.MONGO_URI,
        serverSelectionTimeoutMS=server_selection_timeout_ms,
        tz_aware=True,
    )


def is_reachable(client: MongoClient) -> bool:
    """Check whether ``client``'s MongoDB deployment responds to a ping.

    Runs the lightweight ``ping`` admin command, per MongoDB's documented
    pattern for liveness checks. Never raises: any connection failure
    (server selection timeout, network error, auth failure, or any other
    ``PyMongoError``) is caught and reported as ``False`` so callers (the
    ``/health`` route, the startup seeder's precondition, the ``worker``/
    ``scheduler`` idle loops) can treat this as a plain boolean status
    rather than having to guard every call site with their own try/except.

    Args:
        client: A ``MongoClient`` built by :func:`get_mongo_client`.

    Returns:
        ``True`` if the deployment responded to the ping, ``False`` on any
        connection failure.
    """
    try:
        client.admin.command("ping")
    except PyMongoError:
        return False
    return True
