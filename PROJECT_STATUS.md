# AsliNumber — Project Status

**Scope note:** this covers only **Phase P1** of `docs/aslinumber-implementation-plan.md` ("Repository, CI, containers, auth skeleton"), tracked in the spec at `.kiro/specs/aslinumber-p1-foundation/`. The full product (brands, sweeps, findings, ML, monitoring, etc. - plan phases P2-P14) has not been started. P1 is a self-contained foundation slice, not the whole project.

## Summary

**26 / 68 tasks complete (38%)** per `.kiro/specs/aslinumber-p1-foundation/tasks.md`.

**Current test state (verified by running the suites just now, not assumed):**
- Backend: **71 passed, 12 failed** (`python -m pytest -q` in `backend/`)
- Backend lint: **1 error** (`ruff check .`) - an unused import in a stray debug file
- Frontend: typecheck passes clean (`tsc --noEmit`); no component tests exist yet

The 12 backend failures are a real, diagnosed bug (see Blockers below), not flaky tests. Nothing should be considered "working" past that bug until it's fixed and re-verified.

---

## Checklist

### Setup & tooling
- [x] Monorepo scaffold (`backend/app`, `frontend`, `fixtures`, `deploy`, `scripts`, `docs`)
- [x] Backend `pyproject.toml` (pinned deps, Ruff, pytest config)
- [x] Pre-commit hooks config (Ruff, Prettier, gitleaks)
- [x] Frontend scaffold (Vite + React + TS + Tailwind, `package.json`)
- [x] Tailwind design tokens + self-hosted font `@font-face` rules (actual `.woff2` font files still need to be downloaded by a human - see Blockers)

### Backend - config & core infrastructure
- [x] `Settings` + DEMO_MODE startup guard (`app/config.py`)
- [x] MongoDB client wrapper + reachability check (`app/core/db.py`)
- [x] Error envelope + `AppError` (`app/core/errors.py`)
- [x] Security headers middleware (`app/core/security_headers.py`)
- [ ] FastAPI app factory, `/health` route, `ROLE=api|worker|scheduler|all` entry points - not started (`app/main.py`, `app/roles.py`, `app/api/routers/system.py` are all still empty stubs; two dispatch attempts failed before writing any code)
- [ ] Unit tests for `/health` endpoint - blocked on the above

### Backend - data models & repositories
- [x] Pydantic domain models + `Role` enum (`app/models/`)
- [ ] Repositories for users/tenants/memberships/sessions (code exists in `app/repos/`, but 12 of its tests currently fail - not functioning correctly yet; see Blockers)

### Backend - auth logic
- [x] Argon2id password hashing (`app/auth/passwords.py`)
- [x] Access token issuance/decoding, refresh token generation/hashing (`app/auth/tokens.py`)
- [ ] Session creation/rotation/chain revocation (`app/auth/sessions.py`) - not started
- [ ] Account lockout tracking (`app/auth/lockout.py`) - not started
- [ ] `TenantContext` + `require_role` dependency (`app/auth/deps.py`) - not started

### Backend - property-based tests (Hypothesis)
- [x] Property 1: Password hash round-trip & non-disclosure
- [x] Property 2: Access token claim round-trip
- [x] Property 3: Security headers on every response
- [x] Property 8: Demo-mode startup guard
- [ ] Property 4: Refresh token storage never retains the raw token - not started
- [ ] Property 5: Refresh rotation chain integrity & reuse detection - not started
- [ ] Property 6: Lockout state machine - not started
- [ ] Property 7: Role ordering determines access - not started

### Backend - auth API routes
- [ ] `POST /auth/login` / `POST /auth/logout` - not started
- [ ] `POST /auth/refresh` (rotation + reuse handling) - not started
- [ ] `POST /auth/switch-tenant` / `GET /auth/me` - not started
- [ ] Per-IP rate limiting on login - not started

### Backend - CLI demo seeder
- [ ] `cli seed --demo` command - not started (`app/cli.py` is still a stub)
- [ ] Wire seeding into API startup - not started

