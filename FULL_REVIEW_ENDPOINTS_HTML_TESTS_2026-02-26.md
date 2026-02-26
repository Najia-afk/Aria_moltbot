# Full Project Review — Endpoints / HTML / Tests

Date: 2026-02-26
Scope: API endpoint surface, web templates API usage, scripts/tests HTTP usage under API-key auth.

## Inventory Snapshot

- API route decorators discovered: **235**
- HTML `fetch(...)` calls discovered: **124**
- Test HTTP-call patterns discovered: **56**
- Script HTTP-call patterns discovered: **9**

## High-Impact Fixes Completed

### 1) Auth hardcoding and script compatibility

- Removed hardcoded secrets and switched to env-driven keys in:
  - `scripts/test_all.py`
  - `scripts/test_app_managed.py`
- Added optional `X-API-Key` handling in utility scripts:
  - `scripts/_audit.py`
  - `scripts/_check_sessions.py`
  - `scripts/verify_roundtable_history_endpoints.py`
  - `scripts/_check_failures.py`

### 2) Dashboard proxy 401 remediation

- Added proxy-level key injection fallback in `src/web/app.py`:
  - If browser request lacks `X-API-Key`, proxy injects `ARIA_API_KEY`.
  - Uses `ARIA_ADMIN_KEY` for `admin/*` paths when available.
- Wired required env vars into `aria-web` service in `stacks/brain/docker-compose.yml`.

### 3) Compose hardcoded healthcheck cleanup

- Replaced hardcoded internal healthcheck ports with env-driven internal port vars (with fallbacks) across services.
- Synced `.env.example` with internal healthcheck port variables.

### 4) Template endpoint contract drift fixes

- `src/web/templates/engine_operations.html`
  - Migrated from legacy `/api/engine/cron/jobs...` pattern to active `/api/engine/cron` contract.
  - Corrected methods and history parsing (`entries` support).
- `src/web/templates/engine_health.html`
  - Rewired to existing endpoints: `/api/health`, `/api/status`, `/api/host-stats`.
  - Updated status/metrics rendering to current payload shape.
- `src/web/templates/operations.html`
  - Replaced legacy `/api/engine/...` assumptions with `/api/health` and `/api/stats`.

## Validation Status

- Static error checks for newly edited files: **No errors found**.
- Targeted legacy endpoint grep checks (e.g. `/engine/health`, `/engine/cron/jobs`, `/stats/quick` in edited templates): **clean**.
- Remaining `sessions.html` calls to `/api/engine/sessions*` and `/api/engine/sessions/ghosts` were verified as valid against current routers.

## Final Exhaustive Matrix Pass (Completed)

- Added reproducible generator: `scripts/generate_endpoint_call_matrix.py`
- Generated outputs:
  - `ENDPOINT_CALL_MATRIX_2026-02-26.md`
  - `endpoint_call_matrix_2026-02-26.json`
- Final machine summary:
  - route_count: 237
  - call_count: 64
  - template_calls: 7
  - test_calls: 23
  - script_calls: 34
  - unresolved_literal_api_calls: 0

## Additional High-Impact Auth Fix in This Pass

- Fixed missing REST auth dependency wiring for engine chat/roundtable registration:
  - `src/api/routers/engine_chat.py` (`register_engine_chat` now accepts dependencies)
  - `src/api/routers/engine_roundtable.py` (`register_roundtable` now accepts dependencies)
  - `src/api/main.py` now registers both with `_api_deps`
- Result: `/engine/chat/*` and `/engine/roundtable*` REST routes now enforce API key consistently with the rest of protected API routers.

## Runtime Incident Fix — Mac Website → Docker API

Issue observed live:

- Website/API calls from Mac to Docker were intermittently failing on protected endpoints.

Root causes fixed:

1. `src/web/app.py`
  - API reverse-proxy route was not effectively exempt from CSRF checks for POST/PUT/PATCH/DELETE.
  - Fixed by explicitly applying `csrf.exempt(api_proxy)` after route definition.

2. `stacks/brain/traefik-dynamic.template.yaml` + `stacks/brain/traefik-entrypoint.sh` + `stacks/brain/docker-compose.yml`
  - Traefik `/api/*` routes forwarded directly to `aria-api` without server-side API key injection, causing browser-side 401s.
  - Added `api-auth-inject` middleware with `X-API-Key` custom request header.
  - Passed `ARIA_API_KEY` into Traefik environment and ensured entrypoint template renderer substitutes `${ARIA_API_KEY}`.

Post-fix live verification:

- `http://127.0.0.1:55559/api/engine/chat/sessions` (web proxy path) → **201**
- `http://127.0.0.1:33218/api/engine/chat/sessions` (Traefik HTTP) → **201**
- `https://127.0.0.1:17779/api/engine/chat/sessions` (Traefik HTTPS) → **201**
- `https://127.0.0.1:17779/api/engine/chat/sessions/{id}/messages` → **200** with Aria reply

This closes the Mac→website→Docker API auth failure path for standard dashboard usage.

## Remaining Work (Optional Hardening)

The endpoint-to-callsite matrix is complete for literal `/api` call paths and currently reports zero unresolved literal API calls.

Optional follow-up hardening:

1. Extend parser support for dynamic URL expressions (`{expr}`) to perform context-aware resolution where possible.
2. Run full integration/e2e suites against a live secured stack to validate behavioral parity beyond static mapping.

## Current Risk Level

- **High-risk issues addressed** (auth hardcoding, dashboard 401 path, major endpoint drift, healthcheck hardcoding).
- **Residual risk: medium/low**, mostly from possible long-tail mismatches in less-used pages/scripts.

## Runtime Validation Addendum (Live Secured Stack)

Date: 2026-02-26
Execution target: running `stacks/brain` compose stack (API mapped to dynamic host port)

### Runtime smoke driver

- Added: `scripts/runtime_smoke_check.py`
- Output artifact: `aria_souvenirs/docs/runtime_smoke_2026-02-26.json`

### Smoke results summary

- `api_base`: `http://127.0.0.1:45669`
- `api_key_configured`: `true`
- `GET /api/health`: **200**
- `GET /api/status`: **200**
- `POST /api/engine/chat/sessions` without key: **401** (`Invalid or missing API key`)
- `POST /api/engine/chat/sessions` with key: **201**
- `POST /api/engine/roundtable/swarm`: **201**
- `POST /api/engine/roundtable/swarm/async`: **202**
- Aria loop check:
  - create session (`agent_id=aria`): **201**
  - send message in session: **200**
  - assistant content confirms loop active ("Aria loop active and cycling.")

### Notes

- Secured auth behavior is now validated live: protected route rejects no-key and accepts valid-key requests.
- Swarm execution is validated with registered agent IDs (`aria`, `analyst`).
- One swarm vote entry reported an upstream model auth error for `analyst` in this run; endpoint contract and swarm orchestration remained functional (request completed with consensus payload).
