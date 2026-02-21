# Aria v2 Final Review Sprint — 2026-02-12

> **Product Owner:** Najia (Shiva) | **Sprint Agent:** Claude Opus 4.6
> **Created:** 2026-02-12 | **Environment:** Mac Mini M4 (Production via SSH)
> **Previous Session:** aria_v2_110226 (7 sprints, 74 tickets, ~257 points)

---

## Executive Summary

**4 sprints, 32 tickets, ~98 story points** — Final hardening pass.

Yesterday's 7-sprint marathon (Sprints 1–7) delivered massive improvements: frontend fixes, pagination, sprint board, knowledge graph, pgvector semantic memory, endpoint stabilization, dashboard data fixes, and direct LiteLLM DB queries. Today's session is the **final review and hardening** — making sure every puzzle piece fits perfectly.

### Sprint Organization

| Sprint | Theme | Tickets | Points | Risk | Focus |
|--------|-------|---------|--------|------|-------|
| **Sprint 1** | Critical Bugs & Python Compat | 8 | ~22 | Low | Fix test suite, Python 3.9 compat, 404 endpoints, console.log cleanup |
| **Sprint 2** | Cron & Token Optimization | 8 | ~24 | Medium | Merge redundant crons, model routing optimization, cost tracking |
| **Sprint 3** | Frontend Deduplication & Polish | 8 | ~28 | Medium | Extract 13 duplicate JS functions, shared components, XSS audit |
| **Sprint 4** | Reliability & Self-Healing | 8 | ~24 | Medium | Error recovery, health automation, patching infrastructure, test coverage |

**Total: 32 tickets, ~98 points, estimated 24-36 hours**

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

## Production State Assessment (Pre-Sprint)

### Healthy (Confirmed 2026-02-12)
- All 9 Docker containers UP (17h+ uptime)
- API v3.0.0: `{"status":"healthy","database":"connected"}`
- All 15 frontend pages return HTTP 200
- Architecture checker: **0 errors**, 13 JS warnings
- No SQLAlchemy imports in skills (clean)
- No hardcoded model names (clean)
- No secrets in code (clean)

### Issues Found
| Issue | Severity | Sprint | Ticket |
|-------|----------|--------|--------|
| Tests broken — Python 3.10 syntax on 3.9 server | P0 | 1 | S1-01 |
| `console.log` in knowledge.html, sprint_board.html | P1 | 1 | S1-02 |
| 3 API 404s (route name mismatches) | P1 | 1 | S1-03 |
| 13 duplicate JS functions across templates | P2 | 3 | S3-01..S3-06 |
| work_cycle + memory_sync both 15m (merge opportunity) | P1 | 2 | S2-01 |
| Cron hourly_health_check still hourly (should be 6h per patch) | P1 | 2 | S2-02 |
| No automated patch deployment script | P1 | 4 | S4-01 |
| Test coverage thin — no endpoint integration tests running | P0 | 4 | S4-05 |

---

## Sprint 1 — Critical Bugs & Python Compatibility

**Phase:** 1 — Fix | **Tickets:** 8 | **Points:** ~22 | **Risk:** Low
**Focus:** Fix the test suite (Python 3.9 compat), eliminate 404 endpoints, clean debug code, verify yesterday's sprint completion.

| # | Ticket | Priority | Pts | Description |
|---|--------|----------|-----|-------------|
| S1-01 | Upgrade host Python to 3.12+ | P0 | 5 | Host has 3.9.6, Docker has 3.13 — upgrade host, update pyproject.toml, leave modern syntax |
| S1-02 | Remove bare console.log | P1 | 1 | Gate behind `window.ARIA_DEBUG` in knowledge.html, sprint_board.html |
| S1-03 | Fix API route 404s | P1 | 3 | `/social/posts` → `/social`, `/security/reports` → `/security-events`, `/operations/income` route audit |
| S1-04 | Verify Sprint 7 completions | P0 | 3 | Re-test S7-01..S7-10 tickets from yesterday |
| S1-05 | Fix DOMContentLoaded patterns | P1 | 2 | Verify all 13 templates use arrow function wrappers (S7-01 fix) |
| S1-06 | Verify pgvector & semantic memory | P0 | 3 | Confirm S5-01/S6-01 pgvector working, test semantic endpoints |
| S1-07 | Verify knowledge graph sync | P1 | 3 | Confirm S4-01/S4-07 auto-sync on startup, test graph endpoints |
| S1-08 | Run full test suite & fix failures | P0 | 5 | After S1-01 fix, run `pytest tests/ -q` — fix any remaining failures |

