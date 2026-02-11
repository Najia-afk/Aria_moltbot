# Aria v2 Sprint Master Overview — 2026-02-11 (Revised)

> **Product Owner:** Najia (Shiva) | **Sprint Agent:** Claude Opus 4.6
> **Created:** 2026-02-11 | **Revised:** 2026-02-11 | **Environment:** Mac Mini M4 (Production)

---

## Executive Summary

**5 sprints, 54 tickets, ~191 story points** across four phases:
1. **Phase 1** — Stabilize: Fix frontend bugs, critical backend bugs, add global pagination (Sprints 1 + 2)
2. **Phase 2** — Enhance: Goals sprint board with Kanban, PO skill, stacked chart (Sprint 3)
3. **Phase 3** — Scale: Knowledge graph auto-generation, skill pathfinding RAG, vis.js visualization (Sprint 4)
4. **Phase 4** — Evolve: Semantic memory (pgvector), error recovery, composable pipelines, self-improvement loop (Sprint 5)

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

## Sprint 1 — Frontend Fixes & Bug Squashing

**Phase:** 1 | **Tickets:** 13 | **Points:** ~35 | **Risk:** Low
**Focus:** Fix all known frontend bugs — charts, pricing, pagination, dead code, duplicate JS.

| # | Ticket | Priority | Pts | Description |
|---|--------|----------|-----|-------------|
| S1-01 | Fix double token counting | P0 | 3 | models.html triple-counts total_tokens in Usage by Model chart |
| S1-02 | Fix pricing inconsistency | P0 | 3 | Table uses log.spend, charts use calculateLogCost() |
| S1-03 | Fix LiteLLM pagination | P0 | 5 | 5-10MB JSON response hangs frontend |
| S1-04 | Consolidate duplicate JS | P1 | 3 | ~400 lines duplicated between models.html + wallets.html |
| S1-05 | Remove CNY dead code | P2 | 1 | Hardcoded CNY_TO_USD exchange rate |
| S1-06 | Fix dashboard filter | P1 | 2 | Chart filter dropdown is cosmetic only |
| S1-07 | Fix lite log duration | P2 | 2 | Duration always 0s for lite logs |
| S1-08 | Deduplicate spend fetches | P1 | 3 | 3 redundant fetches per page load |
| S1-09 | Remove console.logs | P2 | 1 | Debug statements in production |
| S1-10 | Fix model config | P1 | 3 | qwen3-coder-free + chimera-free misconfigured |
| S1-11 | DB cleanup | P1 | 3 | Garbage goals, duplicates |
| S1-12 | Fix stale litellm link | P2 | 1 | services.html links to /litellm |
| S1-13 | Verify & push | P0 | 3 | Docker test + git push |

**Dependency:** S1-01→S1-04 can parallel. S1-13 last.

---

## Sprint 2 — Critical Bug Fixes & Global Pagination

**Phase:** 1 | **Tickets:** 13 | **Points:** ~35 | **Risk:** Medium
**Focus:** Fix 6 critical backend bugs + add pagination (25/50) to all endpoints + frontend.

| # | Ticket | Priority | Pts | Description |
|---|--------|----------|-----|-------------|
| S2-01 | Fix goal priority sort | P0 | 1 | `.desc()` → `.asc()` (1 is highest priority) |
| S2-02 | Fix XSS in security.html | P0 | 2 | Unescaped title attribute |
| S2-03 | Fix goal date mismatch | P0 | 2 | Frontend sends target_date, API expects due_date |
| S2-04 | Fix GraphQL completed_at | P0 | 1 | update_goal_status doesn't set completed_at |
| S2-05 | Fix GraphQL upsert race | P1 | 2 | SELECT-then-INSERT not atomic |
| S2-06 | Add PaginatedResponse schema | P0 | 8 | Shared schema + pagination for 9 endpoints |
| S2-07 | Update api_client pagination | P0 | 3 | Add page/per_page params to all list methods |
| S2-08 | Create pagination.js component | P1 | 3 | Shared frontend pagination with 25/50 toggle |
| S2-09 | Wire pagination into templates | P1 | 5 | All list pages use pagination component |
| S2-10 | Add DB indexes for pagination | P2 | 2 | Performance indexes for paginated queries |
| S2-11 | Deduplicate JS helpers | P2 | 2 | escapeHtml, formatDate into shared utils |
| S2-12 | Fix update_goal rowcount | P1 | 1 | No rowcount check on update/delete |
| S2-13 | Verify & test Sprint 2 | P0 | 3 | Full regression test |

**Dependency:** S2-01→S2-05 parallel (bugs). S2-06→S2-09 sequential (pagination). S2-13 last.

---

## Sprint 3 — Goals Sprint Board & PO Skill

