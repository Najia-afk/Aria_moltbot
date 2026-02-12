# S1-03: Fix API Route 404s — Social, Security, Operations
**Epic:** Sprint 1 — Critical Bugs | **Priority:** P1 | **Points:** 3 | **Phase:** 1

## Problem
Three API routes return 404 when accessed via the expected URL patterns:
1. `GET /api/social/posts` → 404 (actual route is `/api/social`)
2. `GET /api/security/reports` → 404 (actual route is `/api/security-events`)
3. `GET /api/operations/income` → 404 (actual route is `/api/rate-limits` or `/api/heartbeat`)

These mismatches exist because the router paths don't match the URL patterns that frontends or documentation expect.

## Root Cause
**social.py (line 20):** Router defines `@router.get("/social")` — the router is mounted at `/` prefix, so the endpoint is `/api/social`, not `/api/social/posts`. No `/posts` sub-route exists.

**security.py (line 31):** Router defines `@router.get("/security-events")` — there is no `/security/reports` route. Frontend may be calling the wrong URL.

**operations.py (line 37+):** Router defines `/rate-limits`, `/api-key-rotations`, `/heartbeat`, `/performance` — there is no `/operations/income` or `/operations` prefix route. The router handles operations-domain endpoints without a group prefix.

These are not bugs in the API itself — they are **documentation/reference mismatches**. The routes work correctly; the issue is that scripts or tools may reference wrong URLs.

## Fix
This is an **audit and documentation ticket**, not a code change. The routes are correctly defined. We need to:

1. **Document the correct routes** in a route reference file
2. **Verify all frontend templates** use correct API URLs
3. **Update any references** to wrong URLs

**Audit commands to run:**
```bash
# Get all registered routes:
curl -s http://localhost:8000/api/openapi.json | python3 -c "
import sys, json
spec = json.load(sys.stdin)
for path, methods in sorted(spec['paths'].items()):
    for method in methods:
        print(f'{method.upper():6s} {path}')
" 2>/dev/null | head -60
```

**If aliasing is desired (optional):**
Add redirect routes in respective routers:
```python
# In social.py — alias for /social/posts
@router.get("/social/posts")
async def get_social_posts_alias(...):
    return await get_social_posts(...)
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | API layer changes only |
| 2 | .env for secrets (zero in code) | ❌ | No secrets |
| 3 | models.yaml single source of truth | ❌ | No model references |
| 4 | Docker-first testing | ✅ | Verify in Docker after any route changes |
| 5 | aria_memories only writable path | ❌ | Code/docs only |
| 6 | No soul modification | ❌ | Not touching soul |

## Dependencies
None — independent audit ticket.

## Verification
```bash
# 1. List all API routes:
curl -s http://localhost:8000/api/docs | head -1
# EXPECTED: HTML page (Swagger docs accessible)

# 2. Correct social endpoint:
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/social
# EXPECTED: 200

# 3. Correct security endpoint:
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/security-events
# EXPECTED: 200

# 4. Correct operations endpoints:
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/rate-limits
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/heartbeat
# EXPECTED: 200 200

# 5. Frontend templates use correct URLs:
grep -rn "/social/posts\|/security/reports\|/operations/income" src/web/templates/ --include="*.html"
# EXPECTED: no output (no wrong references)
```

## Prompt for Agent
```
Audit API routes for correctness and fix any URL mismatches.

**Files to read:**
- src/api/routers/social.py (lines 15-45)
- src/api/routers/security.py (lines 15-40)
- src/api/routers/operations.py (lines 30-45)
- src/api/main.py (lines 40-80 — router mount points)

**Constraints:** 5-layer architecture, Docker-first.

**Steps:**
1. Read all router files to identify actual route paths
2. Search frontend templates for any references to wrong API URLs
3. Fix any frontend references using wrong paths
4. Optionally add route aliases for common mistaken paths
5. Document correct route table in a comment or doc file
6. Run verification commands
```
