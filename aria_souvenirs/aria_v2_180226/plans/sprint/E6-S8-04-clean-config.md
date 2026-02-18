# S8-04: Clean Config — Remove OPENCLAW_* and CLAWDBOT_* Variables
**Epic:** E6 — OpenClaw Removal | **Priority:** P0 | **Points:** 2 | **Phase:** 8

## Problem
`src/api/config.py` still defines `OPENCLAW_JOBS_PATH`, `OPENCLAW_SESSIONS_INDEX_PATH`, `OPENCLAW_AGENTS_ROOT`, and `OPENCLAW_SESSIONS_SYNC_INTERVAL_SECONDS`. The SERVICE_URLS dict still includes the `"clawdbot"` entry. The `.env.example` still lists `CLAWDBOT_*` variables. All must be removed.

## Root Cause
These config variables were used by the sessions router and health checks to talk to OpenClaw. With the engine replacing OpenClaw, these variables are dead code that will confuse developers.

## Fix

### 1. Clean `src/api/config.py`

```python
"""
Aria Brain API — Configuration
All environment variables and service configuration in one place.
"""

import os
from datetime import datetime, timezone

# ── Database ──────────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required")

# ── Networking ────────────────────────────────────────────────────────────────
DOCKER_HOST_IP = os.getenv("DOCKER_HOST_IP", "host.docker.internal")
MLX_ENABLED = os.getenv("MLX_ENABLED", "false").lower() == "true"

# ── Service discovery (name → (base_url, health_path)) ───────────────────────
SERVICE_URLS: dict[str, tuple[str, str]] = {
    "grafana":    (os.getenv("GRAFANA_URL",    "http://grafana:3000"),           "/api/health"),
    "prometheus": (os.getenv("PROMETHEUS_URL",  "http://prometheus:9090"),        "/prometheus/-/healthy"),
    "ollama":     (os.getenv("OLLAMA_URL",      f"http://{DOCKER_HOST_IP}:11434"), "/api/tags"),
    "litellm":    (os.getenv("LITELLM_URL",     "http://litellm:4000"),          "/health/liveliness"),
    "pgadmin":    (os.getenv("PGADMIN_URL",     "http://aria-pgadmin:80"),       "/"),
    "browser":    (os.getenv("BROWSER_URL", "http://aria-browser:3000"),         "/"),
    "traefik":    (os.getenv("TRAEFIK_URL",     "http://traefik:8080"),          "/api/overview"),
    "aria-web":   (os.getenv("ARIA_WEB_URL",    "http://aria-web:5000"),         "/"),
    "aria-api":   (os.getenv("ARIA_API_SELF_URL", "http://localhost:8000"),      "/health"),
}

if MLX_ENABLED:
    SERVICE_URLS["mlx"] = (
        os.getenv("MLX_URL", f"http://{DOCKER_HOST_IP}:8080"),
        "/v1/models",
    )

# ── Admin / Service control ──────────────────────────────────────────────────
ARIA_ADMIN_TOKEN = os.getenv("ARIA_ADMIN_TOKEN")
if not ARIA_ADMIN_TOKEN:
    import logging as _logging
    _logging.getLogger("aria.api").warning("ARIA_ADMIN_TOKEN not set — admin endpoints will reject all requests")
SERVICE_CONTROL_ENABLED = os.getenv(
    "ARIA_SERVICE_CONTROL_ENABLED", "false"
).lower() in {"1", "true", "yes"}

# ── LiteLLM / Providers ─────────────────────────────────────────────────────
LITELLM_MASTER_KEY = os.getenv("LITELLM_MASTER_KEY", "")
MOONSHOT_KIMI_KEY  = os.getenv("MOONSHOT_KIMI_KEY", "")
OPEN_ROUTER_KEY    = os.getenv("OPEN_ROUTER_KEY", "")

# ── Startup jobs ─────────────────────────────────────────────────────────────
SKILL_BACKFILL_ON_STARTUP = os.getenv(
    "SKILL_BACKFILL_ON_STARTUP", "true"
).lower() in {"1", "true", "yes"}

# ── Runtime ──────────────────────────────────────────────────────────────────
STARTUP_TIME = datetime.now(timezone.utc)
API_VERSION  = "3.0.0"
```