**Phase:** 2 | **Tickets:** 10 | **Points:** ~37 | **Risk:** Medium
**Focus:** Kanban board for goals (Backlog/To Do/Doing/On Hold/Done), drag-and-drop, PO skill, stacked chart, token optimization.

| # | Ticket | Priority | Pts | Description |
|---|--------|----------|-----|-------------|
| S3-01 | Goal model sprint fields | P0 | 3 | Add sprint, board_column, position, assigned_to, tags, updated_at |
| S3-02 | Goal board API endpoints | P0 | 5 | Board move, reorder, archive, sprint-summary, history |
| S3-03 | Sprint board template | P0 | 8 | Kanban columns with drag-and-drop, archive tab |
| S3-04 | PO skill for Aria | P1 | 5 | Sprint management, ticket creation, status updates |
| S3-05 | Update api_client board | P0 | 2 | Board methods in AriaAPIClient |
| S3-06 | Stacked chart (goals) | P1 | 3 | Goals status by day — Chart.js stacked bar |
| S3-07 | Optimize goal tokens | P2 | 3 | Lightweight sprint status tool (~200 tokens vs full list) |
| S3-08 | GraphQL board fields | P1 | 2 | Sprint fields in GoalType + mutations |
| S3-09 | GraphQL pagination | P1 | 3 | Add offset/limit to all GQL queries |
| S3-10 | Verify & test Sprint 3 | P0 | 3 | Full regression test |

**Dependency:** S3-01 → S3-02 → S3-03. S3-04/S3-05 after S3-02. S3-06→S3-09 parallel. S3-10 last.

---

## Sprint 4 — Knowledge Graph & Skill Pathfinding RAG

**Phase:** 3 | **Tickets:** 10 | **Points:** ~42 | **Risk:** Medium-High
**Focus:** Auto-generate skill graph, pathfinding API, vis.js visualization, graph query tool for Aria, codebase review.

| # | Ticket | Priority | Pts | Description |
|---|--------|----------|-----|-------------|
| S4-01 | Auto-generate skill graph | P0 | 5 | Populate knowledge graph from skill.json files |
| S4-02 | Graph pathfinding API | P0 | 5 | BFS traversal, search, skill-for-task endpoints |
| S4-03 | vis.js skill graph page | P1 | 5 | Color-coded interactive skill/focus visualization |
| S4-04 | Aria graph query tool | P0 | 5 | ~100 token skill discovery vs ~2000 token TOOLS.md |
| S4-05 | Graph query logging | P2 | 3 | Log Aria's graph traversals for analysis |
| S4-06 | Codebase duplicate review | P1 | 5 | Architecture compliance checker script |
| S4-07 | Auto-sync graph on startup | P1 | 3 | Regenerate graph when API restarts / skills change |
| S4-08 | GraphQL knowledge queries | P2 | 3 | Expose traverse/search via GraphQL |
| S4-09 | Production bug review | P1 | 5 | Full security + reliability audit |
| S4-10 | Verify & test Sprint 4 | P0 | 3 | Full integration test |

**Dependency:** S4-01 → S4-02 → S4-03/S4-04/S4-05. S4-06/S4-09 independent. S4-07 after S4-01. S4-08 after S4-02. S4-10 last.

---

## Sprint 5 — Memory v2, Error Recovery & Future-Proofing

**Phase:** 4 | **Tickets:** 8 | **Points:** ~42 | **Risk:** Medium-High
**Focus:** pgvector semantic memory, lessons learned system, conversation summarization, composable pipelines, test infrastructure, self-improvement PR loop, skill observability.
**Origin:** Claude's own recommendations from codebase audit.

| # | Ticket | Priority | Pts | Description |
|---|--------|----------|-----|-------------|
| S5-01 | pgvector semantic memory | P0 | 8 | Vector embeddings for memory search (cosine similarity) |
| S5-02 | Lessons learned table | P0 | 5 | Error pattern → resolution storage, pre-call checks |
| S5-03 | Conversation summarization | P1 | 5 | Compress sessions into episodic + decision memories |
| S5-04 | Composable skill pipelines | P1 | 5 | YAML pipeline templates, multi-skill orchestration |
| S5-05 | Test infrastructure | P0 | 8 | pytest + async fixtures, endpoint tests, CI-ready |
| S5-06 | Self-improvement PR loop | P2 | 5 | Proposal system with risk tiers + approval workflow |
| S5-07 | Skill observability dashboard | P1 | 3 | Invocation tracking, latency charts, error rates |
| S5-08 | Verify & test Sprint 5 | P0 | 3 | Full integration test |

**Dependency:** S5-01 → S5-03/S5-04. S5-02/S5-05/S5-06 standalone. S5-07 after S5-02. S5-08 last.

