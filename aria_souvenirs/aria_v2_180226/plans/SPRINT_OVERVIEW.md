# Sprint Overview — Operation Independence

**Project:** Aria v2.0 — OpenClaw Phase-Out  
**Total Sprints:** 12 | **Total Tickets:** 66 | **Total Hours:** ~176h  
**Start Date:** 2026-02-18  
**Execution Mode:** Swarm per sprint, isolated PM per sprint  

---

## Sprint Status Board

| Sprint | Epic | Focus | Tickets | Status |
|--------|------|-------|---------|--------|
| Sprint 1 | E1 | Engine Bootstrap + LLM Gateway | S1-01 → S1-06 | 🔲 NOT STARTED |
| Sprint 2 | E1 | Chat Engine + Streaming | S2-01 → S2-06 | 🔲 NOT STARTED |
| Sprint 3 | E2 | Scheduler + Cron Management | S3-01 → S3-05 | 🔲 NOT STARTED |
| Sprint 4 | E3 | Agent Pool + Orchestration | S4-01 → S4-06 | 🔲 NOT STARTED |
| Sprint 5 | E4 | Session Management + Context | S5-01 → S5-05 | 🔲 NOT STARTED |
| Sprint 6 | E5 | Chat UI + Web Interface | S6-01 → S6-06 | 🔲 NOT STARTED |
| Sprint 7 | E5 | Operations Dashboard | S7-01 → S7-05 | 🔲 NOT STARTED |
| Sprint 8 | E6 | OpenClaw Removal + Migration | S8-01 → S8-06 | 🔲 NOT STARTED |
| Sprint 9 | E7 | Python 3.13+ Modernization | S9-01 → S9-05 | 🔲 NOT STARTED |
| Sprint 10 | E8 | Unit Tests for Engine | S10-01 → S10-06 | 🔲 NOT STARTED |
| Sprint 11 | E8 | Integration + E2E Tests | S11-01 → S11-05 | 🔲 NOT STARTED |
| Sprint 12 | E8 | Production Hardening | S12-01 → S12-05 | 🔲 NOT STARTED |

---

## Dependency Graph

```
Sprint 1 (Engine Core) ──┬──→ Sprint 2 (Chat) ──→ Sprint 6 (Chat UI)
                         │                         
                         ├──→ Sprint 3 (Scheduler) ──→ Sprint 7 (Ops UI)
                         │
                         └──→ Sprint 4 (Agents) ──→ Sprint 5 (Sessions)
                                                          │
                                 Sprint 8 (Cleanup) ◄─────┘
                                      │
                                      ▼
                              Sprint 9 (Python 3.13)
                                      │
                                      ▼
                              Sprint 10 (Unit Tests)
                                      │
                                      ▼
                              Sprint 11 (Integration)
                                      │
                                      ▼
                              Sprint 12 (Production)
```

**Parallelizable:** Sprints 2, 3, 4 can run in parallel (all depend only on Sprint 1).  
**Parallelizable:** Sprints 6, 7 can run in parallel (depend on Sprint 2 and Sprint 3 respectively).

---

## Ticket Index

### Sprint 1 — Engine Bootstrap (E1)
| ID | Title | Priority | Points | Status |
|----|-------|----------|--------|--------|
| S1-01 | Create `aria_engine` package structure | P0 | 2 | 🔲 |
| S1-02 | Implement LLM Gateway (direct litellm SDK) | P0 | 5 | 🔲 |
| S1-03 | Thinking token handling | P0 | 3 | 🔲 |
| S1-04 | Tool calling bridge (skills → LiteLLM tools) | P0 | 5 | 🔲 |
| S1-05 | Alembic migration for `aria_engine` schema | P0 | 3 | 🔲 |
| S1-06 | Docker entrypoint for aria-engine | P0 | 3 | 🔲 |

### Sprint 2 — Chat Engine (E1)
| ID | Title | Priority | Points | Status |
|----|-------|----------|--------|--------|
| S2-01 | Chat session lifecycle (create/resume/end) | P0 | 5 | 🔲 |
| S2-02 | Context window manager (sliding + importance) | P0 | 5 | 🔲 |
| S2-03 | Streaming responses via WebSocket | P0 | 5 | 🔲 |
| S2-04 | JSONL transcript export | P1 | 2 | 🔲 |
| S2-05 | System prompt assembly pipeline | P0 | 3 | 🔲 |
| S2-06 | Chat API endpoints (REST + WebSocket) | P0 | 5 | 🔲 |

### Sprint 3 — Scheduler (E2)
| ID | Title | Priority | Points | Status |
|----|-------|----------|--------|--------|
| S3-01 | APScheduler + PostgreSQL job store | P0 | 5 | 🔲 |
| S3-02 | Migrate 15 cron jobs to DB-backed scheduler | P0 | 3 | 🔲 |
| S3-03 | Cron CRUD API endpoints | P0 | 3 | 🔲 |
| S3-04 | Cron web UI page | P1 | 5 | 🔲 |
| S3-05 | Agent-specific heartbeats via scheduler | P0 | 3 | 🔲 |

### Sprint 4 — Agent Pool (E3)
| ID | Title | Priority | Points | Status |
|----|-------|----------|--------|--------|
| S4-01 | Async agent lifecycle (spawn/track/terminate) | P0 | 5 | 🔲 |
| S4-02 | Per-agent session isolation | P0 | 3 | 🔲 |
| S4-03 | Agent tabs in web UI | P1 | 5 | 🔲 |
| S4-04 | Agent auto-routing with pheromone scoring | P0 | 3 | 🔲 |
| S4-05 | Roundtable multi-agent collaboration | P1 | 5 | 🔲 |
| S4-06 | Agent performance dashboard updates | P2 | 3 | 🔲 |

