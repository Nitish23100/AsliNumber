"""FastAPI application factory and ASGI entry point.

``create_app()`` wires together everything task 2.1-2.4 already built:
``Settings`` (and its DEMO_MODE startup guard, which is allowed to
propagate here so an unsafe configuration "fails startup loudly" rather
than starting silently), a MongoDB client stored on ``app.state`` for
routes to use, the security-headers middleware, CORS restricted to the
configured frontend origin, and a single exception handler converting
every raised :class:`app.core.errors.AppError` into its envelope.

P2 (task 13.1) adds four routers alongside the P1 ``system``/``auth``
ones: ``brands``, ``official_contacts``, ``tenant``, and ``audit``. Each
of those router modules calls ``register_route(...)`` at import time
(see ``app.api.route_table``), so importing them here -- which happens
as soon as this module is imported, including by the Permission_Matrix_
Harness and Cross_Tenant_Harness (task 15) -- is what populates
``ROUTE_TABLE`` before either harness runs.

Deliberately does NOT seed demo data itself: `create_app()` runs on every
import of this module (including test collection, and FastAPI's own
TestClient construction with test-specific settings), so writing to
MongoDB here would mean every import attempts a real database write --
including against whatever `MONGO_URI` happens to resolve to at import
time, which tests have no chance to override first. Per Requirement 4.4,
demo seeding instead happens in `app.roles.run_api`, which only runs when
the API process is actually started (see that module for why).

The module-level ``app`` object is what Uvicorn (via ``app.roles``) and
FastAPI's own ``TestClient`` import directly.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routers import audit, auth, brands, official_contacts, system, tenant
from app.config import Settings
from app.core.db import get_mongo_client
from app.core.errors import AppError
from app.core.security_headers import SecurityHeadersMiddleware


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and fully wire a :class:`FastAPI` application instance.

    Args:
        settings: Pre-built :class:`Settings` to use instead of
            constructing one from the environment. Lets tests exercise a
            specific configuration (e.g. ``DEMO_MODE=False``) without
            mutating process environment variables. When omitted,
            ``Settings()`` is constructed normally -- including running
            the DEMO_MODE startup guard, which raises
            :class:`app.config.DemoModeStartupError` (left to propagate,
            so an unsafe configuration aborts the process loudly rather
            than starting with a silently-exposed demo instance).

    Returns:
        A configured :class:`FastAPI` app, not yet running. Does not seed
        demo data -- see module docstring for why.
    """
    if settings is None:
        settings = Settings()

    app = FastAPI(title="AsliNumber API")
    app.state.settings = settings
    app.state.mongo_client = get_mongo_client(settings)

    # Mounted close to the outside of the middleware stack (the default
    # for app.add_middleware) so it still observes responses Starlette's
    # own ServerErrorMiddleware/ExceptionMiddleware produce for unhandled
    # exceptions and HTTPExceptions, per security_headers.py's docstring.
    app.add_middleware(SecurityHeadersMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(AppError)
    async def _handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.to_envelope())

    app.include_router(system.router)
    app.include_router(auth.router)
    app.include_router(brands.router)
    app.include_router(official_contacts.router)
    app.include_router(tenant.router)
    app.include_router(audit.router)

    return app


app = create_app()