---

## Global Dependency Map

```
Sprint 1 (Phase 1 — Stabilize Frontend)
  ├── S1-01→S1-12 (mostly parallel)
  └── S1-13 (verify) last

    ↓ Complete S1 before S2

Sprint 2 (Phase 1 — Stabilize Backend + Pagination)
  ├── S2-01→S2-05 (bug fixes — parallel)
  ├── S2-06 → S2-07 → S2-08 → S2-09 (pagination chain)
  ├── S2-10, S2-11, S2-12 (independent)
  └── S2-13 (verify) last

    ↓ Complete S2 before S3

Sprint 3 (Phase 2 — Goals Sprint Board)
  ├── S3-01 (DB) → S3-02 (API) → S3-03 (UI)
  ├── S3-04, S3-05 (after S3-02)
  ├── S3-06→S3-09 (parallel)
  └── S3-10 (verify) last

    ↓ S3 and S4 can partially overlap

Sprint 4 (Phase 3 — Knowledge Graph + Quality)
  ├── S4-01 (generate) → S4-02 (pathfinding) → S4-03/S4-04/S4-05 (fan-out)
  ├── S4-06, S4-09 (independent — can start anytime)
  ├── S4-07 (after S4-01), S4-08 (after S4-02)
  └── S4-10 (verify) last

    ↓ Complete S4 before S5

Sprint 5 (Phase 4 — Memory v2 + Future-Proofing)
  ├── S5-01 (pgvector) → S5-03 (summarization) / S5-04 (pipelines)
  ├── S5-02 (lessons), S5-05 (tests), S5-06 (proposals) — standalone
  ├── S5-07 (observability, after S5-02)
  └── S5-08 (verify) last
```

---

## Estimated Effort

| Sprint | Tickets | Points | Est. Hours | Risk |
|--------|---------|--------|------------|------|
| Sprint 1 | 13 | ~35 | 8-12h | Low — verified bugs with known fixes |
| Sprint 2 | 13 | ~35 | 10-14h | Medium — pagination touches all layers |
| Sprint 3 | 10 | ~37 | 12-16h | Medium — new feature, DB migration |
| Sprint 4 | 10 | ~42 | 14-20h | Medium-High — new subsystem + audit |
| Sprint 5 | 8 | ~42 | 16-24h | High — new memory layer + pgvector |
| **Total** | **54** | **~191** | **60-86h** | |

---

## Execution Strategy

1. **Each sprint is autonomous** — copy sprint prompt into a new Claude session
2. **Sprint 1 first** — derisks frontend, highest user impact, lowest risk
3. **Sprint 2 after S1 verified** — bug fixes + pagination foundation
4. **Sprint 3 after S2 verified** — needs pagination in place
5. **Sprint 4 starts S4-06/S4-09 anytime** — code review is independent
6. **Sprint 5 after S4 verified** — needs knowledge graph + compliance checker
7. **Each ticket has a self-contained agent prompt** — one subagent per ticket
7. **Test locally in Docker** before marking done
8. **Update tasks/lessons.md** after each sprint

---

## Key Architecture Notes for Agents

### 5-Layer Rule (CRITICAL)
```
Layer 1: PostgreSQL DB (36 tables)
Layer 2: SQLAlchemy ORM (src/api/db/models.py — 21 classes)
Layer 3: FastAPI API (src/api/routers/ — 19 routers)
Layer 4: api_client (aria_skills/api_client/ — httpx client)
Layer 5: Skills + ARIA Mind/Agents
```

**Skills NEVER import SQLAlchemy. Skills ALWAYS go through api_client → API.**

### Critical Files
| File | Lines | Purpose |
|------|-------|---------|
| src/api/db/models.py | ~370 | All ORM models |
| src/api/routers/goals.py | 119 | Goal CRUD (S2+S3 target) |
| src/api/gql/resolvers.py | 197 | GraphQL resolvers |
| src/api/gql/types.py | 113 | GraphQL types |
| src/api/gql/schema.py | 97 | GraphQL schema |
| aria_skills/api_client/__init__.py | 1013 | Centralized HTTP client |
| aria_skills/registry.py | 178 | Skill registration |
| src/web/templates/goals.html | 1397 | Goals frontend |
| src/web/templates/knowledge.html | ~800 | vis.js reference implementation |
| tasks/lessons.md | 42 | Patterns + rules |

### DB Notes
- PostgreSQL 16, async via SQLAlchemy
- Alembic migrations at src/api/alembic/
- Goal: id, goal_id, title, description, status, priority, progress, due_date, created_at, completed_at
- KnowledgeEntity/KnowledgeRelation: graph with JSONB properties + GIN indexes
