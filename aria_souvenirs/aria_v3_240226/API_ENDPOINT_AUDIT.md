# API Endpoint Audit — 2026-02-24

## Overview

- **Total endpoints found in code:** 226 (222 REST + 2 WebSocket + 1 GraphQL + 1 aiohttp)
- **Total routers:** 31
- **Documented in API_ENDPOINT_INVENTORY.md:** ~197
- **Ghost endpoints (in docs, not code):** 2
- **Undocumented endpoints (in code, not docs):** 31
- **Architecture violations:** None critical (5-layer enforced)
- **Authentication:** ZERO on ALL 222 endpoints

---

## Ghost Endpoints (Documented but Missing)

| Endpoint | Status |
|----------|--------|
| `DELETE /proposals/{proposal_id}` | Never implemented |
| `DELETE /hourly-goals/{goal_id}` | Never implemented |

---

## Undocumented Endpoints (31)

### Missing Entire Routers (3)

| Router | Endpoints | Lines |
|--------|-----------|-------|
| artifacts.py | 4 CRUD endpoints for aria_memories/ files | 182 |
| engine_roundtable.py | 12 REST + 1 WebSocket | 1039 |
| rpg.py | 4 RPG dashboard endpoints | 432 |

### Individual Missing Endpoints (11)
- `GET /analysis/sentiment/score`
- `PATCH /engine/sessions/{id}/title`
- `POST /agents/db/enable-core`
- `DELETE /skills/invocations/purge-test-data`
- Plus 7 more added after inventory was written

---

## Security Assessment

### 🔴 HIGH Severity (5)

| # | Issue | Impact |
|---|-------|--------|
| 1 | **Zero authentication on ALL 222 endpoints** | Admin operations fully exposed |
| 2 | Admin endpoints unprotected (`/admin/services/{action}`, `/maintenance`) | Anyone can restart services |
| 3 | Rate limiting only on write methods | Expensive reads unprotected |
| 4 | No CSRF protection on state-changing endpoints | Cross-site request forgery |
| 5 | No API key validation middleware | No access control |

### 🟡 MEDIUM Severity (5)

| # | Issue | Impact |
|---|-------|--------|
| 6 | ~15 routers use raw `request.json()` instead of Pydantic models | No automatic validation |
| 7 | No input sanitization on search endpoints | Potential injection |
| 8 | WebSocket endpoints have no auth | Unauthenticated streaming |
| 9 | File artifact endpoints allow path manipulation | Potential directory traversal |
| 10 | No audit logging for admin operations | No accountability trail |

---

## Performance Concerns

| # | Issue | Router | Impact |
|---|-------|--------|--------|
| 1 | KG BFS traversal with N+1 queries | knowledge.py | Graph traversal can trigger cascading DB queries |
| 2 | Roundtable listing loads all sessions into memory | engine_roundtable.py | Memory exhaustion with many sessions |

---

## Architecture Compliance

**5-layer architecture is well-enforced:**
- Zero direct DB imports in `aria_skills/` or `aria_agents/`
- Skills correctly use `api_client` for API access
- All DB access goes through ORM models in `src/api/db/`

---

## Test Coverage

| Status | Count |
|--------|-------|
| Endpoints with tests | ~177 |
| Endpoints without tests | ~49 |
| Routers with zero coverage | agents_crud.py, models_crud.py, artifacts.py, rpg.py |
