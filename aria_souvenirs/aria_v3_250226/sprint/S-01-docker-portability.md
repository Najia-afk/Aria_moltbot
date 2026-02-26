# S-01: Docker Socket & Cross-Platform Portability Fix
**Epic:** E1 — Docker Portability | **Priority:** P0 | **Points:** 5 | **Phase:** 1

## Problem
`stacks/brain/docker-compose.yml` line 525 mounts `/var/run/docker.sock:/var/run/docker.sock:ro` in the `docker-socket-proxy` service. This path does not exist on Windows — the Docker Engine named pipe is `//./pipe/docker_engine`. On Linux without Docker Desktop, `host.docker.internal` resolution also fails for `litellm` and `aria-brain` services (missing `extra_hosts` entries).

Additionally, several ports are hardcoded without env var overrides:
- `stacks/brain/docker-compose.yml` L206: `"18793:4000"` (litellm — no env var)
- `stacks/brain/docker-compose.yml` L490: `"8000:8000"` (aria-api — no env var)
- `stacks/brain/docker-compose.yml` L355: `"5050:80"` (pgadmin — clashes with aria-web default port)
- `stacks/brain/docker-compose.yml` L298: `OLLAMA_MODEL: hf.co/unsloth/GLM-4.7-Flash-REAP-23B-A3B-GGUF:Q3_K_S` (hardcoded, no env var)

## Root Cause
The compose file was written for macOS Docker Desktop where `/var/run/docker.sock` is symlinked. No conditional or env var fallback was added for other platforms. Port numbers and model names are hardcoded instead of using `${VAR:-default}` pattern applied elsewhere.

## Fix

### Fix 1: Docker socket volume (L525)
**File:** `stacks/brain/docker-compose.yml` L525
**BEFORE:**
```yaml
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
```
**AFTER:**
```yaml
    volumes:
      - ${DOCKER_SOCKET:-/var/run/docker.sock}:/var/run/docker.sock:ro
```

### Fix 2: Add host.docker.internal to litellm (after L220)
**File:** `stacks/brain/docker-compose.yml` ~L220
**BEFORE:**
```yaml
    networks:
      - backend
```
**AFTER:**
```yaml
    extra_hosts:
      - "host.docker.internal:host-gateway"
    networks:
      - backend
```

### Fix 3: Add host.docker.internal to aria-brain (after L308)
**File:** `stacks/brain/docker-compose.yml` ~L308
Same pattern as Fix 2.

### Fix 4: Parameterize ports
**File:** `stacks/brain/docker-compose.yml`
- L206: `"${LITELLM_PORT:-18793}:4000"`
- L490: `"${API_PORT:-8000}:8000"`
- L355: `"${PGADMIN_PORT:-5051}:80"` (change default to 5051 to avoid clash)

### Fix 5: Parameterize Ollama model
**File:** `stacks/brain/docker-compose.yml` L298
**BEFORE:**
```yaml
      OLLAMA_MODEL: hf.co/unsloth/GLM-4.7-Flash-REAP-23B-A3B-GGUF:Q3_K_S
```
**AFTER:**
```yaml
      OLLAMA_MODEL: ${OLLAMA_MODEL:-hf.co/unsloth/GLM-4.7-Flash-REAP-23B-A3B-GGUF:Q3_K_S}
```

### Fix 6: Add all new vars to .env.example
**File:** `stacks/brain/.env.example` — append:
```env
# Docker socket path (Windows: //./pipe/docker_engine, Linux/Mac: /var/run/docker.sock)
DOCKER_SOCKET=/var/run/docker.sock
# Port overrides
LITELLM_PORT=18793
API_PORT=8000
PGADMIN_PORT=5051
# Ollama model (requires VRAM — leave empty to disable)
OLLAMA_MODEL=hf.co/unsloth/GLM-4.7-Flash-REAP-23B-A3B-GGUF:Q3_K_S
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer architecture | ❌ | Docker config only — no application code changes |
| 2 | .env for secrets | ✅ | All new values added to .env.example, not hardcoded |
| 3 | models.yaml | ❌ | No model code changes |
| 4 | Docker-first testing | ✅ | This ticket directly improves Docker portability |
| 5 | aria_memories writable | ❌ | No file write changes |
| 6 | No soul modification | ❌ | No soul files touched |

## Dependencies
None — standalone infrastructure ticket.

## Verification
```bash
# 1. Verify env var usage in docker-compose:
grep -n 'DOCKER_SOCKET\|LITELLM_PORT\|API_PORT\|PGADMIN_PORT\|OLLAMA_MODEL.*\$' stacks/brain/docker-compose.yml
# EXPECTED: 5+ matches showing ${VAR:-default} patterns

# 2. Verify no port 5050 clash:
grep -n '5050' stacks/brain/docker-compose.yml
# EXPECTED: only aria-web uses 5050, pgadmin uses 5051

# 3. Verify extra_hosts on litellm and aria-brain:
grep -A1 'extra_hosts' stacks/brain/docker-compose.yml
# EXPECTED: 3+ instances (aria-engine, litellm, aria-brain, aria-api)

# 4. Verify .env.example has all new vars:
grep -c 'DOCKER_SOCKET\|LITELLM_PORT\|API_PORT\|PGADMIN_PORT\|OLLAMA_MODEL' stacks/brain/.env.example
# EXPECTED: 5

# 5. Docker compose config validates:
docker compose -f stacks/brain/docker-compose.yml config --quiet
# EXPECTED: exit code 0
```

## Prompt for Agent
```
Read these files first:
- stacks/brain/docker-compose.yml (full file — 587 lines)
- stacks/brain/.env.example (full file — 236 lines)

CONSTRAINTS: Constraint #2 (secrets in .env) and #4 (Docker-first) apply.

STEPS:
1. In stacks/brain/docker-compose.yml:
   a. Line ~525: Replace `/var/run/docker.sock` with `${DOCKER_SOCKET:-/var/run/docker.sock}`
   b. Line ~220: Add `extra_hosts: ["host.docker.internal:host-gateway"]` to litellm service
   c. Line ~308: Add `extra_hosts: ["host.docker.internal:host-gateway"]` to aria-brain service
   d. Line ~206: Replace `"18793:4000"` with `"${LITELLM_PORT:-18793}:4000"`
   e. Line ~490: Replace `"8000:8000"` with `"${API_PORT:-8000}:8000"`
   f. Line ~355: Replace `"5050:80"` with `"${PGADMIN_PORT:-5051}:80"`
   g. Line ~298: Replace the hardcoded OLLAMA_MODEL with `${OLLAMA_MODEL:-hf.co/unsloth/...}`
2. In stacks/brain/.env.example: Add DOCKER_SOCKET, LITELLM_PORT, API_PORT, PGADMIN_PORT, OLLAMA_MODEL with comments.
3. Run verification commands.
```