**Dependency:** S1-01 first (unblocks S1-08). S1-04..S1-07 parallel. S1-08 last.

---

## Sprint 2 — Cron & Token Optimization

**Phase:** 2 — Optimize | **Tickets:** 8 | **Points:** ~24 | **Risk:** Medium
**Focus:** Merge redundant crons, implement Aria's own token waste recommendations, cost tracking dashboard integration.

| # | Ticket | Priority | Pts | Description |
|---|--------|----------|-----|-------------|
| S2-01 | Merge work_cycle + memory_sync | P0 | 3 | Both run every 15m — combine into single job with memory sync as final step |
| S2-02 | Verify cron patch persistence | P0 | 2 | Confirm exploration_pulse 2h, hourly_health → 6h patches survived container restart |
| S2-03 | Add cron cost tracking | P1 | 5 | Log token spend per cron job to activities table for spend-per-job dashboarding |
| S2-04 | YAML-driven model routing + bypass | P1 | 5 | Add `routing.bypass` config flag, `tier_order`, zero hardcoded model names in Python |
| S2-05 | Fix social_post cron delivery | P1 | 2 | Currently saves drafts — verify platform routing works end-to-end |
| S2-06 | Validate six_hour_review cooldown | P1 | 2 | Cooldown check may race — verify with activity log timestamps |
| S2-07 | Optimize nightly_tests cron | P2 | 2 | Currently runs pytest via Aria (expensive) — switch to direct execution |
| S2-08 | Verify & document all cron jobs | P0 | 3 | Full cron audit with expected vs actual behavior table |

**Dependency:** S2-01/S2-02 first (cron stability). S2-03..S2-07 parallel. S2-08 last.

---

## Sprint 3 — Frontend Deduplication & Polish

**Phase:** 3 — Consolidate | **Tickets:** 8 | **Points:** ~28 | **Risk:** Medium
**Focus:** Extract duplicate JS into shared modules, improve error handling consistency, XSS audit.

| # | Ticket | Priority | Pts | Description |
|---|--------|----------|-----|-------------|
| S3-01 | Extract shared utility functions | P0 | 5 | `escapeHtml`, `formatTime`, `showToast`, `closeModal` → utils.js |
| S3-02 | Extract shared chart helpers | P1 | 5 | `renderChart`, `renderOverview`, `drawGraph` → chart-helpers.js |
| S3-03 | Extract shared data loaders | P1 | 5 | `loadStats`, `loadAll`, `loadBalances`, `updateStats` → data-loaders.js |
| S3-04 | Consolidate renderGoalCard | P1 | 3 | sprint_board.html + goals.html share same function — extract to goals-common.js |
| S3-05 | Add fetchWithRetry wrapper | P1 | 3 | Standardize error handling across all fetch calls with retry + timeout |
| S3-06 | XSS audit — innerHTML usage | P0 | 3 | Audit all innerHTML assignments for unescaped user data |
| S3-07 | Add ARIA_DEBUG flag globally | P2 | 2 | Single flag controls all debug logging across all templates |
| S3-08 | Verify & test Sprint 3 | P0 | 2 | All pages load, no JS errors in console, functions work correctly |

**Dependency:** S3-01 first (other tickets reference utils.js). S3-02..S3-06 parallel. S3-07 after S3-01. S3-08 last.

---

## Sprint 4 — Reliability & Self-Healing

**Phase:** 4 — Harden | **Tickets:** 8 | **Points:** ~24 | **Risk:** Medium
**Focus:** Automated patching, error recovery, health automation, test infrastructure, production resilience.

