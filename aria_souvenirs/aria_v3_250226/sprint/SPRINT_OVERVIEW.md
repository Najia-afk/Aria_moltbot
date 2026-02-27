# Aria v3 Sprint — 2026-02-26
## Sprint Overview

**Sprint Goal:** Security hardening, clean install reliability, API quality, engine resilience, observability, accessibility, UI consolidation, model pruning, agent delegation, full test coverage.

**Total Tickets:** 38 | **Total Points:** 157 | **Estimated:** ~125 hours

**Audit Sources:**
- Production Mac Mini audit (2026-02-26) — SSH + Docker + DB + Schema
- Expert subagent: API Layer — 22 issues found (3 P0, 7 P1, 12 P2)
- Expert subagent: Frontend/UX — 25 issues found (3 P0, 10 P1, 12 P2)
- Expert subagent: Engine/Skills/Infra — 17 issues found (0 P0, 6 P1, 11 P2)

---

## Epics

| Epic | Name | Tickets | Points |
|---|---|---|---|
| E1 | Docker Portability & Clean Install | S-01, S-02 | 8 |
| E2 | Model Pruning & Rate Limit Redesign | S-03, S-04 | 5 |
| E3 | Web UI Navigation Regrouping | S-05, S-06, S-07 | 10 |
| E4 | Chart Time Range Fixes | S-08 | 3 |
| E5 | Swarm Recap UI | S-09 | 5 |
| E6 | Agent Delegation System | S-10, S-11 | 8 |
| E7 | Cron Model Selection | S-12 | 3 |
| E8 | Dead Code & Duplicate Cleanup | S-13 | 3 |
| E9 | Public Schema Cleanup | S-14, S-15 | 7 |
| **E10** | **Security Hardening** | **S-16, S-17, S-18** | **13** |
| **E11** | **API Quality** | **S-19, S-20, S-21** | **13** |
| **E12** | **Engine Resilience** | **S-22, S-23** | **8** |
| **E13** | **Observability** | **S-24, S-25** | **8** |
| **E14** | **Frontend Quality** | **S-26, S-27** | **8** |
| **E15** | **Fresh Install** | **S-28** | **3** |
| **E16** | **Missing API Endpoints** | **S-29** | **5** |
| **E17** | **Testing** | **S-30** | **3** |
| **E18** | **Visualization & Graph Execution** | **S-31, S-32, S-33, S-34, S-35, S-36, S-37, S-38** | **44** |

---

## Phase Breakdown

### Phase 1 (P0 — Must Have) — 39 pts
| Ticket | Title | Pts | Epic |
|--------|-------|-----|------|
| S-01 | Docker socket Windows/Linux fix | 5 | E1 |
| S-03 | Prune LiteLLM models to essential set | 2 | E2 |
| S-04 | Move rate limits to model manager | 3 | E2 |
| S-08 | Chart time range selectors | 3 | E4 |
| S-13 | Remove dead templates and routes | 3 | E8 |
| S-14 | Verify schema-qualified queries | 5 | E9 |
| **S-16** | **GraphQL + WebSocket authentication** | **5** | **E10** |
| **S-17** | **CSRF protection + secure cookies** | **3** | **E10** |
| **S-18** | **XSS prevention (innerHTML + onclick)** | **5** | **E10** |
| **S-26** | **Accessibility overhaul (ARIA, keyboard)** | **5** | **E14** |

### Phase 2 (P1 — Should Have) — 75 pts
| Ticket | Title | Pts | Epic |
|--------|-------|-----|------|
| S-02 | Docker env var hardcoding fixes | 3 | E1 |
| S-05 | Regroup nav: Memory + Intelligence | 5 | E3 |
| S-09 | Swarm recap UI page | 5 | E5 |
| S-10 | Agent delegation with model param | 5 | E6 |
| **S-19** | **Pydantic request models (33 endpoints)** | **5** | **E11** |
| **S-20** | **Exception logging (21+ bare except)** | **3** | **E11** |
| **S-21** | **Health check DB + Alembic single source** | **5** | **E11** |
| **S-22** | **LLM timeout + skill circuit breakers** | **5** | **E12** |
| **S-23** | **Config validation (Pydantic BaseSettings)** | **3** | **E12** |
| **S-24** | **Structured logging + Docker log rotation** | **3** | **E13** |
| **S-25** | **Skill health API + OpenTelemetry** | **5** | **E13** |
| **S-27** | **API proxy error handling + error display** | **3** | **E14** |
| **S-28** | **First-run script + quickstart docs** | **3** | **E15** |
| **S-31** | **Memory Graph (vis-network all memory types)** | **8** | **E18** |
| **S-34** | **Chat Tool Execution Graph (LangGraph DAG)** | **8** | **E18** |
| **S-37** | **Unified Memory Search (cross-type)** | **5** | **E18** |
| **S-38** | **Navigation Update (all viz pages)** | **2** | **E18** |

