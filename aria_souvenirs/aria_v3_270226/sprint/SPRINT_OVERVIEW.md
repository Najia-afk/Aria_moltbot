# Aria v3 Sprint — 2026-02-27
## Sprint Overview

**Sprint Goal:** End-to-end test coverage, full visualization & graph execution capabilities for all memory types, chat tool execution DAG, unified search, navigation consolidation, and work-cycle/session artifact integrity guardrails.

**Total Tickets:** 13 | **Total Points:** 60 | **Estimated:** ~49 hours

**Audit Sources:**
- Visualization & graph capability discovery (44 templates, 32 API routers)
- Expert subagent: Architecture compliance (3 review passes)
- Expert subagent: UX & Docker port audit

---

## Epics

| Epic | Name | Tickets | Points |
|---|---|---|---|
| **E17** | **Testing** | **S-30** | **3** |
| **E18** | **Visualization & Graph Execution** | **S-31, S-32, S-33, S-34, S-35, S-36, S-37, S-38** | **44** |
| **E19** | **Session & Artifact Integrity** | **S-39, S-40, S-41, S-42** | **13** |

---

## Phase Breakdown

### Phase 1 (P1 — Should Have) — 36 pts
| Ticket | Title | Pts | Epic |
|--------|-------|-----|------|
| S-31 | Memory Graph (vis-network all memory types) | 8 | E18 |
| S-34 | Chat Tool Execution Graph (LangGraph DAG) | 8 | E18 |
| S-37 | Unified Memory Search (cross-type) | 5 | E18 |
| S-38 | Navigation Update (all viz pages) | 2 | E18 |
| S-39 | Work-Cycle Log Integrity Guardrails | 5 | E19 |
| S-40 | Artifact Path Resolution for Sub-Agents | 3 | E19 |
| S-41 | Schedule create_job Arg Compatibility | 3 | E19 |
| S-42 | Heartbeat Payload Contract Hardening | 2 | E19 |

### Phase 2 (P2 — Nice to Have) — 24 pts
| Ticket | Title | Pts | Epic |
|--------|-------|-----|------|
| S-30 | Load tests + E2E tests | 3 | E17 |
| S-32 | Memory Timeline & Heatmap (Chart.js) | 5 | E18 |
| S-33 | Embedding Cluster Explorer (PCA/t-SNE) | 8 | E18 |
| S-35 | Memory Consolidation Dashboard | 5 | E18 |
| S-36 | Lessons Learned Dashboard | 3 | E18 |

---

## Dependency Graph

```
E17 — Testing:
  S-30 (load tests + E2E) — independent, can run anytime

E18 — Visualization (all feed into nav update):
  S-31 (memory graph) ──┐
  S-32 (timeline)  ─────┤
  S-33 (embeddings) ────┼──→ S-38 (nav update — all routes must exist)
  S-34 (chat DAG) ──────┤
  S-35 (consolidation) ─┤
  S-36 (lessons) ───────┤
  S-37 (unified search) ┘

E19 — Session & Artifact Integrity:
  S-39 (work-cycle log integrity guardrails) — independent, recommended before dashboard-heavy reporting work
  S-40 (artifact path resolution + docs/test hardening) — run with or immediately after S-39
  S-41 (schedule arg compatibility) — unblock recurring scheduler tool calls
  S-42 (heartbeat contract hardening) — remove recurring 422 noise and improve health telemetry
```

---

## Ticket Summary

### E17 — Testing (3 pts)
| Ticket | File | Description |
|--------|-------|-------------|
| [S-30](S-30-load-tests-e2e.md) | `tests/load/`, `tests/e2e/`, `.github/workflows/` | Locust load tests, Playwright E2E, CI pipeline |

### E18 — Visualization & Graph Execution (44 pts)
| Ticket | File | Description |
|--------|-------|-------------|
| [S-31](S-31-memory-graph-visualization.md) | `memories.py`, `memory_graph.html`, `app.py` | vis-network graph of all memory types with category/source edges | ✅ Done |
| [S-32](S-32-memory-timeline-heatmap.md) | `memories.py`, `memory_timeline.html`, `app.py` | Chart.js temporal heatmap, stacked area, TTL decay bars |
| [S-33](S-33-embedding-cluster-explorer.md) | `memories.py`, `embedding_explorer.html`, `app.py` | PCA/t-SNE 2D scatter plot of semantic memory embeddings |
| [S-34](S-34-chat-tool-execution-graph.md) | `streaming.py`, `engine_chat.html` | LangGraph-style DAG for tool execution pipeline in chat UI |
| [S-35](S-35-memory-consolidation-dashboard.md) | `memories.py`, `memory_consolidation.html`, `app.py` | Surface→Medium→Deep flow, compression stats, promotion candidates |
| [S-36](S-36-lessons-learned-dashboard.md) | `lessons.py`, `lessons.html`, `app.py` | Skill→Error→Lesson vis-network graph, effectiveness charts |
| [S-37](S-37-unified-memory-search.md) | `memories.py`, `memory_search.html`, `app.py` | Cross-memory-type search (vector+ILIKE) with ranked results |
| [S-38](S-38-navigation-update-visualization.md) | `base.html` | Nav menu update — add all new visualization pages |

