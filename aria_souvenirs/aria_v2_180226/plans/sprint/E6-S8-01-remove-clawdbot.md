# S8-01: Remove Clawdbot Service from Docker Compose
**Epic:** E6 — OpenClaw Removal | **Priority:** P0 | **Points:** 1 | **Phase:** 8

## Problem
The `clawdbot` service block (lines 42–136) in `stacks/brain/docker-compose.yml` runs a Node.js OpenClaw gateway that is fully replaced by the Aria engine. The service, its volumes, and its dependent configs must be removed.

## Root Cause
OpenClaw was the original chat gateway. The engine now handles chat, cron, and tool execution natively. The clawdbot container consumes 1 GB RAM and a full CPU core for functionality that no longer exists.

## Fix

### 1. Remove from `stacks/brain/docker-compose.yml`

**Remove the entire `clawdbot:` service block (lines 42–136):**

```yaml
# DELETE THIS ENTIRE BLOCK (approximately lines 42-136):

  # Clawdbot Gateway - AI Assistant Control UI
  # Uses LiteLLM as backend to route to local Ollama (qwen3-vl) or cloud models
  # Mounts aria_mind/ as workspace with aria_skills/, aria_agents/ for Python skill execution
  clawdbot:
    image: node:22-bookworm
    container_name: clawdbot
    restart: unless-stopped
    working_dir: /root
    environment:
      NODE_OPTIONS: "--max-old-space-size=1024"
      OPENCLAW_VERSION: "2026.2.6-3"
      OPENCLAW_CONFIG_PATH: "/root/.openclaw/openclaw.json"
      OPENCLAW_WORKSPACE: "/root/.openclaw/workspace"
      OPENCLAW_GATEWAY_PORT: "18789"
      OPENCLAW_GATEWAY_TOKEN: ${CLAWDBOT_TOKEN:-default-clawdbot-token}
      OPENCLAW_NO_ONBOARD: "1"
      OPENCLAW_NO_PROMPT: "1"
      OPENCLAW_SYSTEM_PROMPT_FILE: "/root/.openclaw/system_prompt.txt"
      BROWSER_CDP_URL: http://aria-browser:3000
      LITELLM_MASTER_KEY: ${LITELLM_MASTER_KEY:-sk-change-me}
      MOONSHOT_KIMI_KEY: ${MOONSHOT_KIMI_KEY:-}
      DATABASE_URL: postgresql://${DB_USER:-admin}:${DB_PASSWORD:-admin}@aria-db:5432/${DB_NAME:-aria_warehouse}
      OLLAMA_URL: http://host.docker.internal:11434
      OLLAMA_MODEL: hf.co/unsloth/GLM-4.7-Flash-REAP-23B-A3B-GGUF:Q3_K_S
      MOLTBOOK_TOKEN: ${MOLTBOOK_TOKEN:-}
      MOLTBOOK_API_KEY: ${MOLTBOOK_TOKEN:-}
      MOLTBOOK_API_URL: ${MOLTBOOK_API_URL:-https://www.moltbook.com/api/v1}
      TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN:-}
      TELEGRAM_CHAT_ID: ${TELEGRAM_CHAT_ID:-}
      X_API_KEY: ${X_API_KEY:-}
      X_API_SECRET: ${X_API_SECRET:-}
      X_ACCESS_TOKEN: ${X_ACCESS_TOKEN:-}
      X_ACCESS_SECRET: ${X_ACCESS_SECRET:-}
      MOLT_CHURCH_API_KEY: ${MOLT_CHURCH_API_KEY:-}
      MOLT_CHURCH_URL: ${MOLT_CHURCH_URL:-https://molt.church}
      MOLT_CHURCH_AGENT: ${MOLT_CHURCH_AGENT:-Aria}
      ARIA_API_URL: http://aria-api:8000
      PYTHONPATH: /root/repo:/root/.openclaw/workspace/skills:/root/.openclaw/workspace
    volumes:
      - openclaw_data:/root/.openclaw
      - ../../:/root/repo:ro
      - ../../aria_mind:/root/.openclaw/workspace
      - ../../aria_memories:/root/.openclaw/aria_memories
      - ../../aria_souvenirs:/root/.openclaw/aria_souvenirs:ro
      - ../../aria_skills:/root/.openclaw/workspace/skills/aria_skills:ro
      - ../../aria_agents:/root/.openclaw/workspace/skills/aria_agents:ro
      - ../../aria_models:/root/.openclaw/workspace/aria_models:ro
      - ../../skills:/root/.openclaw/workspace/skills/legacy:ro
      - ../../patch:/root/.openclaw/patches:ro
      - ../../tests:/root/.openclaw/workspace/tests:ro
      - ../../pyproject.toml:/root/.openclaw/workspace/pyproject.toml:ro
      - ./openclaw-entrypoint.sh:/openclaw-entrypoint.sh:ro
      - ./openclaw-config.json:/root/.openclaw/openclaw-config-template.json:ro
      - ./openclaw-auth-profiles.json:/root/.openclaw/auth-profiles-template.json:ro
      - ../../prompts/system_prompt.txt:/root/.openclaw/system_prompt.txt:ro
    ports:
      - "18789:18789"
    depends_on:
      aria-db:
        condition: service_healthy
      litellm:
        condition: service_started
    command: ["bash", "/openclaw-entrypoint.sh"]
    networks:
      - aria-net
    mem_limit: ${CLAWDBOT_MEM_LIMIT:-1g}
    cpus: ${CLAWDBOT_CPU_LIMIT:-1.0}
    extra_hosts:
      - "host.docker.internal:host-gateway"
```

