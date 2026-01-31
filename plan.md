# Aria Rebuild Plan (Traefik + FastAPI + aria_warehouse)

## Phase 0 — Preflight & Baseline
- [x] Snapshot current state (containers, volumes, configs) to allow rollback.
- [x] Confirm Mac Docker resources (RAM/CPU) are sufficient and document target allocations.
- [x] Identify all hardcoded secrets/defaults; map to .env variables only.

## Phase 1 — Configuration & Secrets Hygiene
- [x] Remove hardcoded secrets from:
  - [x] stacks/brain/docker-compose.yml
  - [x] src/web/app.py
  - [x] src/web/config.py
  - [x] scripts/*
  - [x] deploy/*
- [x] Ensure all credentials are required via .env (no defaults).
- [x] Standardize env naming across stack and code (DB, OpenClaw token, LLM keys).

## Phase 2 — Database Standardization (aria_warehouse)
- [x] Standardize DB name/user to aria_warehouse in:
  - [x] stacks/brain/docker-compose.yml
  - [x] scripts/*
  - [x] deploy/*
- [x] Update init/import scripts to load legacy Aria data into aria_warehouse schema.
- [x] Ensure schema is created via API on startup (SQLAlchemy models, no manual SQL).
- [x] Validate schema matches Bubble/Mission7 patterns for journaling/logging.

## Phase 3 — API Consolidation (FastAPI owns data routes)
- [x] Move /api/* routes from Flask to FastAPI:
  - [x] Migrate endpoints from src/web/app.py to src/api/*.
  - [x] Ensure all DB access occurs via API endpoints only.
- [x] Restrict Flask to UI templates only (no direct DB access).
- [x] Update UI to call FastAPI endpoints.
- [x] API auto-creates tables + indexes on startup.

## Phase 4 — Traefik-Only HTTPS
- [x] Remove Nginx from the stack; re-enable Traefik service.
- [x] Implement Traefik routers/services for:
  - [x] Portal (Flask UI)
  - [x] FastAPI (/api)
  - [x] OpenClaw/Clawdbot
  - [x] Grafana, Prometheus, PgAdmin, Ollama
- [x] Self-signed TLS:
  - [x] Auto-generate certs on first run.
  - [x] Mount certs into Traefik.
  - [x] Ensure HTTPS works from local LAN.

## Phase 5 — OpenClaw (Docker-only)
- [x] Ensure OpenClaw gateway runs only in Docker (no Mac-native service).
- [x] Wire OpenClaw URL/token via .env only.
- [x] Verify gateway health + HTTPS routing via Traefik.

## Phase 6 — Aria Brain + Skills + Cron
- [x] Verify Aria brain container starts with correct env.
- [x] Confirm SOUL files and skill definitions are loaded.
- [x] Ensure scheduler/cron loop is active and uses API endpoints.
- [x] Confirm Aria can learn new skills and persist to warehouse.
- [x] Validate HEARTBEAT.md tasks parse correctly in OpenClaw workspace.

## Phase 7 — End-to-End Fresh Install Test
- [x] Simulate fresh clone + docker compose up on Mac:
  - [x] Clean/prune volumes.
  - [x] Apply .env.
  - [x] Compose up all services.
- [x] Validate service health checks.
- [x] Validate HTTPS access to portal and OpenClaw.
- [x] Validate Aria chat works by default.
- [x] Validate data logging + retrieval via API.
- [x] One-click deploy script works end-to-end (no manual DB commands).

## Phase 8 — Documentation & Handoff
- [x] Update README/ops docs with exact steps.
- [x] Record .env schema (no values).
- [x] Provide checklist for future redeploys.

## Phase 9 — OpenClaw Workspace Alignment
- [x] Mount aria_mind as OpenClaw workspace in clawdbot container.
- [x] Align AGENTS.md workspace path to container mount.
- [x] Validate OpenClaw TUI chat + agent routing using mounted workspace.

---

### Subagent Tasks (if needed)
- [x] Audit API surface alignment (FastAPI vs Flask).
- [x] Review SOUL/skills/cron integration.
- [x] Verify DB schema imports from legacy Aria data.