### E19 — Session & Artifact Integrity (13 pts)
| Ticket | File | Description |
|--------|-------|-------------|
| [S-39](S-39-work-cycle-log-integrity-guardrails.md) | `src/api/routers/artifacts.py`, `aria_skills/session_manager/__init__.py`, `aria_mind/cron_jobs.yaml`, `src/api/routers/goals.py` | Enforce artifact format checks, canonical session stats source, structured work-cycle log output, and goal ordering consistency |
| [S-40](S-40-artifact-path-resolution-sub-agents.md) | `aria_skills/api_client/__init__.py`, `aria_mind/MEMORY.md`, `tests/test_artifacts_router.py` | Add artifact read-by-path helper and docs/tests to prevent false 404/empty conclusions for nested artifact paths |
| [S-41](S-41-schedule-create-job-arg-compatibility.md) | `aria_skills/schedule/__init__.py`, `tests/skills/test_schedule.py` | Accept and normalize extra job payload args (including `type`) to prevent runtime create_job failures |
| [S-42](S-42-heartbeat-payload-contract-hardening.md) | `src/api/routers/operations.py`, `src/api/schemas/requests.py`, `tests/api/` | Harden heartbeat request validation/coercion and align endpoint contract to prevent `/api/heartbeat` 422 noise |

---

## Recommended Execution Order

```
Week 1: Visualization Sprint (E18) + Testing (E17)
  Day 1:   S-31 (memory graph — foundational, adds imports used by others)
  Day 2:   S-39 (log/session integrity guardrails before broad reporting)
  Day 3:   S-40 (artifact path resolution for sub-agents) + S-41 (schedule arg compatibility)
  Day 4:   S-42 (heartbeat contract hardening) + S-34 (chat DAG)
  Day 5:   S-33 (embedding explorer) + S-35 (consolidation dashboard)
  Day 6:   S-38 (nav update — all routes must exist first) + S-30 (load tests + E2E)
```

---

## E18 Design System Requirements

All E18 visualization tickets **MUST** follow these shared standards:

### Architecture Rules (MANDATORY)

**1. No direct SQL** — All DB access through SQLAlchemy ORM (`select()`, `func.*`, `Column`, etc.). Never use `text()`, `raw()`, or string SQL.

**2. Env var fallback pattern (NEVER hardcode)** — All ports, URLs, and paths must follow the docker-compose convention:
```python
# Python — env var with fallback
import os
port = int(os.environ.get("API_INTERNAL_PORT", "8000"))
litellm_url = os.environ.get("LITELLM_URL", "http://litellm:4000")
memories_path = os.environ.get("ARIA_MEMORIES_PATH", "/aria_memories")
```
```bash
# Shell/verification — env var with fallback
curl -s "http://localhost:${ARIA_API_PORT:-8000}/api/endpoint"
curl -s "http://localhost:${ARIA_WEB_PORT:-5050}/page"
```
**Reference ports from docker-compose:**
| Service | External Env Var | Internal Env Var | Defaults |
|---------|-----------------|------------------|----------|
| aria-api | `ARIA_API_PORT` | `API_INTERNAL_PORT` | 8000:8000 |
| aria-web | `ARIA_WEB_PORT` | `WEB_INTERNAL_PORT` | 5050:5000 |
| aria-db | `DB_PORT` | `DB_INTERNAL_PORT` | 5432:5432 |
| litellm | `LITELLM_PORT` | `LITELLM_INTERNAL_PORT` | 18793:4000 |

**3. 5-layer architecture** — DB → ORM → API → api_client → Skills → Agents. Templates call API through `/api/` proxy. Never import ORM models in templates.

### vis-network Source
Use the local bundled file: `/static/js/vis-network.min.js` (not CDN).

