# S-57: Web UI Chat + Agent Dashboard Wiring
**Epic:** E9 — Database Integration | **Priority:** P2 | **Points:** 4 | **Phase:** 3

## Problem

The web UI has templates for chat and agent management, but they have wiring issues:

### Chat UI (`src/web/templates/engine_chat.html`)

1. **WebSocket URL mismatch** (line ~1566): The chat UI connects to
   `/api/ws/chat/${sessionId}` but the WebSocket router defines the endpoint at
   `/ws/chat/{session_id}` (no `/api/` prefix). The FastAPI app has `root_path="/api"`,
   which means:
   - Via Traefik (production): `/api/ws/chat/...` → Traefik strips `/api` → works
   - Direct access (development): `/api/ws/chat/...` → 404 because actual path is `/ws/chat/...`

2. **Session API URL mismatch** (line ~1427): The chat UI calls
   `/api/engine/sessions` (engine_sessions router) for session listing, not
   `/api/engine/chat/sessions` (the chat router). Session listing works via
   engine_sessions, but **session creation and message sending** require the chat router's
   `/api/engine/chat/sessions` prefix.

### Agent Pages

3. **Agent pages** (`engine_agents.html`, `engine_agent_dashboard.html`) call
   `/api/engine/agents` and `/api/engine/agents/metrics` — these will work once S-53
   mounts the routers, but the URL prefix consistency should be verified.

### Operations Hub

4. **Operations pages** (`engine_operations.html`, `engine_agents_mgmt.html`,
   `engine_health.html`) — verify they call correct API URLs after router mounting.

## Root Cause

The web UI was built while the API was still being developed. The URL patterns in the
JavaScript fetch calls don't match the actual router prefixes after the API structure
was finalized. The WebSocket path differs from REST paths due to FastAPI's root_path
behavior.

## Fix

### Change 1: Fix WebSocket URL in chat UI

**File:** `src/web/templates/engine_chat.html` (line ~1566)

BEFORE:
```javascript
const ws = new WebSocket(`ws://${window.location.host}/api/ws/chat/${sessionId}`);
```

AFTER:
```javascript
const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const ws = new WebSocket(`${wsProtocol}//${window.location.host}/ws/chat/${sessionId}`);
```

### Change 2: Fix session API URLs in chat UI

**File:** `src/web/templates/engine_chat.html` (line ~1427)

Ensure session creation calls `/api/engine/chat/sessions` (the chat router) for:
- POST create session
- POST send message
- DELETE end session

Session listing can stay at `/api/engine/sessions` or switch to `/api/engine/chat/sessions`.

### Change 3: Verify all dashboard pages

Check all API URLs in these templates match their router prefixes:
- `engine_agents.html` → `/api/engine/agents`
- `engine_agent_dashboard.html` → `/api/engine/agents/metrics`
- `engine_cron.html` → `/api/engine/cron`
- `engine_operations.html` → cross-check all URLs
- `engine_health.html` → cross-check all URLs
- `heartbeat.html` → `/heartbeat`

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ❌ | Frontend templates only |
| 2 | .env for secrets (zero in code) | ✅ | No tokens/keys in JS |
| 3 | models.yaml single source of truth | ❌ | No model names in templates |
| 4 | Docker-first testing | ✅ | Must test via Docker Compose (Traefik proxy) |
| 5 | aria_memories only writable path | ❌ | No file writes |
| 6 | No soul modification | ❌ | No soul files |

## Dependencies
- S-52 must complete first — chat API router must be mounted
- S-53 must complete first — agent/metrics routers must be mounted

## Verification
```bash
# 1. WebSocket URL is correct:
grep -n "WebSocket" src/web/templates/engine_chat.html | head -5
# EXPECTED: ws:// or wss:// without /api/ prefix before /ws/

# 2. Chat session URL uses chat router:
grep -n "engine/chat/sessions" src/web/templates/engine_chat.html
# EXPECTED: matches for POST create and POST message send

# 3. Agent URLs match:
grep -n "engine/agents" src/web/templates/engine_agents.html
# EXPECTED: /api/engine/agents endpoint calls

# 4. No hardcoded localhost or IPs:
grep -rn "localhost\|127\.0\.0\.1\|http://aria" src/web/templates/engine_*.html
# EXPECTED: no matches (all relative URLs)

# 5. End-to-end chat test (manual):
# Open http://localhost/chat/ → Create session → Send message → See response
# EXPECTED: Chat works end-to-end
```

## Prompt for Agent
Read these files first:
- `src/web/templates/engine_chat.html` (full file — focus on JavaScript fetch/WebSocket calls)
- `src/web/templates/engine_agents.html` (full file — verify API URLs)
- `src/web/templates/engine_agent_dashboard.html` (full file — verify API URLs)
- `src/web/templates/engine_cron.html` (full file — verify API URLs)
- `src/web/templates/engine_operations.html` (full file — verify API URLs)
- `src/web/templates/engine_health.html` (full file — verify API URLs)
- `src/web/templates/heartbeat.html` (full file — verify API URLs)
- `src/api/routers/engine_chat.py` (lines 1-20 — router prefix)
- `src/api/routers/engine_agents.py` (lines 1-20 — router prefix)
- `src/api/routers/engine_agent_metrics.py` (lines 1-25 — router prefix)

Steps:
1. Audit every `fetch()` and `WebSocket()` call in all engine_* templates
2. Map each URL to its corresponding router and verify the prefix matches
3. Fix WebSocket URL to remove `/api/` prefix (FastAPI root_path handles this)
4. Fix any session creation URLs to use the chat router prefix
5. Verify no hardcoded hosts/IPs in templates
6. Run verification commands

Constraints: #2 (no secrets in JS), #4 (Docker test with Traefik)