### Frontend
- [x] Vite + React + TS + Tailwind project scaffold
- [x] Design tokens in Tailwind theme + font-loading CSS
- [ ] OpenAPI type generation script - not started (no backend schema to generate from yet, since `/health` route doesn't exist)
- [ ] `StatusBadge` / `FormField` shared components - not started
- [ ] Login page (validation, EN/HI strings, `fa-lock` icon) - not started
- [ ] Login API wiring + authenticated status view - not started
- [ ] Component tests (Login, StatusBadge) - not started

### Docker / deployment
- [ ] Backend & frontend Dockerfiles - not started
- [ ] `docker-compose.yml` - not started

### Environment & git hygiene
- [ ] `.env.example` - not started (a real `.env` and a legacy `env` file exist in the repo root - see Blockers)
- [ ] `.gitignore` - not started

### CI
- [ ] GitHub Actions workflow (`.github/workflows/ci.yml`) - not started

### Developer scripts & docs
- [ ] `scripts/*.ps1` + `*.sh` - not started (`scripts/` only has a `.gitkeep`)
- [ ] `Makefile` - not started
- [ ] `README.md` - not started

---

## Blockers / Issues

1. **Repository layer bug (blocks everything downstream of it - sessions, lockout, auth routes, CLI seeder).** `app/models/common.py`'s `PyObjectId` type serializes `ObjectId -> str` unconditionally, including in plain Python-mode `model_dump()`. Every repo's `create()` method calls `model_dump(by_alias=True)` before inserting into MongoDB, so every document's `_id` (and any `ObjectId` foreign key: `userId`, `tenantId`, `rotatedFrom`) gets stored as a **string**, not a real `ObjectId`. Every later lookup that filters by a real `ObjectId` instance (`find_by_id`, `increment_failed_logins`, session rotation-chain walks) then silently matches nothing. 12 tests currently fail because of this. Fix is a one-line change (`when_used="json"` on the serializer) but it has not been applied yet - two attempts to dispatch this fix were interrupted by a tooling outage mid-session.

2. **Lint failure from a leftover debug file.** `backend/_scratch_test3.py` is a scratch script (used to manually inspect the bug above) left in the repo root with an unused import, failing `ruff check .`. It isn't part of the spec and should be deleted.

3. **Two tasks never actually executed despite being attempted twice.** `app/main.py`, `app/roles.py`, and `app/api/routers/system.py` are confirmed still at their original stub content from the initial scaffold - the FastAPI app, `/health` route, and process-role entry points do not exist. Two sub-agent dispatches for this failed (one network timeout, one one-hour stall with no output); task-tracking tooling then became unavailable mid-session, so this work is stalled, not done.

4. **Font files are a known, documented gap, not a bug.** `frontend/src/assets/fonts/README.md` explains that the actual `.woff2` binaries for Hind/Fraunces/JetBrains Mono must be downloaded by a human - this was called out intentionally when the CSS was written and isn't new.

5. **Root-level file hygiene.** There's a real `.env`, a legacy `env` (no leading dot), and an unrelated `tm2b.json` (looks like unrelated version-list data, possibly dropped in by accident) sitting in the repo root. No `.gitignore` exists yet, so none of this is excluded from version control if committed. Worth a human look before any `git add`.

## Next Steps

1. **Fix the `PyObjectId` serialization bug** in `app/models/common.py` and get all 71+12 backend tests green - this unblocks sessions, lockout, `TenantContext`, and every auth route, all of which depend on repositories that currently don't work.
2. **Implement the FastAPI app factory, `/health` route, and `roles.py`** (task 2.6) - this is the one piece of core infrastructure that's fully specified and ready to build, and it unblocks the OpenAPI type-generation step the frontend needs.
3. **Clean up repo hygiene** before any further work: delete `_scratch_test3.py`, decide what to do with `env` vs `.env` and `tm2b.json`, and get a `.gitignore` in place early so build artifacts (`node_modules`, `__pycache__`, `.pytest_cache`, etc.) don't end up tracked.