### Chart.js Source
Pin to: `https://cdn.jsdelivr.net/npm/chart.js@4.4.1` (consistent with majority of existing templates).

### vis-network Physics (for force-directed graphs)
```javascript
physics: { solver: 'forceAtlas2Based',
    forceAtlas2Based: { gravitationalConstant: -40, centralGravity: 0.005, springLength: 120, springConstant: 0.06 },
    stabilization: { iterations: 100 }
}
```
Exception: S-34 (chat DAG) uses hierarchical LR layout — no physics.

### CSS Color Variables (use instead of hardcoded hex)
```
--accent-primary: #6366f1  (indigo)
--accent-secondary: #8b5cf6  (purple — semantic memory)
--accent-cyan: #06b6d4
--accent-pink: #ec4899
--success: #10b981  (green — thoughts, input nodes)
--warning: #f59e0b  (orange — working memory, tools)
--danger: #ef4444  (red — lessons, errors)
--info: #3b82f6  (blue — KV memory, skills)
```

### Memory Type Color Mapping
| Type | Color | Shape | CSS Variable |
|------|-------|-------|-------------|
| semantic_memory | Purple #8b5cf6 | Dot | --accent-secondary |
| working_memory | Orange #f59e0b | Diamond | --warning |
| kv_memory | Blue #3b82f6 | Square | --info |
| thought | Green #10b981 | Triangle | --success |
| lesson | Red #ef4444 | Star | --danger |

### Docker Ports for Verification
- API: `localhost:${ARIA_API_PORT:-8000}` (aria-api)
- Web: `localhost:${ARIA_WEB_PORT:-5050}` (aria-web, external port)
- DB: `localhost:${DB_PORT:-5432}` (aria-db)


---

## Sprint Audit Log — E19 Ticket Upgrades

**Date:** 2026-02-27 | **Audit Author:** Copilot / production review session

All four E19 tickets have been upgraded to **AA++ production quality** with:
- Dynamic port sourcing (`set -a && source stacks/brain/.env && set +a`) — no hardcoded ports
- No direct SQL — all verification uses REST API only
- Full expert autonomous agent prompts with exact file:line references and code blocks
- ARIA-to-ARIA integration tests (Aria talks to herself, exercises tools, verifies via REST, reflects)
- Hard constraints checklists
- Definition of Done with checkbox items

### E19 Ticket Status

| Ticket | Title | Upgrade Status | ARIA-to-ARIA Steps |
|--------|-------|---------------|-------------------|
| [S-39](S-39-work-cycle-log-integrity-guardrails.md) | Work-Cycle Log Integrity Guardrails | AA++ Complete | 8 steps |
| [S-40](S-40-artifact-path-resolution-sub-agents.md) | Artifact Path Resolution for Sub-Agents | AA++ Complete | 7 steps |
| [S-41](S-41-schedule-create-job-arg-compatibility.md) | Schedule create_job Arg Compatibility | AA++ Complete | 8 steps |
| [S-42](S-42-heartbeat-payload-contract-hardening.md) | Heartbeat Payload Contract Hardening | AA++ Complete | 8 steps |

### Confirmed Architecture Evidence (all code-verified)

| Bug | File | Line | Fix |
|-----|------|------|-----|
| .json artifacts accept Markdown | src/api/routers/artifacts.py | 73-74 | json.loads() guard before open() |
| Session stats use stale heuristics | aria_skills/session_manager/__init__.py | 276 | Replace with GET /sessions/stats API call |
| work_cycle cron allows free-form JSON | aria_mind/cron_jobs.yaml | ~36 | Append strict JSON schema requirement |
| Goal ordering direction mismatch | src/api/routers/goals.py | 69 | .asc() to .desc() (match prompts.py) |
| No read_artifact_by_path() helper | aria_skills/api_client/__init__.py | ~1658 | Add helper method |
| MEMORY.md lacks nested path examples | aria_mind/MEMORY.md | 89 | Update table + nested example |
| create_job() rejects type kwarg | aria_skills/schedule/__init__.py | 52 | Add **kwargs + type alias normalization |
| "action": action not normalized | aria_skills/schedule/__init__.py | 80 | Change to "action": normalized_action |
| CreateHeartbeat.details: dict strict | src/api/schemas/requests.py | 130 | Broaden to dict | str | list | None |
| Non-dict details not normalized | src/api/routers/operations.py | ~190 | Add normalized_details wrapper |

---

## Sprint Audit Log — E20 Ticket Additions

**Date:** 2026-02-27 | **Source:** Memory classification audit + identity review