**Remove `openclaw_data` volume declaration (at bottom of file):**

```yaml
# In the volumes: section, REMOVE this line:
  openclaw_data:
```

**Remove any `openclaw_data` mount in other services (line ~464):**

```yaml
# In aria-api or other services, REMOVE any line like:
      - openclaw_data:/openclaw:ro
```

**Remove `CLAWDBOT_TOKEN` references from other services.**

Search for services that pass `CLAWDBOT_TOKEN` and remove those env vars:

```yaml
# In aria-api environment, REMOVE:
      CLAWDBOT_TOKEN: ${CLAWDBOT_TOKEN:-default-clawdbot-token}
```

**Remove `depends_on: clawdbot` from any service that had it.**

### 2. Updated docker-compose.yml services section (after removal)

The services list should go from:
```
aria-db → clawdbot → tor-proxy → ...
```
To:
```
aria-db → tor-proxy → ...
```

No other service depends on clawdbot, so no dependency chain breaks.

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ❌ | Infrastructure only |
| 2 | .env for secrets (zero in code) | ✅ | Remove CLAWDBOT_TOKEN from .env.example |
| 3 | models.yaml single source of truth | ❌ | N/A |
| 4 | Docker-first testing | ✅ | Test with `docker compose config` |
| 5 | aria_memories only writable path | ❌ | N/A |
| 6 | No soul modification | ❌ | N/A |

## Dependencies
- S6-06 (Remove OpenClaw proxy from Flask — no more /clawdbot/ route)
- S8-02 (Delete OpenClaw config files — after service removed)
- All Sprint 6-7 UI tickets (engine pages must be running before removing clawdbot)

## Verification
```bash
# 1. Docker compose validates:
cd stacks/brain && docker compose config > /dev/null && echo "VALID"
# EXPECTED: VALID

# 2. No clawdbot service:
docker compose config --services | grep -c clawdbot
# EXPECTED: 0

# 3. No openclaw_data volume:
docker compose config | grep -c openclaw_data
# EXPECTED: 0

# 4. No CLAWDBOT references:
grep -rci "clawdbot\|CLAWDBOT" docker-compose.yml
# EXPECTED: 0

# 5. Other services still start:
docker compose up -d aria-db litellm aria-api aria-web
docker compose ps --format "table {{.Name}}\t{{.Status}}" | grep -c "Up"
# EXPECTED: 4
```

## Prompt for Agent
```
Remove the clawdbot service from the Docker Compose stack.

FILES TO READ FIRST:
- stacks/brain/docker-compose.yml (full file — find clawdbot block and all references)
- stacks/brain/.env.example (CLAWDBOT_* vars to remove)

STEPS:
1. Delete the entire clawdbot service block (~lines 42-136)
2. Delete the openclaw_data volume declaration from the volumes: section
3. Remove any openclaw_data:/openclaw mount from other services (e.g., aria-api)
4. Remove CLAWDBOT_TOKEN references from other service environment blocks
5. Remove port 18789 from any port mappings
6. Remove CLAWDBOT_* from .env.example
7. Validate with `docker compose config`

SAFETY:
- Run `docker compose config --services` before and after to confirm only clawdbot was removed
- No other service depends_on clawdbot (verified in context)
- The openclaw_data volume can be pruned later with `docker volume rm`
```
