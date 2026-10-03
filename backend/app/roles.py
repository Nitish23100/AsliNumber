"""Process-role entry points.

``ROLE=api|worker|scheduler|all`` (read directly from the environment,
not from :class:`app.config.Settings`, since it selects *which* process
behavior to run before any of ``Settings``'s own validation -- including
the DEMO_MODE startup guard -- is relevant) dispatches to one of four
run functions:

- ``api``: seeds demo data when ``DEMO_MODE`` is true (Requirement 4.4,
  done here rather than in ``app.main.create_app`` because that factory
  runs on every import -- including test collection -- so a real database
  write at import time would fire even when a test is about to swap in a
  different Mongo client; here it only runs once, at actual process
  startup), then runs the FastAPI app (``app.main.app``) under Uvicorn,
  bound to ``Settings.BIND_HOST`` on port 8000.
- ``worker`` / ``scheduler``: per Requirement 4.3, no job-queue or
  scheduled-job logic exists until phase P3, so these roles only prove the
  process starts and can reach MongoDB -- they log a reachability check
  once, then idle in a sleep loop. A later phase replaces the loop body
  with real job handling; the ``ROLE`` dispatch and connection wiring
  established here does not need to change when that happens.
- ``all``: for this phase, runs the API in the foreground. Running three
  full concurrent server loops (api + worker idle-loop + scheduler
  idle-loop) in one process would need threading/multiprocessing
  machinery disproportionate to a stub idle loop that does nothing yet --
  deliberately deferred until ``worker``/``scheduler`` have real job logic
  (P3) worth running concurrently. Documented here as a known scope
  limit, not an oversight.
"""

import logging
import os
import time

import uvicorn

from app.cli import seed_demo
from app.config import Settings
from app.core.db import get_mongo_client, is_reachable
from app.repos import create_indexes
from app.repos.brands_repo import BrandsRepo
from app.repos.memberships_repo import MembershipsRepo
from app.repos.tenants_repo import TenantsRepo
from app.repos.users_repo import UsersRepo

logger = logging.getLogger(__name__)

_IDLE_LOOP_SLEEP_SECONDS = 5


def run_api(settings: Settings) -> None:
    """Seed demo data (if DEMO_MODE) and run the FastAPI app under Uvicorn."""
    if settings.DEMO_MODE:
        client = get_mongo_client(settings)
        db = client.get_default_database()
        create_indexes(db)
        seed_demo(TenantsRepo(db), UsersRepo(db), MembershipsRepo(db), brands_repo=BrandsRepo(db))
        logger.info("Demo tenants, users, and brands seeded (idempotent).")

    uvicorn.run("app.main:app", host=settings.BIND_HOST, port=8000)


def _run_idle_loop(settings: Settings, role_name: str) -> None:
    """Connect to MongoDB, log reachability once, then idle.

    No job types exist until phase P3 (Requirement 4.3), so this proves
    only that the process starts and the configured ``MONGO_URI`` is
    reachable from this process role -- it does not read a ``jobs``
    collection or do any work.
    """
    client = get_mongo_client(settings)
    reachable = is_reachable(client)
    logger.info(
        "%s role started; MongoDB reachable: %s. Idling (no job types until P3).",
        role_name,
        reachable,
    )
    while True:
        time.sleep(_IDLE_LOOP_SLEEP_SECONDS)


def run_worker(settings: Settings) -> None:
    """Run the ``worker`` role's idle loop. See module docstring."""
    _run_idle_loop(settings, "worker")


def run_scheduler(settings: Settings) -> None:
    """Run the ``scheduler`` role's idle loop. See module docstring."""
    _run_idle_loop(settings, "scheduler")


def main() -> None:
    """Dispatch to the role named by the ``ROLE`` environment variable.

    Defaults to ``all`` when unset. For this phase, ``all`` runs the API
    in the foreground (see module docstring for why worker/scheduler are
    not also run concurrently yet).
    """
    role = os.environ.get("ROLE", "all")
    settings = Settings()

    if role == "api":
        run_api(settings)
    elif role == "worker":
        run_worker(settings)
    elif role == "scheduler":
        run_scheduler(settings)
    elif role == "all":
        logger.info(
            "ROLE=all: running the API in the foreground only. "
            "worker/scheduler have no job logic until phase P3, so this "
            "phase does not run them concurrently in-process."
        )
        run_api(settings)
    else:
        raise ValueError(f"Unknown ROLE={role!r}. Expected one of: api, worker, scheduler, all.")


if __name__ == "__main__":
    main()
