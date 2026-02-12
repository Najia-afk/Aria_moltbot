# S4-07: Document Production Runbook
**Epic:** Sprint 4 — Reliability & Self-Healing | **Priority:** P1 | **Points:** 2 | **Phase:** 4

## Problem
There is no centralized operational runbook. When something goes wrong at 2am, Shiva has to:
- Remember which containers to restart
- Remember the correct docker compose paths
- Figure out which logs to check
- Remember how to roll back changes

Critical operational knowledge lives in Shiva's head, scattered across CHANGELOG, README, and Slack messages.

## Root Cause
Project grew organically from prototype to production without an ops documentation phase.

## Fix
Create `docs/RUNBOOK.md` covering:

```markdown
# Aria Production Runbook

## Quick Reference
| Action | Command |
|--------|---------|
| Check all containers | `docker ps --format "table {{.Names}}\t{{.Status}}"` |
| Restart API | `docker compose restart aria-api` |
| Restart all | `docker compose down && docker compose up -d` |
| Check API health | `curl http://localhost:8000/health` |
| Check logs | `docker logs aria-api --tail 50` |
| Run tests | `python -m pytest tests/ -q` |
| Architecture check | `python scripts/check_architecture.py` |
| Verify deployment | `./scripts/verify_deployment.sh` |

## Architecture Overview
[diagram of 5-layer stack]

## Container Map
| Container | Port | Purpose | Health Check |
|-----------|------|---------|-------------|
| aria-db | 5432 | PostgreSQL 16 + pgvector | pg_isready |
| aria-api | 8000 | FastAPI REST/GraphQL | /health |
| aria-web | 5000 | Flask Dashboard | / returns 200 |
| aria-brain | - | Aria Core Agent | Internal |
| clawdbot | - | Node Discord/Telegram | Internal |
| litellm | 4000 | LLM Proxy | /health |
| traefik | 80/443 | Reverse Proxy | Dashboard |
| tor-proxy | 9050 | Tor SOCKS Proxy | curl test |
| aria-browser | 3000 | Browserless Chrome | /json/version |

## Common Issues & Resolution

### API not responding
1. Check container: `docker ps | grep aria-api`
2. Check logs: `docker logs aria-api --tail 100`
3. Common causes: DB connection pool exhausted, OOM
4. Fix: `docker compose restart aria-api`
5. If persists: `docker compose down aria-api && docker compose up -d aria-api`

### Database issues
1. Check: `docker exec aria-db pg_isready`
2. Connection pool: Check active connections
3. Migration: `docker exec aria-api alembic upgrade head`
4. Backup: `docker exec aria-db pg_dump -U aria aria > backup.sql`

### Frontend shows stale data
1. Force rebuild: `docker compose build aria-web --no-cache`
2. Or: `docker compose restart aria-web`

### Ollama not responding
1. Check: `curl http://localhost:11434/api/tags`
2. Ollama runs NATIVE on Mac (not Docker)
3. Restart: `ollama serve` (or reboot)

## Rollback Procedures
1. Find last good state: `git log --oneline -10`
2. Rollback code: `git checkout <commit>`
3. Rebuild: `docker compose build && docker compose up -d`
4. Verify: `./scripts/verify_deployment.sh`

## Monitoring
- Health watchdog: `scripts/health_watchdog.sh` (cron every 5m)
- Architecture: `scripts/check_architecture.py`
- Logs: `aria_memories/logs/`

## Cron Jobs
Reference: `aria_mind/cron_jobs.yaml`
- Cron runs INSIDE aria-brain container
- Edit cron: modify cron_jobs.yaml → rebuild aria-brain

## Emergency Contacts
- Server: Mac Mini M4 (SSH via VSCode)
- Backup: [add backup location]
- Owner: Najia (Shiva)
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ✅ | Document the architecture |
| 2 | .env secrets | ✅ | Do NOT include any .env values in the runbook |
| 3 | models.yaml SSOT | ❌ | Documentation only |
| 4 | Docker-first | ✅ | All commands reference Docker |
| 5 | aria_memories writable | ❌ | docs/ directory |
| 6 | No soul modification | ❌ | Not touching soul |

## Dependencies
S4-01 (patch script), S4-02 (watchdog), S4-04 (verify script) should be referenced.

## Verification
```bash
# 1. Runbook exists:
ls docs/RUNBOOK.md
# EXPECTED: file exists

# 2. Contains all sections:
for section in "Quick Reference" "Container Map" "Common Issues" "Rollback" "Monitoring" "Cron Jobs"; do
  grep -c "$section" docs/RUNBOOK.md > /dev/null && echo "✅ $section" || echo "❌ $section missing"
done
# EXPECTED: all ✅

# 3. No secrets in runbook:
grep -i "password\|secret\|token\|api.key" docs/RUNBOOK.md | grep -v "placeholder\|example\|.env" | wc -l
# EXPECTED: 0

# 4. All referenced scripts exist:
for script in verify_deployment.sh health_watchdog.sh apply_patch.sh check_architecture.py; do
  ls "scripts/$script" 2>/dev/null && echo "✅ $script" || echo "❌ $script missing"
done
```

## Prompt for Agent
```
Create a comprehensive production runbook for Aria.

**Files to read:**
- stacks/brain/docker-compose.yml (container details, ports, health checks)
- aria_mind/cron_jobs.yaml (cron job reference)
- scripts/ (list all scripts to reference)
- Makefile (existing automation targets)
- STRUCTURE.md (architecture overview)
- README.md (project overview)
- CHANGELOG.md (recent changes for context)

**Steps:**
1. Create docs/RUNBOOK.md
2. Include: quick reference table, container map, common issues guide
3. Include: rollback procedures, monitoring setup, cron reference
4. Verify no secrets are included
5. Cross-reference all scripts from S4-01, S4-02, S4-04
6. Keep it practical — commands that can be copy-pasted
```