**Changes from original:**
1. Removed `"clawdbot"` from `SERVICE_URLS` dict
2. Removed entire `# ── OpenClaw ──` section (4 variables):
   - `OPENCLAW_JOBS_PATH`
   - `OPENCLAW_SESSIONS_INDEX_PATH`
   - `OPENCLAW_AGENTS_ROOT`
   - `OPENCLAW_SESSIONS_SYNC_INTERVAL_SECONDS`

### 2. Clean `.env.example` in `stacks/brain/`

```bash
# Remove these lines from stacks/brain/.env.example:
CLAWDBOT_TOKEN=
CLAWDBOT_MEM_LIMIT=1g
CLAWDBOT_CPU_LIMIT=1.0
```

### 3. Clean `.env` (actual env file)

```bash
# Remove from stacks/brain/.env:
CLAWDBOT_TOKEN=<actual-token-value>
# And any other CLAWDBOT_* or OPENCLAW_* lines
```

### 4. Search for any remaining OPENCLAW_/CLAWDBOT_ references in Python

```bash
grep -rn "OPENCLAW_\|CLAWDBOT_" --include="*.py" src/ aria_mind/ aria_skills/ aria_agents/ \
    | grep -v __pycache__ \
    | grep -v "plans/"
```

Files likely to have references:
- `src/api/routers/sessions.py` — imports these config vars (cleaned in S8-05)
- `src/api/routers/health.py` — may check clawdbot health
- `aria_mind/config/` — may reference OPENCLAW paths

Each reference found must be removed or updated.

### 5. Clean health router if it references clawdbot

```python
# In src/api/routers/health.py, if there's a clawdbot health check:
# The SERVICE_URLS removal already handles this if the health router
# iterates SERVICE_URLS. Verify no hardcoded clawdbot references exist.
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | Config layer changes |
| 2 | .env for secrets (zero in code) | ✅ | Removing dead env vars from .env.example |
| 3 | models.yaml single source of truth | ❌ | N/A |
| 4 | Docker-first testing | ✅ | Verify API starts without removed vars |
| 5 | aria_memories only writable path | ❌ | N/A |
| 6 | No soul modification | ❌ | N/A |

## Dependencies
- S8-01 (Remove clawdbot service — no service needs these vars anymore)
- S8-05 (Clean sessions router — depends on these vars being removed from config first)

## Verification
```bash
# 1. No OPENCLAW_ in config.py:
grep -c "OPENCLAW_" src/api/config.py
# EXPECTED: 0

# 2. No clawdbot in SERVICE_URLS:
grep -c "clawdbot" src/api/config.py
# EXPECTED: 0

# 3. No CLAWDBOT_ in .env.example:
grep -c "CLAWDBOT_" stacks/brain/.env.example
# EXPECTED: 0

# 4. Config still imports successfully:
python -c "from src.api.config import SERVICE_URLS, DATABASE_URL; print(f'Services: {len(SERVICE_URLS)}')"
# EXPECTED: Services: 9 (was 10, removed clawdbot)

# 5. API starts without errors:
docker compose up -d aria-api
docker compose logs aria-api --tail=20 | grep -c "ERROR\|ImportError"
# EXPECTED: 0
```

## Prompt for Agent
```
Remove all OPENCLAW_* and CLAWDBOT_* configuration variables.

FILES TO READ FIRST:
- src/api/config.py (main config — remove OpenClaw section + clawdbot from SERVICE_URLS)
- stacks/brain/.env.example (remove CLAWDBOT_* vars)
- stacks/brain/.env (remove CLAWDBOT_* vars — careful with actual secrets)

STEPS:
1. Edit src/api/config.py:
   a. Remove "clawdbot" entry from SERVICE_URLS dict
   b. Delete the entire "# ── OpenClaw ──" section (lines 52-60)
2. Edit stacks/brain/.env.example: remove CLAWDBOT_TOKEN, CLAWDBOT_MEM_LIMIT, CLAWDBOT_CPU_LIMIT
3. Edit stacks/brain/.env: remove CLAWDBOT_TOKEN and any OPENCLAW_* lines
4. Run: grep -rn "OPENCLAW_\|CLAWDBOT_" --include="*.py" src/ to find remaining references
5. Clean each remaining reference
6. Verify: python -c "from src.api.config import SERVICE_URLS" works

SAFETY:
- Sessions router (src/api/routers/sessions.py) imports these vars — it will break until S8-05 rewrites it
- Health router iterates SERVICE_URLS — removing clawdbot is safe (it just won't be checked)
- The .env file contains real secrets — only remove CLAWDBOT_* lines, don't modify other secrets
```