| # | Ticket | Priority | Pts | Description |
|---|--------|----------|-----|-------------|
| S4-01 | Create automated patch script | P0 | 5 | `scripts/apply_patch.sh` — atomic file replacement + container reload + rollback |
| S4-02 | Add health-based auto-restart | P1 | 3 | If health check fails 3× consecutive → auto-restart container + alert |
| S4-03 | Add error recovery to api_client | P1 | 3 | Retry with exponential backoff on 5xx, circuit breaker on repeated failures |
| S4-04 | Create deployment verification script | P0 | 3 | `scripts/verify_deployment.sh` — check all endpoints, all pages, all containers |
| S4-05 | Fix and expand test suite | P0 | 5 | Fix conftest.py, add missing endpoint tests, ensure `pytest` passes clean |
| S4-06 | Add pre-commit architecture check | P2 | 2 | Run `check_architecture.py` as git pre-commit hook |
| S4-07 | Document production runbook | P1 | 2 | `docs/RUNBOOK.md` — restart procedures, rollback, monitoring, alerts |
| S4-08 | Final verification pass | P0 | 1 | All sprints verified, all tests pass, all endpoints healthy |

**Dependency:** S4-01..S4-04 parallel. S4-05 standalone. S4-06/S4-07 standalone. S4-08 last (depends on all).

---

## Global Dependency Map

```
Sprint 1 (Fix Critical) → Sprint 2 (Optimize Crons) → Sprint 3 (Frontend Polish) → Sprint 4 (Harden/Ship)
```

Sprint 1 is prerequisite — tests must pass before optimization work.
Sprints 2 and 3 can run in parallel (backend vs frontend focus).
Sprint 4 is the final gate.

---

## Estimated Effort

| Sprint | Tickets | Points | Est. Hours | Risk |
|--------|---------|--------|------------|------|
| Sprint 1 | 8 | ~22 | 4-6h | Low |
| Sprint 2 | 8 | ~24 | 6-8h | Medium |
| Sprint 3 | 8 | ~28 | 6-10h | Medium |
| Sprint 4 | 8 | ~24 | 4-6h | Medium |
| **Total** | **32** | **~98** | **20-30h** | |

---

## Key Architecture Notes for Agents

### 5-Layer Rule (CRITICAL)
```
Layer 1: PostgreSQL DB (36+ tables)
Layer 2: SQLAlchemy ORM (src/api/db/models.py — 684 lines, 20+ classes)
Layer 3: FastAPI API (src/api/routers/ — 21 routers)
Layer 4: api_client (aria_skills/api_client/ — httpx client)
Layer 5: Skills + ARIA Mind/Agents
```

**Skills NEVER import SQLAlchemy. Skills ALWAYS go through api_client → API.**

### Critical Files
| File | Lines | Purpose |
|------|-------|---------|
| src/api/db/models.py | 684 | All ORM models |
| src/api/main.py | 258 | FastAPI app + lifespan |
| src/api/routers/ | 21 files | All REST endpoints |
| aria_skills/api_client/__init__.py | 1013+ | Centralized HTTP client |
| aria_mind/cron_jobs.yaml | ~150 | Cron job definitions |
| aria_models/models.yaml | 324 | Model routing SSOT |
| src/web/static/js/ | 4 files | Shared JS (aria-common, pagination, pricing, utils) |
| stacks/brain/docker-compose.yml | 480 | Docker orchestration |

### Production Environment
- **Server:** Mac Mini M4, macOS, SSH via VSCode
- **Python:** Host is 3.9.6 (system) — **S1-01 upgrades to 3.12+**. Docker already 3.13. Modern syntax (`X | None`) is correct, do NOT downgrade
- **Docker:** 9 containers running (aria-db, aria-api, aria-web, aria-brain, clawdbot, litellm, traefik, tor-proxy, aria-browser)
- **Ollama:** Native on macOS (Metal GPU) at `host.docker.internal:11434`

---

## Session Completion Criteria

Before marking this session as complete:
- [ ] All 32 tickets executed or documented as deferred
- [ ] `pytest tests/ -q` passes with 0 failures
- [ ] All API endpoints return valid responses
- [ ] All frontend pages load without JS errors
- [ ] Architecture checker: 0 errors
- [ ] `tasks/lessons.md` updated with new patterns
- [ ] Deployment verification script passes
