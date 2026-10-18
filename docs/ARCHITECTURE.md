# Architecture

## Overview
Pramaan AI is a single deployable service: a FastAPI backend that also serves a vanilla-JS single-page frontend. State lives in one SQL database (SQLite by default, PostgreSQL in Docker). All external integrations are optional and degrade gracefully.

## Request flow
1. **Browser** loads `index.html`, then `js/app.js`. `boot()` calls `GET /api/auth/me`; the session cookie is `httpOnly`, so JavaScript only learns the user profile, never a token.
2. **Middleware** (`backend/main.py`) assigns a request ID, applies the per-IP rate limit, runs the route, then adds security headers including the Content-Security-Policy.
3. **Auth guard** (`security.current_user`) reads the access cookie (or a Bearer header for API clients), enforces the CSRF header on unsafe methods, checks revocation, loads the user.
4. **Routers** are thin: validate input (Pydantic), enforce role and ownership, call a service, write audit/timeline entries.
5. **Services** hold the logic and are unit-testable without HTTP.

## Session lifecycle
```
login/register -> set cookies: pr_at (15 min, httpOnly), pr_rt (7 d, httpOnly, path /api/auth), pr_csrf (readable)
API call 401   -> api.js POST /auth/refresh (X-CSRF-Token) -> server rotates refresh token (old one marked used) -> retry once
refresh replay -> an already-used refresh token is presented -> ALL refresh tokens of that user revoked + audit event
logout         -> access jti added to revoked_tokens, refresh row revoked, cookies cleared
```

## Analysis pipeline (`services/pipeline.py`)
```
claim ──► denial_codes.info()  (CARC/RARC/EOB dataset + category + prior)
      ├─► policies visible to user (shared + own org) filtered by payer
      ├─► rag.retrieve()       (TF-IDF [+ embeddings], procedure-code boost)
      ├─► specific = hits from payer-specific policies (generic "ALL" standards excluded)
      ├─► evidence.analyse()   (chart sentences ⇄ policy criteria → met/partial/missing)
      ├─► predictor.predict()  (logistic regression; model_kind synthetic|trained)
      └─► deadlines.deadline() (appeal_rules.csv; verified flag)
```
`no_policy = True` when no payer-specific policy was relevant. The letter then says so explicitly.

## Letter generation (`services/appeal_gen.py`)
`generate()` tries Claude when `ANTHROPIC_API_KEY` is set: facts JSON → `deid.deidentify()` → API (retry with backoff) → `deid.reinsert()` → citation guard. Any failure returns the deterministic template with the reason in the `engine` field (`template:fallback-citation`, `template:fallback-api`).

## Data model (`backend/models.py`)
`orgs` ⟵ `users` ⟶ `claims` ⟶ `appeals`, `claim_events`; `policies` (org_id NULL = shared, read-only); `refresh_tokens`, `revoked_tokens`, `audit_log`, `notifications`, `contact_messages`, `icd_cache`. Timestamps are strings so SQLite and PostgreSQL behave the same. `backend/database.py` translates `?` placeholders to named binds and handles `INSERT OR IGNORE` and `RETURNING id` per dialect.

## Isolation rules
- Claims and appeals are owned by one user; every query filters by `user_id`, other users get 404.
- Policies: shared library (`org_id IS NULL`) is read-only; uploads belong to the uploader's organisation.
- Roles are enforced server-side (`require_biller`, `require_admin`) and mirrored by the router guard.

## Frontend structure
`public.js` renders the marketing pages from `/api/site/content` and `/api/public/stats`. `auth.js` handles sign-in/up/2FA/reset. `portal/` holds the three portals: `shell.js` (frame, bell, theme, autocomplete), `dashboard.js` (Chart.js), `claims.js`, `appeals.js` (workspace), `library.js`, `settings.js`, `admin.js`. Theme is stored per user on the server and mirrored in `localStorage` for first paint.

## Deployment
`docker compose up --build` starts PostgreSQL and the app. `deploy/entrypoint.sh` waits for the DB, runs `alembic upgrade head`, then starts Uvicorn. Policies from `backend/data/policies` are seeded idempotently on startup. Optional nginx profile terminates the public port.