### Phase 3 (P2 — Nice to Have) — 42 pts
| Ticket | Title | Pts | Epic |
|--------|-------|-----|------|
| S-06 | Regroup nav: Agents & Skills | 3 | E3 |
| S-07 | Regroup nav: Operations consolidation | 2 | E3 |
| S-11 | End-to-end delegate_task() method | 3 | E6 |
| S-12 | Cron job model selection | 3 | E7 |
| S-15 | Drop public schema duplicates | 2 | E9 |
| **S-29** | **Complete CRUD + Sentiment API + GraphQL** | **5** | **E16** |
| **S-30** | **Load tests + E2E tests** | **3** | **E17** |
| **S-32** | **Memory Timeline & Heatmap (Chart.js)** | **5** | **E18** |
| **S-33** | **Embedding Cluster Explorer (PCA/t-SNE)** | **8** | **E18** |
| **S-35** | **Memory Consolidation Dashboard** | **5** | **E18** |
| **S-36** | **Lessons Learned Dashboard** | **3** | **E18** |

---

## Dependency Graph

```
Phase 1 (P0) — Do First:
  S-14 (schema queries) → S-15 (drop public)
  S-16 (auth) ──┬──→ S-29 (new endpoints use auth)
                ├──→ S-17 (CSRF builds on auth)
                └──→ S-28 (first-run generates API key)
  S-18 (XSS) ─────→ S-26 (accessibility can reuse refactored templates)
  S-01 (Docker) ───→ S-28 (first-run references Docker fix)

Phase 2 (P1) — Security + Quality:
  S-19 (Pydantic) ─→ S-29 (new endpoints use Pydantic)
  S-21 (Alembic) ──→ S-15 (Alembic manages schema)
  S-22 (circuit breaker) → S-25 (OpenTelemetry instruments circuit breaker)
  S-24 (structured logging) → S-20 (exception logging uses structured logger)

Phase 3 (P2) — Features + Testing:
  S-28 (first-run) → S-30 (E2E tests need Docker up)
  S-29 (CRUD) ────→ S-30 (load tests exercise DELETE)

Phase 2-3 — Visualization (E18):
  S-31 (memory graph) ──┐
  S-32 (timeline)  ─────┤
  S-33 (embeddings) ────┼──→ S-38 (nav update — all routes must exist)
  S-34 (chat DAG) ──────┤
  S-35 (consolidation) ─┤
  S-36 (lessons) ───────┤
  S-37 (unified search) ┘
```

---

## New Tickets Summary (S-16 through S-30)

### E10 — Security Hardening (13 pts)
| Ticket | File | Description |
|--------|-------|-------------|
| [S-16](S-16-graphql-websocket-auth.md) | `main.py L575`, `auth.py L47-55`, `engine_chat.py L478`, `engine_roundtable.py L878` | Mount GraphQL/WS with auth deps; fix fail-open |
| [S-17](S-17-csrf-secure-cookies.md) | `app.py L16`, `base.html`, `aria-common.js` | CSRFProtect, meta tag, ariaFetch wrapper, secure cookies |
| [S-18](S-18-xss-prevention.md) | 6 templates with innerHTML, 200+ onclick handlers | safeHTML(), event delegation, var→const |

### E11 — API Quality (13 pts)
| Ticket | File | Description |
|--------|-------|-------------|
| [S-19](S-19-pydantic-request-models.md) | 33 POST endpoints | Replace request.json() with Pydantic BaseModel |
| [S-20](S-20-exception-logging.md) | 21+ bare except:pass | Add logger.exception() to all bare excepts |
| [S-21](S-21-health-check-alembic.md) | `health.py L40`, `alembic/`, `db/session.py` | Real DB check, Alembic-only migrations, disable auto-create_all |

### E12 — Engine Resilience (8 pts)
| Ticket | File | Description |
|--------|-------|-------------|
| [S-22](S-22-llm-timeout-circuit-breakers.md) | `llm_gateway.py L155`, `base.py L363` | asyncio.wait_for timeout, generic CircuitBreaker for all skills |
| [S-23](S-23-config-validation.md) | `config.py L1-64`, `entrypoint.py` | Pydantic BaseSettings with validators |