### Sprint 5 — Session Management (E4)
| ID | Title | Priority | Points | Status |
|----|-------|----------|--------|--------|
| S5-01 | Rewrite session_manager (PostgreSQL-only) | P0 | 5 | 🔲 |
| S5-02 | Auto-session management | P0 | 3 | 🔲 |
| S5-03 | Session history with pagination + search | P1 | 3 | 🔲 |
| S5-04 | Cross-session context loading | P1 | 5 | 🔲 |
| S5-05 | Session protection in engine | P0 | 2 | 🔲 |

### Sprint 6 — Chat UI (E5)
| ID | Title | Priority | Points | Status |
|----|-------|----------|--------|--------|
| S6-01 | Web chat UI with WebSocket streaming | P0 | 8 | 🔲 |
| S6-02 | Thinking token display panel | P1 | 3 | 🔲 |
| S6-03 | Session sidebar (list/create/resume/delete) | P0 | 5 | 🔲 |
| S6-04 | Model selector dropdown | P1 | 2 | 🔲 |
| S6-05 | Tool call visualization in chat | P2 | 3 | 🔲 |
| S6-06 | Remove OpenClaw proxy routes from web app | P0 | 2 | 🔲 |

### Sprint 7 — Operations Dashboard (E5)
| ID | Title | Priority | Points | Status |
|----|-------|----------|--------|--------|
| S7-01 | Cron management web page | P0 | 5 | 🔲 |
| S7-02 | Agent management web page | P1 | 5 | 🔲 |
| S7-03 | System prompt editor (per-agent) | P2 | 3 | 🔲 |
| S7-04 | Update operations.html for native cron | P0 | 2 | 🔲 |
| S7-05 | Engine health dashboard page | P1 | 3 | 🔲 |

### Sprint 8 — OpenClaw Removal (E6)
| ID | Title | Priority | Points | Status |
|----|-------|----------|--------|--------|
| S8-01 | Remove clawdbot from docker-compose.yml | P0 | 1 | 🔲 |
| S8-02 | Delete OpenClaw config files | P0 | 1 | 🔲 |
| S8-03 | Delete openclaw_config.py | P0 | 1 | 🔲 |
| S8-04 | Clean config.py (remove OPENCLAW_* vars) | P0 | 2 | 🔲 |
| S8-05 | Clean sessions.py router (remove sync logic) | P0 | 5 | 🔲 |
| S8-06 | Data migration: existing sessions → engine | P0 | 3 | 🔲 |

### Sprint 9 — Python 3.13+ (E7)
| ID | Title | Priority | Points | Status |
|----|-------|----------|--------|--------|
| S9-01 | Update pyproject.toml (requires-python ≥3.13) | P1 | 1 | 🔲 |
| S9-02 | Modernize type hints (X | None syntax) | P2 | 3 | 🔲 |
| S9-03 | Use asyncio.TaskGroup in agent pool | P1 | 3 | 🔲 |
| S9-04 | Use tomllib for config parsing | P2 | 1 | 🔲 |
| S9-05 | Python 3.13 JIT flags + benchmarks | P2 | 2 | 🔲 |

### Sprint 10 — Unit Tests (E8)
| ID | Title | Priority | Points | Status |
|----|-------|----------|--------|--------|
| S10-01 | Tests: LLMGateway | P0 | 3 | 🔲 |
| S10-02 | Tests: ChatEngine | P0 | 3 | 🔲 |
| S10-03 | Tests: Scheduler | P0 | 3 | 🔲 |
| S10-04 | Tests: AgentPool | P0 | 3 | 🔲 |
| S10-05 | Tests: SessionManager | P0 | 2 | 🔲 |
| S10-06 | Tests: No OpenClaw imports anywhere | P0 | 1 | 🔲 |

### Sprint 11 — Integration Tests (E8)
| ID | Title | Priority | Points | Status |
|----|-------|----------|--------|--------|
| S11-01 | E2E: WebSocket chat flow | P0 | 3 | 🔲 |
| S11-02 | E2E: Cron execution flow | P0 | 3 | 🔲 |
| S11-03 | E2E: Agent routing flow | P0 | 3 | 🔲 |
| S11-04 | Dashboard verification (all 25+ pages) | P0 | 3 | 🔲 |
| S11-05 | JSONL backward compatibility | P1 | 2 | 🔲 |

### Sprint 12 — Production (E8)
| ID | Title | Priority | Points | Status |
|----|-------|----------|--------|--------|
| S12-01 | Load testing | P1 | 3 | 🔲 |
| S12-02 | Memory profiling | P1 | 3 | 🔲 |
| S12-03 | Prometheus metrics for engine | P0 | 3 | 🔲 |
| S12-04 | Mac Mini production deployment | P0 | 3 | 🔲 |
| S12-05 | Rollback procedure + docs | P0 | 2 | 🔲 |

---

## Velocity Tracking

| Sprint | Planned Points | Actual Points | Duration | Notes |
|--------|---------------|---------------|----------|-------|
| 1 | 21 | — | — | — |
| 2 | 25 | — | — | — |
| 3 | 19 | — | — | — |
| 4 | 24 | — | — | — |
| 5 | 18 | — | — | — |
| 6 | 23 | — | — | — |
| 7 | 18 | — | — | — |
| 8 | 13 | — | — | — |
| 9 | 10 | — | — | — |
| 10 | 15 | — | — | — |
| 11 | 14 | — | — | — |
| 12 | 14 | — | — | — |
