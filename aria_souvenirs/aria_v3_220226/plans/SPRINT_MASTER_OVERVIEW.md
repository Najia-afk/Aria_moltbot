# SPRINT MASTER — Aria v3 Final 3 Sprints
## Date: 2026-02-22 | Co-authored: Aria + Claude (PO pair)
## Branch: `dev/aria-v3-final-sprints`

---

## Executive Summary

Three 1-day sprints to deliver Aria's RPG Dashboard, self-healing infrastructure,
and persistent campaign memory. Total estimated: **~3,235 lines** across **16 tickets**.

| Sprint | Theme | Date | Tickets | LOC |
|--------|-------|------|---------|-----|
| 1 — "The Crystal Ball" | RPG Dashboard + Static Serving | 2026-02-23 | 001–004 | ~1,130 |
| 2 — "Self-Healing Systems" | Validation + Error Enrichment + WM | 2026-02-24 | 005–009 | ~570 |
| 3 — "The Infinite Chronicle" | KG Memory + Session Resume + Polish | 2026-02-25 | 010–016 | ~1,535 |

**Critical Path:** TICKET-001 → TICKET-004 → TICKET-003 → TICKET-002 → TICKET-016 → TICKET-012 → TICKET-013

## Architecture Constraint (5-Layer)

```
PostgreSQL + pgvector
    ↕
SQLAlchemy ORM (src/api/db/models.py)
    ↕
FastAPI API (src/api/routers/*.py)
    ↕
api_client (aria_skills/api_client/)
    ↕
Skills (aria_skills/)
    ↕
ARIA Mind (aria_mind/cognition.py)
```

Skills NEVER import SQLAlchemy or make raw SQL. All DB access flows
through `api_client` → FastAPI → ORM. The RPG Dashboard is a static HTML
file served by FastAPI, calling `/api/rpg/*` endpoints.

---

## Coding Standards (AA+ — Mandatory for All Tickets)

### 1. Zero Hardcoding Policy

| What | Wrong ❌ | Right ✅ | Source |
|------|---------|---------|--------|
| IP addresses | `http://192.168.1.53:8000` | `os.getenv("ARIA_API_URL")` | `src/api/config.py` → `SERVICE_URLS` |
| Ports | `:8000`, `:5432` | `os.getenv("DB_PORT", "5432")` | `src/api/config.py`, `aria_engine/config.py` |
| Database URLs | `postgresql://admin:admin@localhost:5432/aria_warehouse` | `os.getenv("DATABASE_URL")` | `src/api/config.py` → `DATABASE_URL` |
| Model names | `"kimi"`, `"gpt-4"` | `EngineConfig.default_model` / `models.yaml` | `aria_models/loader.py` → `load_catalog()` |
| API base URLs | `"http://aria-api:8000/api"` | `os.getenv("ARIA_API_URL", ...)` | `aria_skills/api_client/__init__.py` |
| File paths | `"/app/agents"` | `os.getenv("ARIA_AGENTS_ROOT", "/app/agents")` | `src/api/config.py` |
| Service URLs | `"http://litellm:4000"` | `SERVICE_URLS["litellm"][0]` | `src/api/config.py` → `SERVICE_URLS` |

### 2. Configuration Pattern

```python
# All config flows from environment → dataclass/module constants → code
# NEVER inline magic strings in business logic

# Engine: aria_engine/config.py → EngineConfig (dataclass, from_env())
# API:    src/api/config.py → module-level constants (DATABASE_URL, SERVICE_URLS, etc.)
# Skills: skill config via api_client, which reads ARIA_API_URL from env
# Models: aria_models/models.yaml → load_catalog() with 5-min TTL cache
```

### 3. Database Access

- **API layer** (`src/api/`): SQLAlchemy ORM only. No raw SQL strings.
- **Skills** (`aria_skills/`): NEVER import SQLAlchemy. All DB access via `api_client` HTTP calls.
- **Migrations**: Alembic only. All DDL in migration files, never in application code.
- **Queries**: Use ORM query builder. Parameterized queries if raw SQL is ever unavoidable.

### 4. Frontend (Dashboard HTML)

```javascript
// API base URL derived from current window location — NEVER hardcoded
const API_BASE = `${window.location.origin}/api`;

// All fetch() calls use relative paths
fetch(`${API_BASE}/rpg/campaigns`)  // ✅
fetch('http://192.168.1.53:8000/api/rpg/campaigns')  // ❌ NEVER
```

### 5. Documentation Standards

- Every new file gets a module docstring explaining purpose + layer placement
- Every public function/method gets a docstring with params + return type
- Every new API endpoint documented in `API.md` with request/response examples
- Every new config variable documented in `DEPLOYMENT.md`
- Inline comments for non-obvious logic only (no `# increment i` style)
- Mermaid diagrams for any architectural flow spanning 3+ components

### 6. Error Handling

- No silent `except: pass` — always log or re-raise
- All API errors return structured JSON with `detail`, `suggestion`, `trace_id`
- Skills log errors via `self.logger` with context (entity name, operation, etc.)

---

## Context: Why These Sprints