New tickets identified via full `aria_memories/` audit. All written to AA++ standard:
- 3× architecture review
- Dynamic port from `stacks/brain/.env`
- No direct SQL — all verification via REST API
- Full expert agent prompt with file:line references
- ARIA-to-ARIA integration test (Aria exercises tools, reflects on outcome)
- Hard constraints checklist + Definition of Done

### E20 Ticket Status

| Ticket | Title | Points | Priority | ARIA-to-ARIA Steps | Status |
|--------|-------|--------|----------|--------------------|--------|
| [S-43](S-43-identity-manifest-v1-1.md) | Identity Manifest v1.1 (Remove OpenClaw) | 2 | P1 | 4 steps | Ready |
| [S-44](S-44-heartbeat-md-in-aria-memories.md) | HEARTBEAT.md Accessible in aria_memories/ | 1 | P1 | 5 steps | Ready |
| [S-45](S-45-self-healing-error-recovery-phase2-5.md) | Self-Healing Error Recovery Phase 2–5 | 5 | P1 | 6 steps | ✅ Done |
| [S-46](S-46-telegram-bot-integration.md) | Telegram Bot Integration | 5 | P2 | 8 steps | Ready |
| [S-47](S-47-litellm-public-schema-isolation.md) | LiteLLM Writing to Public Schema | 2 | **P0** | 5 steps | Ready |
| [S-48](S-48-browser-hardcoded-litellm-port.md) | Browser Hardcoded LiteLLM Port :18793 | 2 | **P0** | 7 steps | Ready |
| [S-49](S-49-fresh-clone-env-bootstrap.md) | Fresh-Clone Auto-Bootstrap `.env` | 2 | **P0** | 5 steps | Ready |
| [S-50](S-50-upgrade-browserless-v1-to-v2.md) | Upgrade browserless/chrome v1 → ghcr.io/browserless/chromium v2 | 1 | P1 | 5 steps | Ready |
| [S-51](S-51-pg17-pgvector-upgrade-hnsw.md) | Upgrade pg16→pg17, pgvector 0.8.0→0.8.2, fix missing Python pkg, add HNSW indexes | 3 | **P0** | 5 steps | Ready |

### E20 Root Causes

| Ticket | Root Cause | Key File | Fix Summary |
|--------|-----------|----------|-------------|
| S-43 | identity_aria_v1.md never updated after V3 | aria_memories/memory/identity_aria_v1.md | Bump v1.1, remove OpenClaw, add Feb 15–27 evolution |
| S-44 | HEARTBEAT.md only in aria_mind/ — not readable via artifact tools | aria_memories/ (absent) | Create aria_memories/HEARTBEAT.md + fix cron path |
| S-45 | 20+ api_client methods bypass _request_with_retry | aria_skills/api_client/__init__.py | Migrate all to self.post()/self.get() + LLM fallback + health degradation |
| S-46 | telegram.py is a stub since TICKET-22 (never delivered) | aria_skills/social/telegram.py | Implement /status /goals /memory + long-poll cron |
| S-47 | search_path=litellm,public allows Prisma migrations to fall into public schema | src/api/db/session.py:55 + docker-compose.yml:221 + deps.py:28 | Remove ,public from all 3; add litellm to ensure_schema() |
| S-48 | LITELLM_PORT not injected into aria-web; index.html hardcodes :18793 | src/web/templates/index.html:354 | Add env var to docker-compose aria-web + app.py + template |
| S-49 | Fresh clone has no .env — stack starts with empty DB_PASSWORD + LITELLM_MASTER_KEY | Makefile (no check-env), first-run.sh (no --auto mode) | Add check-env to Makefile up target + --auto flag to first-run.sh |
| S-50 | `browserless/chrome:latest` frozen ~2 years on Docker Hub — no Chrome/CVE updates | `stacks/brain/docker-compose.yml:30` (old SHA-pinned v1 image) | Replace with `ghcr.io/browserless/chromium:v2.42.0` — identical REST API, non-breaking |
| S-51 | `pgvector` Python pkg absent from `pyproject.toml` → `HAS_PGVECTOR=False` in Docker → ORM uses JSONB → `cosine_distance()` crashes; no HNSW indexes = full seq scan on all vector searches | `pyproject.toml` (missing dep), `docker-compose.yml:4` (pg16/0.8.0), `session.py` (no HNSW DDL) | Add `pgvector>=0.3.6` to deps; bump to `pgvector/pgvector:0.8.2-pg17`; add HNSW indexes + alembic migration |
