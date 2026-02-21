# Sprint Overview — Operation Integration

**Project:** Aria v3.0 — Database Integration & Engine Activation  
**Total Sprints:** 1 (focused) | **Total Tickets:** 10 | **Total Points:** 38  
**Start Date:** 2026-02-19  
**Execution Mode:** Sequential phases, subagent delegation  

---

## Mission Statement

Consolidate Aria's database layer (Alembic migrations for fresh installs), activate
all Engine v2 routers (chat, agents, metrics), unify heartbeat/cron systems into
the DB, verify skills + chat end-to-end, and activate the prototype-derived memory/sentiment
skills that are fully built but not yet wired into the automated pipeline.

---

## Sprint Status Board

| # | Ticket | Title | Points | Phase | Status |
|---|--------|-------|--------|-------|--------|
| 1 | S-50 | Alembic Baseline Migration | 5 | P0 | ✅ DONE |
| 2 | S-51 | Fix Disconnected s42 Migration | 2 | P0 | ✅ DONE |
| 3 | S-52 | Mount Engine Chat Router (Fix Chat) | 5 | P0 | ✅ DONE |
| 4 | S-53 | Mount Engine Agents + Metrics Routers | 3 | P0 | ✅ DONE |
| 5 | S-54 | Cron Jobs YAML Auto-Sync on Startup | 5 | P1 | ✅ DONE |
| 6 | S-55 | Unify Heartbeat to HeartbeatLog Table | 5 | P1 | ✅ DONE |
| 7 | S-56 | Skills & api_client Audit + Fix | 5 | P1 | ✅ DONE |
| 8 | S-57 | Web UI Chat + Agent Dashboard Wiring | 4 | P2 | ✅ DONE |
| 9 | S-58 | Wire Memory Compression (Cron + Auto-Run) | 3 | P1 | 🔲 NOT STARTED |
| 10 | S-59 | Archive Prototypes Folder | 1 | P2 | 🔲 NOT STARTED |

**Total: 38 points**

---

## Dependency Graph

```
S-50 (Alembic baseline) ──┬──→ S-51 (fix s42 chain)
                          │
S-52 (mount chat router) ─┤──→ S-57 (web UI wiring)
S-53 (mount agents)  ─────┘
                          
S-54 (cron sync) ──────────→ S-58 (memory compression cron)
S-55 (heartbeat unify) ───── independent  
S-56 (skills audit) ──────── independent
S-59 (archive prototypes) ── independent
```

Phase 0 (P0) — Critical path: S-50, S-51, S-52, S-53  
Phase 1 (P1) — Integration: S-54, S-55, S-56  
Phase 2 (P2) — Polish: S-57  

---

## Phase Summary

### Phase 1 (P0) — Critical: Database & Router Activation
- **S-50**: Create Alembic baseline migration covering all 36 ORM tables for fresh installs
- **S-51**: Fix s42 migration's `down_revision = None` to chain properly into s37→s44 sequence
- **S-52**: Mount `engine_chat` router + call `configure_engine()` in lifespan → fixes chat
- **S-53**: Mount `engine_agents` + `engine_agent_metrics` routers → enables agent dashboard

### Phase 2 (P1) — Integration: Heartbeat, Cron, Skills
- **S-54**: Auto-sync `cron_jobs.yaml` → DB on startup so YAML changes auto-deploy
- **S-55**: Unify both heartbeat systems to write to `heartbeat_log` table via API
- **S-56**: Full skills audit — verify api_client usage, fix any broken `run()` methods

### Phase 3 (P2) — Polish: Web UI
- **S-57**: Fix WebSocket URL mismatch in chat UI + verify all dashboard pages hit live APIs
- **S-59**: Move `aria_mind/prototypes/` to `aria_souvenirs/prototypes_160226/` — all implemented

---

## Epic E10 — Prototypes Integration Audit (2026-02-19)

Lean integration audit of the `aria_mind/prototypes/` folder.

### Prototype Status (verified 2026-02-19)

| Prototype | Target | Status |
|-----------|--------|--------|
| `session_protection_fix.py` | `aria_skills/session_manager/` | ✅ DONE — lines 243-256 |
| `memory_compression.py` | `aria_skills/memory_compression/` | ✅ DONE — skill exists, 516 lines |
| `sentiment_analysis.py` | `aria_skills/sentiment_analysis/` | ✅ DONE — skill exists, 962 lines |
| `pattern_recognition.py` | `aria_skills/pattern_recognition/` | ✅ DONE — skill exists |
| `unified_search.py` | `aria_skills/unified_search/` | ✅ DONE — RRF merge implemented |
| `embedding_memory.py` | pgvector via api_client | ✅ STOPPED — reinvents `api_client.search_memories_semantic()` |
| `advanced_memory_skill.py` | N/A | ✅ STOPPED — superseded by individual skills |

### What was implemented as part of this audit
- `POST /analysis/compression/auto-run` — new API endpoint (self-fetching compression, no payload needed)
- `memory_compression` cron job added to `aria_mind/cron_jobs.yaml` (every 6 hours)

---

## Epic E11 — MCP Hybrid Integration (2026-02-21)

Add MCP (Model Context Protocol) as a hybrid layer. Keep existing in-process skill
execution untouched. Add MCP client (consume external servers) + MCP server (expose
Aria's skills).

**Design doc:** `aria_souvenirs/aria_v2_210226/plans/MCP_HYBRID_ARCHITECTURE.md`

### Sprint Status Board — E11

| # | Ticket | Title | Points | Phase | Status |
|---|--------|-------|--------|-------|--------|
| 1 | S-60 | MCP Client Adapter — Core | 5 | P0 | ✅ DONE |
| 2 | S-61 | MCP Client — ToolRegistry Integration | 3 | P0 | 🔲 NOT STARTED |
| 3 | S-62 | MCP Server Adapter — Expose Skills | 5 | P1 | 🔲 NOT STARTED |
| 4 | S-63 | MCP Config (YAML + EngineConfig + .env) | 2 | P0 | 🔲 NOT STARTED |
| 5 | S-64 | MCP Client — Lifecycle & Error Handling | 3 | P1 | 🔲 NOT STARTED |
| 6 | S-65 | MCP Integration Tests | 3 | P2 | 🔲 NOT STARTED |
| 7 | S-66 | Documentation Update | 2 | P2 | 🔲 NOT STARTED |

**Total: 23 points**

### Dependency Graph — E11

```
S-60 (client core)  ──┬──→ S-61 (registry integration) ──→ S-64 (lifecycle)
                      │
S-63 (config) ────────┘
                      
S-62 (server adapter) ── independent of client path

S-65 (tests) ─── after S-60, S-61, S-62, S-63, S-64
S-66 (docs)  ─── after all others
```

Phase 0 (P0): S-60, S-61, S-63 (foundation — 10 pts)
Phase 1 (P1): S-62, S-64 (production features — 8 pts)
Phase 2 (P2): S-65, S-66 (quality & docs — 5 pts)

---

## Velocity Tracking

| Metric | Value |
|--------|-------|
| Sprint start (E10) | 2026-02-19 |
| Points planned (E10) | 38 |
| Points completed (E10) | 34 |
| Velocity (E10) | 34 pts / 1 session |
| Sprint start (E11) | 2026-02-21 |
| Points planned (E11) | 23 |
| Points completed (E11) | 0 |
