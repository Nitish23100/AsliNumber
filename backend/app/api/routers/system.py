"""System routes: liveness and dependency health.

Implements Requirement 3.1/3.2: ``GET /health`` always returns HTTP 200
(the API process itself being reachable is what "health" means here), with
a JSON body separately reporting whether MongoDB responded to a ping. An
unreachable MongoDB is a *reportable state* in the body, never a non-200
status or an unhandled exception -- callers that need to react to a down
database read the ``mongo`` field, not the HTTP status.
"""

from fastapi import APIRouter, Request

from app.core.db import is_reachable

router = APIRouter(tags=["system"])


@router.get("/health")
def get_health(request: Request) -> dict[str, str]:
    """Report API liveness and MongoDB reachability.

    Always HTTP 200. ``mongo`` is ``"ok"`` when the deployment responds to
    a ping, ``"unavailable"`` on any connection failure (per
    :func:`app.core.db.is_reachable`, which never raises).
    """
    client = request.app.state.mongo_client
    mongo_status = "ok" if is_reachable(client) else "unavailable"
    return {"status": "ok", "mongo": mongo_status}
