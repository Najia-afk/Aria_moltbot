# S-103: Add Authentication Middleware to FastAPI
**Epic:** E4 — Security Hardening | **Priority:** P0 | **Points:** 8 | **Phase:** 1

## Problem
All 222 REST endpoints and 2 WebSocket endpoints in `src/api/` have **zero authentication**. Admin endpoints (`/admin/services/{action}`, `/maintenance/*`, `/artifacts/*` write operations) are fully exposed to anyone who can reach the API.

The API is currently protected only by network isolation (Traefik reverse proxy on the Mac Mini LAN). If Traefik is misconfigured or the LAN is compromised, all endpoints are accessible.

## Root Cause
Authentication was never implemented. The FastAPI app has no middleware, dependency injection, or decorator for auth checks.

## Fix
Implement a two-tier auth system using FastAPI dependency injection:

### 1. Create `src/api/auth.py`
```python
"""Authentication middleware for Aria API."""
import os
import secrets
from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

# Keys loaded from environment
ARIA_API_KEY = os.environ.get("ARIA_API_KEY", "")
ARIA_ADMIN_KEY = os.environ.get("ARIA_ADMIN_KEY", "")

async def require_api_key(api_key: str = Security(API_KEY_HEADER)) -> str:
    """Require valid API key for standard endpoints."""
    if not ARIA_API_KEY:
        return "no-auth-configured"  # Fail-open in dev if no key set
    if not api_key or not secrets.compare_digest(api_key, ARIA_API_KEY):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return api_key

async def require_admin_key(api_key: str = Security(API_KEY_HEADER)) -> str:
    """Require admin API key for privileged endpoints."""
    if not ARIA_ADMIN_KEY:
        return "no-auth-configured"
    if not api_key or not secrets.compare_digest(api_key, ARIA_ADMIN_KEY):
        raise HTTPException(status_code=403, detail="Admin access required")
    return api_key
```

### 2. Add to .env.example
```
ARIA_API_KEY=your-api-key-here
ARIA_ADMIN_KEY=your-admin-key-here
```

### 3. Apply to routers
Add `dependencies=[Depends(require_api_key)]` to all routers:
```python
router = APIRouter(prefix="/goals", tags=["Goals"], dependencies=[Depends(require_api_key)])
```

Add `dependencies=[Depends(require_admin_key)]` to admin routers.

### 4. Health endpoint exemption
Keep `/health` and `/docs` unauthenticated for monitoring.

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer architecture | ✅ | Auth is API layer — correct placement |
| 2 | .env for secrets | ✅ | Keys in .env, only .env.example updated |
| 3 | models.yaml single source | ❌ | No model changes |
| 4 | Docker-first testing | ✅ | Must test in Docker |
| 5 | aria_memories writable path | ❌ | No memory changes |
| 6 | No soul modification | ❌ | No soul changes |

## Dependencies
- None — this is foundational for all other security work

## Verification
```bash
# 1. Without API key — should fail
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/goals
# EXPECTED: 401

# 2. With API key — should succeed
curl -s -H "X-API-Key: $ARIA_API_KEY" http://localhost:8000/goals | jq .
# EXPECTED: 200 with goals data

# 3. Health endpoint — no auth needed
curl -s http://localhost:8000/health | jq .status
# EXPECTED: "healthy" (no 401)

# 4. Admin endpoint without admin key — should fail
curl -s -o /dev/null -w "%{http_code}" -H "X-API-Key: $ARIA_API_KEY" http://localhost:8000/admin/services
# EXPECTED: 403

# 5. Admin endpoint with admin key — should succeed
curl -s -H "X-API-Key: $ARIA_ADMIN_KEY" http://localhost:8000/admin/services | jq .
# EXPECTED: 200
```

## Prompt for Agent
```
Read these files first:
- src/api/main.py (find the FastAPI app creation and router includes)
- src/api/routers/ (list all router files)
- .env.example

Steps:
1. Create src/api/auth.py with API key and admin key dependencies
2. Add ARIA_API_KEY and ARIA_ADMIN_KEY to .env.example
3. Add dependencies=[Depends(require_api_key)] to ALL routers except /health and /docs
4. Add dependencies=[Depends(require_admin_key)] to admin/maintenance routers
5. Update aria_skills/api_client/ to pass X-API-Key header in all requests
6. Update aria_engine to pass API key when calling the API
7. Test: verify unauthenticated requests return 401
8. Test: verify authenticated requests succeed
9. Test: verify /health remains unauthenticated

Constraints: .env for secrets (add to .env.example only). Docker-first testing.
Keys must be read from environment variables at startup.
```
