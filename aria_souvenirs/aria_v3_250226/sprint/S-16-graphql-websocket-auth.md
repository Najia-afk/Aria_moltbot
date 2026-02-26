# S-16: GraphQL & WebSocket Authentication
**Epic:** E10 — Security Hardening | **Priority:** P0 | **Points:** 5 | **Phase:** 1

## Problem
Three critical authentication gaps expose the entire data layer:

1. **GraphQL endpoint is completely unprotected** — `src/api/main.py` L575 mounts the GraphQL router without `dependencies=[Depends(require_api_key)]`. Every REST router has this dependency, but GraphQL was missed. Additionally, `security_middleware.py` L78 **exempts** `/graphql` from body scanning.

2. **WebSocket endpoints have no auth** — `src/api/routers/engine_chat.py` L478-504 (`/ws/chat/{session_id}`) and `src/api/routers/engine_roundtable.py` L878-935 (`/ws/roundtable`) accept connections without any token validation. Anyone who guesses a session ID can stream messages.

3. **Auth is fail-open** — `src/api/auth.py` L47-55: when `ARIA_API_KEY` is not set, `require_api_key()` returns `"no-auth-configured"` and allows all requests. This is the default state for a fresh install.

## Root Cause
GraphQL was added after the auth dependency pattern was established. WebSocket auth requires a different mechanism (can't use HTTP header dependencies after upgrade). Fail-open was a dev convenience that was never locked down.

## Fix

### Fix 1: Add auth dependency to GraphQL router
**File:** `src/api/main.py` L575
**BEFORE:**
```python
app.include_router(gql_router, prefix="/graphql")
```
**AFTER:**
```python
app.include_router(gql_router, prefix="/graphql", dependencies=_api_deps)
```

### Fix 2: Remove GraphQL exemption from security middleware
**File:** `src/api/security_middleware.py` L78
Remove `/graphql` from the exemption list.

### Fix 3: Add WebSocket authentication
**File:** `src/api/routers/engine_chat.py` L478-504
```python
@router.websocket("/ws/chat/{session_id}")
async def websocket_chat(websocket: WebSocket, session_id: str):
    # Validate token from query param or first message
    token = websocket.query_params.get("token")
    if not _validate_ws_token(token):
        await websocket.close(code=4001, reason="Unauthorized")
        return
    await websocket.accept()
    # ... existing logic
```

**File:** `src/api/routers/engine_roundtable.py` L878-935 — same pattern.

### Fix 4: Create WebSocket token validation
**File:** `src/api/auth.py` — add:
```python
def _validate_ws_token(token: str | None) -> bool:
    """Validate WebSocket connection token.
    Uses same ARIA_API_KEY for now. Future: JWT with expiry.
    """
    if not ARIA_API_KEY:
        return True  # Will be fail-closed in Fix 5
    return token == ARIA_API_KEY
```

### Fix 5: Fail-closed auth in production
**File:** `src/api/auth.py` L47-55
**BEFORE:**
```python
if not ARIA_API_KEY:
    return "no-auth-configured"
```
**AFTER:**
```python
if not ARIA_API_KEY:
    if os.environ.get("ENGINE_DEBUG", "").lower() == "true":
        return "no-auth-configured"
    raise HTTPException(status_code=503, detail="API key not configured. Set ARIA_API_KEY.")
```

### Fix 6: Update WebSocket client code
**File:** `src/web/templates/engine_chat.html` L1835-1913
Add `?token=${API_KEY}` to WebSocket URL construction:
```javascript
const wsUrl = `${wsBase}/ws/chat/${sessionId}?token=${encodeURIComponent(apiKey)}`;
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer architecture | ✅ | Auth middleware is in the API layer |
| 2 | .env for secrets | ✅ | ARIA_API_KEY from .env |
| 3 | models.yaml truth | ❌ | |
| 4 | Docker-first testing | ✅ | |
| 5 | aria_memories writable | ❌ | |
| 6 | No soul modification | ❌ | |

## Dependencies
- None — this is a P0 standalone security fix.

## Verification
```bash
# 1. GraphQL requires auth:
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/graphql -H 'Content-Type: application/json' \
  -d '{"query": "{ activities { totalCount } }"}'
# EXPECTED: 401 (no API key)

curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/graphql \
  -H 'Content-Type: application/json' -H 'X-API-Key: YOUR_KEY' \
  -d '{"query": "{ activities { totalCount } }"}'
# EXPECTED: 200

# 2. WebSocket rejects without token:
# Use wscat: wscat -c ws://localhost:8000/ws/chat/test-id
# EXPECTED: Connection closed with code 4001

# 3. WebSocket accepts with token:
# wscat -c "ws://localhost:8000/ws/chat/test-id?token=YOUR_KEY"
# EXPECTED: Connected

# 4. Fail-closed without ENGINE_DEBUG:
# Unset ARIA_API_KEY, restart without ENGINE_DEBUG=true
# curl http://localhost:8000/health
# EXPECTED: 503

# 5. Fail-open in debug mode:
# Set ENGINE_DEBUG=true, unset ARIA_API_KEY
# curl http://localhost:8000/health
# EXPECTED: 200
```

## Prompt for Agent
```
Read these files FIRST:
- src/api/main.py (L330-L580 — middleware setup and router includes)
- src/api/auth.py (full)
- src/api/security_middleware.py (L70-L100 — exemption list)
- src/api/routers/engine_chat.py (L470-L510 — WebSocket endpoint)
- src/api/routers/engine_roundtable.py (L870-L940 — WebSocket endpoint)
- src/web/templates/engine_chat.html (L1830-L1920 — WS client code)

CONSTRAINTS: #2 (.env for ARIA_API_KEY). SECURITY-CRITICAL ticket.

STEPS:
1. Add `dependencies=_api_deps` to GraphQL router include in main.py
2. Remove /graphql from security_middleware exemption list
3. Add _validate_ws_token() to auth.py
4. Add token query param validation to both WebSocket endpoints
5. Change auth.py to fail-closed unless ENGINE_DEBUG=true
6. Update engine_chat.html WS client to pass token as query param
7. Check engine_roundtable.html for WS client code — update there too
8. Update .env.example to document ARIA_API_KEY as REQUIRED for production
9. Test all 5 verification commands
10. IMPORTANT: Do NOT break the /health endpoint — it must remain unauthenticated for Docker healthchecks
```