### E13 — Observability (8 pts)
| Ticket | File | Description |
|--------|-------|-------------|
| [S-24](S-24-structured-logging.md) | `entrypoint.py L199`, `docker-compose.yml` | Call configure_logging(), Docker log rotation, correlation IDs |
| [S-25](S-25-skill-health-opentelemetry.md) | `skill_health_dashboard.py`, `telemetry.py`, `metrics.py` | API endpoint for skill health, OpenTelemetry foundation |

### E14 — Frontend Quality (8 pts)
| Ticket | File | Description |
|--------|-------|-------------|
| [S-26](S-26-accessibility-overhaul.md) | `base.html`, `base.css` | Skip nav, keyboard dropdowns, ARIA labels, :focus-visible |
| [S-27](S-27-api-proxy-error-handling.md) | `app.py L63-77`, `aria-common.js` | try/except in proxy, standardize showErrorState() |

### E15 — Fresh Install (3 pts)
| Ticket | File | Description |
|--------|-------|-------------|
| [S-28](S-28-first-run-quickstart.md) | `scripts/`, `README.md`, `.env.example` | First-run script, quickstart docs, required vs optional vars |

### E16 — Missing API Endpoints (5 pts)
| Ticket | File | Description |
|--------|-------|-------------|
| [S-29](S-29-complete-crud-sentiment-graphql.md) | `routers/`, `gql/schema.py`, `gql/resolvers.py` | DELETE/UPDATE for 8 entities, sentiment router, GraphQL mutations, cursor pagination |

### E17 — Testing (3 pts)
| Ticket | File | Description |
|--------|-------|-------------|
| [S-30](S-30-load-tests-e2e.md) | `tests/load/`, `tests/e2e/`, `.github/workflows/` | Locust load tests, Playwright E2E, CI pipeline |

### E18 — Visualization & Graph Execution (44 pts)
| Ticket | File | Description |
|--------|-------|-------------|
| [S-31](S-31-memory-graph-visualization.md) | `memories.py`, `memory_graph.html`, `app.py` | vis-network graph of all memory types with category/source edges |
| [S-32](S-32-memory-timeline-heatmap.md) | `memories.py`, `memory_timeline.html`, `app.py` | Chart.js temporal heatmap, stacked area, TTL decay bars |
| [S-33](S-33-embedding-cluster-explorer.md) | `memories.py`, `embedding_explorer.html`, `app.py` | PCA/t-SNE 2D scatter plot of semantic memory embeddings |
| [S-34](S-34-chat-tool-execution-graph.md) | `chat_engine.py`, `engine_chat.html` | LangGraph-style DAG for tool execution pipeline in chat UI |
| [S-35](S-35-memory-consolidation-dashboard.md) | `memories.py`, `memory_consolidation.html`, `app.py` | Surface→Medium→Deep flow, compression stats, promotion candidates |
| [S-36](S-36-lessons-learned-dashboard.md) | `lessons.py`, `lessons.html`, `app.py` | Skill→Error→Lesson vis-network graph, effectiveness charts |
| [S-37](S-37-unified-memory-search.md) | `memories.py`, `memory_search.html`, `app.py` | Cross-memory-type search (vector+ILIKE) with ranked results |
| [S-38](S-38-navigation-update-visualization.md) | `base.html` | Nav menu update — add all new visualization pages |

---

## Recommended Execution Order

```
Week 1: Security Sprint (P0)
  Day 1-2: S-16 (GraphQL/WS auth) + S-17 (CSRF)
  Day 3:   S-18 (XSS) + S-26 (accessibility)
  Day 4:   S-01 (Docker) + S-14 (schema queries)
  Day 5:   S-03 (model prune) + S-04 (rate limits) + S-08 (charts) + S-13 (dead code)

Week 2: Quality Sprint (P1)
  Day 1:   S-19 (Pydantic) + S-20 (exceptions)
  Day 2:   S-21 (health/Alembic) + S-23 (config validation)
  Day 3:   S-22 (LLM timeout/circuit breakers)
  Day 4:   S-24 (logging) + S-25 (observability)
  Day 5:   S-27 (proxy) + S-28 (first-run) + S-02 (env vars)

Week 3: Features Sprint (P1-P2)
  Day 1-2: S-05 (nav Memory+Intel) + S-09 (swarm recap)
  Day 3:   S-10 (agent model) + S-06 (nav Agents) + S-07 (nav Ops)
  Day 4:   S-11 (delegate_task) + S-12 (cron model) + S-15 (public schema)
  Day 5:   S-29 (CRUD/sentiment/GraphQL) + S-30 (tests)
```
