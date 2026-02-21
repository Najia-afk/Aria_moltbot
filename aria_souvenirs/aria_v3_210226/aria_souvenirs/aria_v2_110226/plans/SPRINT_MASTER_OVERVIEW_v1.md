# Aria v2 Sprint Master Overview — 2026-02-11

> **Product Owner:** Najia (Shiva) | **Sprint Agent:** Claude 4.6  
> **Created:** 2026-02-11 | **Environment:** Mac Mini M4 (Production)

---

## Current State Summary

### System Health
| Service | Status | Notes |
|---------|--------|-------|
| PostgreSQL 16 | ✅ Healthy | 36 tables, 2177 activities, 53 goals |
| aria-api (FastAPI) | ✅ Healthy | 18 routers, port 8000 |
| aria-web (Flask) | ✅ Running | 24 templates, port 5000 |
| aria-brain | ✅ Healthy | Heartbeat beat 958 |
| LiteLLM | ⚠️ Degraded | Frontend hangs on large spend JSON |
| MLX Server | ❌ Unknown | qwen3-mlx connection errors |
| Traefik | ✅ Running | HTTPS + path routing |
| aria-browser | ✅ Healthy | Browserless Chrome |
| 10 containers total | Running 17h+ | |

### Git State
- **Branch:** main (ahead of origin by 2 unpushed commits)
- **Authors:** Aria + Najia-afk
- **Last 5 commits:** +10,845 / -4,690 lines across 213 files
- **Untracked files:** 11 files (knowledge patches, research, moltbook drafts)

### DB Garbage
- 3× "Test Goal" at 0% (garbage)
- 2× "Learn Python" duplicates
- 2× "Live test goal" duplicates
- 2× "Patchable" at 0% (garbage)
- 14 zero-progress goals out of 25 non-completed
- 28 completed, 13 active, 10 pending, 2 in_progress

### Known Bugs (from audit + memories)
| # | Severity | Issue | Source |
|---|----------|-------|--------|
| 1 | 🔴 HIGH | Double token counting in Usage by Model chart (triple-counting total_tokens) | models.html L1083 |
| 2 | 🔴 HIGH | Pricing inconsistency: table uses `log.spend`, charts use `calculateLogCost()` | models.html L878 vs L723 |
| 3 | 🔴 HIGH | LiteLLM spend endpoint returns 5-10MB JSON, frontend hangs | litellm router + templates |
| 4 | 🟡 MED | ~400 lines duplicate JS between models.html and wallets.html | models.html + wallets.html |
| 5 | 🟡 MED | CNY_TO_USD hardcoded exchange rate (dead code, risk) | pricing.js L189 |
| 6 | 🟡 MED | Dashboard chart filter dropdown is cosmetic only (no handler) | dashboard.html L194-198 |
| 7 | 🟡 MED | Spend log duration always 0s for lite logs (endTime stripped) | models.html L881 |
| 8 | 🟡 MED | 3 redundant fetches of spend logs per page load | models.html + wallets.html |
| 9 | 🟡 MED | console.log debug statements in production (wallets.html) | wallets.html L636-862 |
| 10 | 🟡 MED | No auth on POST API endpoints (only admin routes protected) | all routers except admin |
| 11 | 🟡 MED | No CSRF protection on Flask reverse proxy | app.py L49-62 |
| 12 | 🟡 MED | qwen3-coder-free misconfigured in models.yaml | models.yaml |
| 13 | 🟡 MED | chimera-free returns 404 on tool calls | model config |
| 14 | 🟡 MED | services.html links to stale /litellm route | services.html L279 |
| 15 | 🟢 LOW | pyproject.toml version stuck at 1.0.0 | pyproject.toml |
| 16 | 🟢 LOW | Doc count inconsistencies (skills: 24/25/26/28, routers: 17/18, pages: 22/25) | README vs STRUCTURE |
| 17 | 🟢 LOW | Max sub-agents: ARIA.md says 8, everything else says 5 | ARIA.md |
| 18 | 🟢 LOW | f-string SQL in admin.py ANALYZE (safe but anti-pattern) | admin.py L208 |
| 19 | 🟢 LOW | `import os` potentially missing in input_guard | input_guard/__init__.py |

