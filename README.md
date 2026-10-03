# AsliNumber

A multi-tenant helpline-integrity platform. This repository currently
implements **phase P1** of the full implementation plan: the monorepo
scaffold, a FastAPI backend with a multi-tenant authentication skeleton,
a styled login page, and a CI pipeline.

## Scope of this repository right now

This is the foundation phase only. There is **no brand, registry, sweep,
evidence, or finding functionality yet** -- no SerpApi integration, no job
queue processing, no LLM calls. The worker and scheduler processes run
and connect to MongoDB, but idle: they prove the process-role wiring
works, not that any sweep logic exists. That arrives in later phases.

What *is* here: a working login flow (argon2id password hashing, JWT
access tokens, rotating refresh-token cookies with reuse detection,
account lockout, tenant switching), a /health endpoint, a seeded demo
tenant/user set, and a frontend scaffold with the product's design tokens
and a login screen.

## Quick start (Docker)

Requires Docker Desktop. Run the compose stack manually in your own
terminal (it starts long-running services, so run it yourself rather
than from an automated session):

    docker compose up --build

This starts MongoDB, the API (port 8000), an idle worker, an idle
scheduler, and the frontend dev server (port 5173). On first start, with
the default DEMO_MODE=true, the API seeds two demo tenants and four
demo users (one per role).

Open http://localhost:5173 and log in with any of:

| Email | Role |
|---|---|
| owner@demo.aslinumber.test | owner |
| admin@demo.aslinumber.test | admin |
| analyst@demo.aslinumber.test | analyst |
| viewer@demo.aslinumber.test | viewer |

Password for all demo accounts: DemoPassword123! (override via
DEMO_PASSWORD before any real deployment -- see .env.example).

You should reach a working, logged-in state within a few minutes of a
fresh clone.

## Quick start (native, no Docker)

Backend (Python 3.12). Run these yourself in a terminal:

    cd backend
    pip install -e ".[dev]"
    copy ..\.env.example ..\.env
    python -m app.cli seed --demo
    python -m app.roles

Frontend (Node 20). Run these yourself in a terminal (the dev server is
long-running, so start it manually rather than from an automated session):

    cd frontend
    npm install
    npm run dev

## Development

PowerShell (Windows):

    .\scripts\setup.ps1
    .\scripts\lint.ps1
    .\scripts\test.ps1
    .\scripts\seed.ps1

Bash (macOS/Linux), or via make:

    make setup
    make lint
    make test
    make seed

## Environment variables

Copy .env.example to .env and fill in real values. .env is git-ignored
and must never be committed. Key variables:

- MONGO_URI -- MongoDB connection string. Include a database name
  (e.g. /aslinumber); otherwise the driver falls back to the test
  database.
- JWT_SECRET, FERNET_KEY -- generate strong random values locally.
- DEMO_MODE -- when true, the API refuses to start unless bound to
  127.0.0.1 or READ_ONLY=true (a safety guard against exposing seeded
  demo credentials on a public interface).
- LLM_PROVIDER=groq, GROQ_API_KEY, etc. -- declared for a later phase
  (summary generation); unused by anything in this phase.

See .env.example for the full list.

## Repository layout

    backend/      FastAPI API, worker, and scheduler process roles (Python 3.12)
    frontend/     Vite + React + TypeScript + Tailwind (login page only, for now)
    docs/         Project documentation (not all files are tracked in git)
    scripts/      setup/lint/test/compose-up/seed, in both .ps1 and .sh
    .github/      CI workflow
    docker-compose.yml   Local dev stack: mongo, api, worker, scheduler, web

## Testing

- Backend: pytest (unit + integration), including Hypothesis
  property-based tests for the auth logic (password hashing, token
  round-trips, refresh rotation, lockout, RBAC ordering, the demo-mode
  startup guard).
- Frontend: vitest + React Testing Library for the login page and its
  shared components.

CI (.github/workflows/ci.yml) runs both suites, plus Ruff and
ESLint/Prettier, on every push and pull request.