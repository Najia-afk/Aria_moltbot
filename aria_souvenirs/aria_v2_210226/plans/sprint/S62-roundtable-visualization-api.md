# S-62: Roundtable Visualization & API Wiring
**Epic:** E12 — Multi-Agent Orchestration UI | **Priority:** P0 | **Points:** 8 | **Phase:** 1

## Problem
The `Roundtable` engine class ([aria_engine/roundtable.py](aria_engine/roundtable.py), 575 lines) is
**fully implemented** with parallel `TaskGroup` execution, N-round structured discussions
(EXPLORE → WORK → VALIDATE), synthesis agent, DB persistence, and pheromone score updates.

However it is **completely disconnected** from the rest of the system:
- No API endpoints expose it — no router imports it
- No frontend page displays roundtable sessions or turns
- No route in the nav bar links to roundtable
- Session auto-management is missing — nothing creates, archives, or lists roundtable sessions
- The `ChatEngine` never triggers a roundtable (no `/roundtable` command, no auto-escalation)
- Swarm is **concept-only** — `agent_type='swarm'` is a DB label with zero behavioral code

## Root Cause
The roundtable backend was built during the engine extraction (S4 sprint) but the API layer
and frontend were never wired. The `Roundtable` class constructor needs `(db_engine, AgentPool,
EngineRouter)` which were not instantiated during app startup. No REST router was created
to call `roundtable.discuss()` or `roundtable.list_roundtables()`.

## 6 Hard Constraints Check
| # | Constraint | Status |
|---|-----------|--------|
| 1 | 5-layer architecture (soul → engine → skills → api → web) | ✅ `aria_engine/roundtable.py` → `src/api/routers/engine_roundtable.py` → `src/web/templates/engine_roundtable.html` |
| 2 | Secrets in .env only | ✅ No new secrets needed |
| 3 | models.yaml single source for LLM | ✅ Uses existing agent pool which reads models from DB |
| 4 | Docker-first | ✅ All new code runs inside existing `aria-api` + `aria-web` containers |
| 5 | aria_memories/ only writable path | ✅ No new file writes — all state in PostgreSQL |
| 6 | Soul files read-only | ✅ No soul modifications |

## Fix — Implemented

### 1. New file: `src/api/routers/engine_roundtable.py`

**452 lines.** Full REST API router for roundtable discussions.

**Endpoints:**

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/engine/roundtable` | Start a synchronous roundtable (waits for completion) |
| `POST` | `/api/engine/roundtable/async` | Start a background roundtable (returns immediately) |
| `GET` | `/api/engine/roundtable` | List roundtable sessions (paginated) |
| `GET` | `/api/engine/roundtable/agents/available` | List agents available for participation |
| `GET` | `/api/engine/roundtable/status/{key}` | Poll async roundtable status |
| `GET` | `/api/engine/roundtable/{session_id}` | Get full roundtable detail (turns + synthesis) |
| `GET` | `/api/engine/roundtable/{session_id}/turns` | Get just turns (lightweight for polling) |
| `DELETE` | `/api/engine/roundtable/{session_id}` | End/archive a roundtable |

**Key design decisions:**
- Route order: `/agents/available` and `/status/{key}` registered **before** `/{session_id}`
  to prevent FastAPI path parameter collision
- `configure_roundtable()` DI pattern matches existing `configure_engine()` pattern
- In-memory `_completed` cache for recently finished roundtables (DB fallback for older ones)
- Background task support via `BackgroundTasks` for long-running discussions
- All DB queries use `aria_engine.chat_sessions` and `aria_engine.chat_messages` (correct schema)

```python
class StartRoundtableRequest(BaseModel):
    topic: str = Field(..., min_length=2, max_length=2000)
    agent_ids: list[str] = Field(..., min_length=2, max_length=10)
    rounds: int = Field(default=3, ge=1, le=10)
    synthesizer_id: str = Field(default="main")
    agent_timeout: int = Field(default=60, ge=10, le=300)
    total_timeout: int = Field(default=300, ge=30, le=900)