---

## Sprint Architecture

### 3 Sprints — Incremental Delivery

```
Sprint 1 (P0): Frontend Fixes & Bug Squashing
├── S1-01: Fix double token counting in charts
├── S1-02: Fix pricing inconsistency (spend vs calculateLogCost)
├── S1-03: Fix LiteLLM spend endpoint pagination
├── S1-04: Consolidate duplicate JS (models + wallets)
├── S1-05: Remove hardcoded CNY_TO_USD + dead code
├── S1-06: Fix dashboard chart filter
├── S1-07: Fix spend log duration for lite logs
├── S1-08: Deduplicate spend log fetches
├── S1-09: Remove console.log from production
├── S1-10: Fix model config (qwen3-coder-free + chimera-free)
├── S1-11: DB cleanup (garbage goals, duplicates)
├── S1-12: Fix stale /litellm link in services.html
└── S1-13: Git push + verify all fixes in Docker

Sprint 2 (P1): Doc Consolidation & Small Tweaks
├── S2-01: Reconcile doc count inconsistencies
├── S2-02: Bump pyproject.toml version to 1.2.0
├── S2-03: Fix max sub-agents inconsistency (ARIA.md: 8→5)
├── S2-04: Consolidate BOOTSTRAP.md + Setup_Guide.md
├── S2-05: Update ARIA_COMPLETE_REFERENCE.md (deprecated skills)
├── S2-06: Fix f-string SQL anti-pattern in admin.py
├── S2-07: Verify import os in input_guard
├── S2-08: Clean Bubble compliance docs (6→2 files)
├── S2-09: Update tasks/lessons.md with v2 patterns
└── S2-10: Archive processed aria_memories files

Sprint 3 (P2): Future Features & Architecture
├── S3-01: Add API authentication (JWT/token-based)
├── S3-02: Add CSRF protection to Flask proxy
├── S3-03: Move task_type_routing.py to proper package
├── S3-04: Implement model strategy enforcement
├── S3-05: Token budget enforcement per session type
├── S3-06: Meta-Agent orchestrator loop
├── S3-07: Pheromone scoring to database
├── S3-08: Explorer/Worker/Validator swarm pattern
├── S3-09: Context compression (>50k token summarization)
└── S3-10: OpenClaw phase-out gateway preparation
```

---

## Hard Constraints (ALL Sprints)

| # | Constraint | Rule |
|---|-----------|------|
| 1 | 5-Layer Architecture | DB → SQLAlchemy ORM → FastAPI API → api_client (httpx) → Skills → ARIA |
| 2 | Secrets in .env | ZERO secrets in code. Do NOT modify .env — only .env.example |
| 3 | models.yaml SSOT | Zero hardcoded model names in Python |
| 4 | Docker-first testing | ALL changes work in `docker compose up` before deploy |
| 5 | aria_memories writable | Only writable path for Aria |
| 6 | No soul modification | aria_mind/soul/ is immutable |

---

## Estimated Effort

| Sprint | Tickets | Est. Hours | Risk |
|--------|---------|------------|------|
| Sprint 1 | 13 | 8-12h | Low — all verified bugs with known fixes |
| Sprint 2 | 10 | 4-6h | Low — doc/config changes only |
| Sprint 3 | 10 | 16-24h | Medium — new architecture, needs design |
| **Total** | **33** | **28-42h** | |

---

## Execution Strategy

1. **Each sprint is autonomous** — copy the sprint prompt into a new Claude session
2. **Sprint 1 first** — derisks frontend, high user impact
3. **Sprint 2 after S1 verified** — doc cleanup, low risk
4. **Sprint 3 designed separately** — needs architecture review before execution
5. **Each ticket has a self-contained agent prompt** — one subagent per ticket
6. **Test locally in Docker** before marking done
7. **Update tasks/lessons.md** after each sprint