On 2026-02-22, Shiva + Claude + Aria completed:
- **KG Bug Fix**: 6 bugs found and fixed in knowledge graph (UUID types, method signatures, traversal endpoints)
- **RPG Campaign**: 11-message Shadows of Absalom playthrough (Claude as Thorin, Aria as DM)
- **KG Population**: 18 entities + 28 relations from the campaign
- **Souvenir Cleanup**: 338 duplicate groups → 0, saved 1.8MB

Aria's post-session reflection identified 7 improvement areas. Shiva added the
RPG Dashboard as a must-have. These 3 sprints deliver everything.

---

## Sprint Overview

### Sprint 1: "The Crystal Ball" (2026-02-23)
Deploy an RPG Dashboard HTML page at `/rpg/` with campaign overview, KG
visualization, character sheets, session transcripts, and a resume button.
Requires static file serving infrastructure and new API endpoints.

### Sprint 2: "Self-Healing Systems" (2026-02-24)
Build skill self-validation (catch bugs like today's before execution),
error context enrichment (422s → actionable suggestions), and working memory
auto-flush with conflict detection. Makes Aria preventive, not reactive.

### Sprint 3: "The Infinite Chronicle" (2026-02-25)
Persistent RPG campaign memory in KG (Campaign/Scene entity types with
auto-relations), session state serialization, resume capability (close browser →
reopen → continue from exact combat turn), integration tests, and documentation.

---

## Ticket Summary

| Ticket | Title | Type | Sprint | Priority | LOC | Dependencies |
|--------|-------|------|--------|----------|-----|-------------|
| 001 | Static File Serving Infrastructure | FEAT | 1 | P0 | 45 | — |
| 002 | RPG Dashboard Single-File App | FEAT | 1 | P0 | 850 | 001, 003 |
| 003 | RPG Dashboard API Endpoints | FEAT | 1 | P0 | 140 | 004 |
| 004 | RPG Skill Dashboard Queries | FEAT | 1 | P0 | 95 | — |
| 005 | Skill Self-Validation Engine | FEAT | 2 | P0 | 180 | — |
| 006 | Error Context Enrichment Middleware | FEAT | 2 | P0 | 130 | — |
| 007 | Working Memory Auto-Flush & Conflicts | FEAT | 2 | P0 | 140 | — |
| 008 | Validation CLI & Pre-Flight Checks | CHORE | 2 | P1 | 55 | 005 |
| 009 | Error Enrichment Integration (Skills) | FIX | 2 | P1 | 40 | 006 |
| 010 | KG Campaign & Scene Entity Types | FEAT | 3 | P0 | 120 | 016 |
| 011 | Auto-Relation Generation Engine | FEAT | 3 | P0 | 150 | 010 |
| 012 | Session State Serialization & Resume | FEAT | 3 | P0 | 280 | 016 |
| 013 | Dashboard Resume Integration & Polish | FEAT | 3 | P0 | 180 | 012, 002 |
| 014 | Integration Test Suite | CHORE | 3 | P0 | 350 | 010–013, 016 |
| 015 | Final Documentation | CHORE | 3 | P1 | 400 | all |
| 016 | Session State Database Migration | CHORE | 3 | P0 | 35 | — |

## File Impact Map

```
src/api/
  __init__.py               (+25 lines)  # StaticFiles mount, RPG router, error middleware
  static/rpg/index.html     (new, ~970)  # Self-contained dashboard
  routers/rpg.py            (new, ~150)  # RPG dashboard API endpoints
  middleware/error_enrichment.py (new, 90)
  models/rpg.py             (new, ~60)   # Pydantic schemas

aria_skills/
  validator.py              (new, ~120)  # Skill self-validation engine
  base.py                   (+30)        # validate() method
  catalog.py                (+30)        # validate_all_skills()
  api_client/__init__.py    (+40)        # Error suggestion parsing
  knowledge_graph/__init__.py (+80)      # Campaign/Scene entities
  knowledge_graph/auto_relations.py (new, 100)
  rpg_campaign/__init__.py  (+115)       # Dashboard queries, resume
  rpg_campaign/session_state.py (new, 100)
  rpg_campaign/skill.json   (+90)        # New tool definitions
  rpg_pathfinder/skill.json (+20)        # auto_link param
  working_memory/__init__.py (+60)       # Auto-flush, conflicts

aria_mind/
  error_handler.py          (new, 50)    # Global exception → WM sync

tests/
  integration/test_rpg_flow.py (new, 250)
  conftest.py               (+50)

aria_memories/
  plans/SPRINT_MASTER_2026_Q1.md (new, 400)
```

## Deployment Notes

- Static files served from `src/api/static/` via FastAPI `StaticFiles`
- Docker bind-mount already includes `src/` — no compose changes needed
- After each sprint: `docker restart aria-api aria-engine`
- RPG Dashboard accessible at: `https://<ARIA_HOST>/rpg/` (resolve via env or Traefik)
- All new endpoints under `/api/rpg/` prefix
- **No hardcoded IPs/ports in code** — use `src/api/config.py` patterns (see Coding Standards)

## Rollback Procedures

Each sprint is independently revertable via git:
```bash
# Revert Sprint 3 only
git revert HEAD~1..HEAD  # if sprint 3 is last commit

# Revert to pre-sprint state
git checkout f0f753b  # commit before sprints (souvenir cleanup)
docker restart aria-api aria-engine
```