```

### 2. New file: `src/web/templates/engine_roundtable.html`

**620 lines.** Full roundtable visualization page with 3 tabs.

**Tab 1 — Start:**
- Agent picker with color-coded chips (from `/agents/available` endpoint)
- Topic textarea, round selector, synthesizer dropdown
- Start button with running status indicator

**Tab 2 — Visualize:** (uses skill_graph's vis-network pattern)
- **Force graph** (vis.js Network): Central topic node → agent nodes (circle layout) →
  round turn nodes (diamond) → synthesis star node. Edges show discussion flow.
- **Participation bar chart** (Chart.js): Turns per agent with agent colors
- **Response time line chart** (Chart.js): Duration per agent per round
- **Turn-by-turn timeline**: Color-coded cards with round dividers (EXPLORE/WORK/VALIDATE phases)
- **Synthesis box**: Green-bordered card showing the synthesizer's final answer

**Tab 3 — History:**
- Data table with all past roundtables (topic, agents, turn count, date)
- Click to load any historical roundtable into the Visualize tab
- Delete button to archive

**Visualization reuses patterns from:**
- [skill_graph.html](src/web/templates/skill_graph.html) — vis-network force graph, node inspector, legend
- [skill_stats.html](src/web/templates/skill_stats.html) — pathfinding decision graph, Chart.js charts, tabs

### 3. Modified: `src/api/main.py`

**Changes:**
- Import `engine_roundtable_router` and `configure_roundtable` (both relative + fallback import blocks)
- Register `app.include_router(engine_roundtable_router)` alongside other routers
- In lifespan: instantiate `AgentPool`, `EngineRouter`, `Roundtable`, call `configure_roundtable()`
- Startup log now shows: `✅ Aria Engine initialized (chat + streaming + agents + roundtable)`

```python
# In lifespan, after engine init:
from aria_engine.roundtable import Roundtable
from aria_engine.agent_pool import AgentPool
from aria_engine.routing import EngineRouter

_rt_pool = AgentPool(async_engine, engine_cfg)
_rt_router = EngineRouter(async_engine, engine_cfg)
_roundtable = Roundtable(async_engine, _rt_pool, _rt_router)
configure_roundtable(_roundtable, async_engine)
```

### 4. Modified: `src/web/app.py`

**Changes:**
- Added `/roundtable`, `/roundtable/`, `/roundtable/<session_id>` routes → `engine_roundtable.html`

### 5. Modified: `src/web/templates/base.html`

**Changes:**
- Added 🔄 Roundtable link to Operations nav dropdown (between Chat and Heartbeat)
- Added `/roundtable` to the Operations dropdown active state check

## Architecture Flow

```
User clicks "Start Roundtable" on /roundtable page
  → POST /api/engine/roundtable { topic, agent_ids, rounds, synthesizer_id }
    → engine_roundtable.py::start_roundtable()
      → Roundtable.discuss(topic, agent_ids, rounds)
        → _create_session() → INSERT aria_engine.chat_sessions (session_type='roundtable')
        → for round 1..N:
            → _run_round() → asyncio.TaskGroup → all agents in parallel
              → AgentPool.process_with_agent() → LLMGateway → response
              → _persist_message() → INSERT aria_engine.chat_messages
        → _synthesize() → synthesizer agent combines all turns
        → update pheromone scores for all participants
      ← RoundtableResult { turns, synthesis, duration_ms }
    ← JSON response with full result
  → Frontend renders:
      vis.js force graph (agents ↔ turns ↔ synthesis)
      Chart.js participation + duration charts
      Turn-by-turn timeline with round phase dividers
```

## Files Changed

| File | Action | Lines |
|------|--------|-------|
| `src/api/routers/engine_roundtable.py` | **NEW** | 452 |
| `src/web/templates/engine_roundtable.html` | **NEW** | 620 |
| `src/api/main.py` | Modified | +25 (imports + lifespan init + router registration) |
| `src/web/app.py` | Modified | +7 (Flask route) |
| `src/web/templates/base.html` | Modified | +4 (nav link + active check) |

## Tests

```
463 passed, 0 failed, 8 skipped (95s)
```

No regressions. The single pre-existing `test_get_agent_metrics` flake (depends on running Docker
services) is unrelated and was already intermittent.

## Remaining Gaps (Future Sprint Tickets)

| # | Gap | Ticket |
|---|-----|--------|
| 1 | **ChatEngine → Roundtable trigger** | S-63: Add `/roundtable` slash command in chat to spawn a roundtable from conversation |
| 2 | **Auto-escalation routing** | S-64: EngineRouter logic to detect "this question needs multiple perspectives" and auto-escalate to roundtable |
| 3 | **WebSocket streaming for roundtable** | S-65: Stream turns in real-time via WS as agents respond (instead of waiting for full completion) |
| 4 | **Swarm orchestration engine** | S-66: Actual swarm topology, emergent behavior, pheromone-based swarm routing (currently label-only) |
| 5 | **Session auto-cleanup** | S-67: Background task to archive roundtable sessions older than N days, compress turn content |
| 6 | **Roundtable cron integration** | S-68: Schedule recurring roundtables via cron (e.g., daily architecture review) |

## Verification

1. Navigate to `http://localhost:8080/roundtable`
2. Agents load in the picker from `/api/engine/roundtable/agents/available`
3. Select 2+ agents, enter a topic, click Start
4. After completion: force graph renders, synthesis box shows, timeline populates
5. History tab lists all past roundtables
6. Click any history row → loads into Visualize tab
7. API docs at `http://localhost:8080/api/docs` show all 8 roundtable endpoints
