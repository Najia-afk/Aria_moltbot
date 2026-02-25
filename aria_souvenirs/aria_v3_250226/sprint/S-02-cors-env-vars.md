# S-02: CORS & Traefik Dynamic Config from Env Vars
**Epic:** E1 — Docker Portability | **Priority:** P1 | **Points:** 3 | **Phase:** 2

## Problem
`stacks/brain/traefik-dynamic.yaml` lines 249-252, 268-271, 289-292 hardcode CORS allowed origins to `http://localhost:5000`, `http://localhost:5050`, `http://aria-web:5000`. Any deployment using different ports or a custom domain will have CORS failures. The `traefik-dynamic.template.yaml` has the same hardcoded values but is meant to be processed by `traefik-entrypoint.sh`.

## Root Cause
The Traefik entrypoint (`stacks/brain/traefik-entrypoint.sh`) copies the template to `dynamic.yaml` but does no variable substitution — it's a raw copy. The CORS origins should be injected from environment variables.

## Fix

### Fix 1: Template the CORS origins in traefik-dynamic.template.yaml
**File:** `stacks/brain/traefik-dynamic.template.yaml` L249-252, L269-271, L291-293
**BEFORE** (3 blocks):
```yaml
        accessControlAllowOriginList:
          - "http://localhost:5000"
          - "http://localhost:5050"
          - "http://aria-web:5000"
```
**AFTER** (3 blocks):
```yaml
        accessControlAllowOriginList:
          - "CORS_ORIGIN_1"
          - "CORS_ORIGIN_2"
          - "CORS_ORIGIN_3"
```

### Fix 2: Update traefik-entrypoint.sh to perform substitution
**File:** `stacks/brain/traefik-entrypoint.sh`
**BEFORE:**
```bash
cp /etc/traefik/traefik-dynamic.template.yaml /etc/traefik/traefik-dynamic.yaml
```
**AFTER:**
```bash
sed -e "s|CORS_ORIGIN_1|${CORS_ORIGIN_1:-http://localhost:5000}|g" \
    -e "s|CORS_ORIGIN_2|${CORS_ORIGIN_2:-http://localhost:5050}|g" \
    -e "s|CORS_ORIGIN_3|${CORS_ORIGIN_3:-http://aria-web:5000}|g" \
    /etc/traefik/traefik-dynamic.template.yaml > /etc/traefik/traefik-dynamic.yaml
```

### Fix 3: Add CORS vars to .env.example
**File:** `stacks/brain/.env.example`
```env
# CORS allowed origins for Traefik
CORS_ORIGIN_1=http://localhost:5000
CORS_ORIGIN_2=http://localhost:5050
CORS_ORIGIN_3=http://aria-web:5000
```

### Fix 4: Pass CORS env vars to traefik service
**File:** `stacks/brain/docker-compose.yml` — add to traefik service environment:
```yaml
      CORS_ORIGIN_1: ${CORS_ORIGIN_1:-http://localhost:5000}
      CORS_ORIGIN_2: ${CORS_ORIGIN_2:-http://localhost:5050}
      CORS_ORIGIN_3: ${CORS_ORIGIN_3:-http://aria-web:5000}
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer architecture | ❌ | Infrastructure only |
| 2 | .env for secrets | ✅ | CORS origins configurable via .env |
| 3 | models.yaml | ❌ | No model changes |
| 4 | Docker-first testing | ✅ | Traefik config — Docker only |
| 5 | aria_memories writable | ❌ | No file writes |
| 6 | No soul modification | ❌ | No soul changes |

## Dependencies
None — can be done in parallel with S-01.

## Verification
```bash
# 1. Verify template has placeholders:
grep -c 'CORS_ORIGIN' stacks/brain/traefik-dynamic.template.yaml
# EXPECTED: 9 (3 blocks × 3 origins)

# 2. Verify entrypoint does sed substitution:
grep 'sed' stacks/brain/traefik-entrypoint.sh
# EXPECTED: sed command with CORS_ORIGIN substitution

# 3. Verify docker-compose passes CORS vars to traefik:
grep 'CORS_ORIGIN' stacks/brain/docker-compose.yml
# EXPECTED: 3 lines in traefik environment

# 4. Verify .env.example documents CORS vars:
grep 'CORS_ORIGIN' stacks/brain/.env.example
# EXPECTED: 3 variable definitions
```

## Prompt for Agent
```
Read these files first:
- stacks/brain/traefik-dynamic.template.yaml (full — 340 lines)
- stacks/brain/traefik-entrypoint.sh (full — ~20 lines)
- stacks/brain/docker-compose.yml (traefik service section)
- stacks/brain/.env.example

CONSTRAINTS: #2 (env for config), #4 (Docker-first).

STEPS:
1. In traefik-dynamic.template.yaml: Replace all 3 blocks of hardcoded origins with CORS_ORIGIN_1/2/3 placeholders
2. In traefik-entrypoint.sh: Replace the cp command with a sed command that substitutes the placeholders with env vars (with defaults)
3. In docker-compose.yml: Add CORS_ORIGIN_1/2/3 to traefik service environment section
4. In .env.example: Add CORS_ORIGIN_1/2/3 with sensible defaults
5. Do NOT modify traefik-dynamic.yaml (generated file)
6. Run verification commands
```
