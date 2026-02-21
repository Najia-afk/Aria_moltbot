# S-63→S-68 — Multi-Agent Orchestration Sprint

**Sprint**: S-63 through S-68 (6 tickets)  
**Grade**: AA+  
**Branch**: `feature/aria-v2-operation-independence`  
**Date**: 2025-01-27  

---

## Summary

Implements the 6 "Future Gap" tickets identified in S-62 (Roundtable Visualization & API Wiring). Delivers **swarm intelligence**, **slash commands**, **auto-escalation**, **WebSocket streaming**, **session auto-cleanup**, and **cron integration** — completing the multi-agent orchestration stack.

---

## Tickets Implemented

### S-63 — Chat `/roundtable` & `/swarm` Slash Commands ✅

**File**: `aria_engine/chat_engine.py`

- Added `SLASH_COMMANDS = {"/roundtable", "/swarm"}` detection
- `_handle_slash_command()` — intercepts `/roundtable <topic>` and `/swarm <topic>` in user messages
- `_get_auto_agents()` — queries `EngineAgentState` for top 4 enabled agents by `pheromone_score DESC`
- `_make_slash_response()` — formats orchestration results as Markdown (participants, rounds/iterations, synthesis/consensus)
- `set_roundtable()`, `set_swarm()`, `set_escalation_router()` — dependency injection methods called from `main.py` lifespan
- Slash check inserted **after** user message persistence, **before** LLM call — preserves message history

### S-64 — Auto-Escalation Routing ✅

**File**: `aria_engine/routing.py`

- `ESCALATION_PATTERNS` — 5 weighted regex patterns:
  - `roundtable|swarm|discuss|debate|deliberate` → weight 0.9
  - `compare|versus|pros.cons|trade.?off` → weight 0.7
  - `should we|strategy|decide|plan|approach` → weight 0.6
  - Multi-domain cross-references → weight 0.3
  - `opinion|perspective|viewpoint|think about` → weight 0.4
- `ESCALATION_THRESHOLD = 0.6`
- `assess_escalation()` method on `EngineRouter`:
  - Returns `{should_escalate, score, mode, reason, matching_domains}`
  - Mode detection: "swarm" for decision keywords (`should|decide|choose`), "roundtable" for analysis
  - Cross-domain bonus: +0.15 per matching specialty domain beyond the first

### S-65 — WebSocket Streaming Roundtable ✅

**Files**: `aria_engine/roundtable.py`, `src/api/routers/engine_roundtable.py`

- Added `on_turn: Any = None` callback parameter to `Roundtable.discuss()` — invoked after each round's turns complete
- `ws_router = APIRouter(tags=["Engine Roundtable WebSocket"])` — separate router for WS routes
- `@ws_router.websocket("/ws/roundtable")` — single WS endpoint handling both modes:
  - Client sends: `{"mode": "roundtable"|"swarm", "topic": "...", "agent_ids": [...], ...}`
  - Server streams: `{"type": "turn"|"vote"|"synthesis"|"consensus"|"done"|"error", ...}`
- `_handle_roundtable_ws()` — uses `on_turn` callback to stream each turn as it completes
- `_handle_swarm_ws()` — uses `on_vote` callback to stream each vote as it's cast
- `register_roundtable(app)` — registers both REST + WS routers in one call

### S-66 — Swarm Orchestration Engine ✅

**File**: `aria_engine/swarm.py` (NEW — ~580 lines)

- `SwarmOrchestrator` class — emergent collective intelligence via pheromone-weighted voting
- `SwarmVote` dataclass: `agent_id`, `vote` (agree/disagree/extend/pivot), `confidence`, `reasoning`, `iteration`, `duration_ms`
- `SwarmResult` dataclass: `session_id`, `topic`, `votes`, `consensus`, `consensus_score`, `converged`, `iterations`, `trail`, `participants`, `duration_ms`
- `execute()` — iterative convergence loop:
  1. Gather pheromone weights from `EngineAgentState`
  2. Run agents concurrently via `asyncio.TaskGroup`
  3. Parse `[VOTE: agree|disagree|extend|pivot]` and `[CONFIDENCE: 0.0-1.0]` tags (with heuristic fallback)
  4. Calculate consensus: 60% agreement ratio + 40% weighted confidence
  5. If threshold met → converge; else iterate (up to `max_iterations`)
  6. Build stigmergy trail with ★/●/○ pheromone markers
  7. Highest-scoring agent synthesizes final consensus
- DB persistence: sessions with `session_type='swarm'`, votes as `role='swarm-{iteration}'`, consensus as `role='consensus'`
- Constants: `DEFAULT_MAX_ITERATIONS=5`, `DEFAULT_CONSENSUS_THRESHOLD=0.7`, `MIN_AGENTS=2`, `MAX_AGENTS=12`
- REST endpoints (in `engine_roundtable.py`):
  - `POST /engine/roundtable/swarm` — synchronous swarm execution
  - `POST /engine/roundtable/swarm/async` — background swarm (async key)
  - `GET /engine/roundtable/swarm/status/{key}` — check async swarm status
  - `GET /engine/roundtable/swarm/{session_id}` — get swarm result detail

### S-67 — Session Auto-Cleanup ✅

**Files**: `src/api/main.py`, `src/api/routers/engine_sessions.py`

- **Background task**: `_session_cleanup_loop()` in `main.py` lifespan — runs every 6 hours, prunes sessions >30 days old
  - Leverages existing `NativeSessionManager.prune_old_sessions(days, dry_run)`
  - Graceful shutdown via `asyncio.CancelledError`
- **REST endpoint**: `POST /engine/sessions/cleanup?days=30&dry_run=true`
  - `dry_run=true` (default) for safe preview, `dry_run=false` to execute
  - Returns `{pruned_count, message_count, dry_run}`

### S-68 — Roundtable Cron Integration ✅

**File**: `aria_mind/cron_jobs.yaml`

- `session_cleanup` — daily at 05:00 UTC, calls `POST /api/engine/sessions/cleanup?days=30&dry_run=false`
- `roundtable_architecture_review` — weekly Wednesday at 03:00 UTC, auto-starts 3-round architecture roundtable with top 4 agents by pheromone score

---

## Bug Fixes

### Constructor Mismatch in main.py (Critical)

- **`AgentPool(async_engine, engine_cfg)`** was passing args in wrong order → fixed to `AgentPool(engine_cfg, async_engine)`
  - `AgentPool.__init__` signature: `(config: EngineConfig, db_engine: AsyncEngine, llm_gateway=None)`
- **`EngineRouter(async_engine, engine_cfg)`** was passing 2 args to 1-arg constructor → fixed to `EngineRouter(async_engine)`
  - `EngineRouter.__init__` signature: `(db_engine: AsyncEngine)`

---

## Frontend Updates

**File**: `src/web/templates/engine_roundtable.html`

- **Mode Toggle**: Roundtable ↔ Swarm switch button in Start tab
- **Swarm Form Fields**: Max iterations selector (3/5/7/10), consensus threshold selector (50%–90%)
- **Consensus Gauge**: Horizontal progress bar with color gradient (red→yellow→green), percentage display, iteration count, convergence status, dominant vote
- **History Type Column**: Shows 🔄 Roundtable or 🐝 Swarm badge per session
- **Stats Bar**: Added "Swarms" counter next to "Roundtables"

---

## Wiring (main.py)

1. Import `configure_swarm`, `register_roundtable` from `engine_roundtable`
2. Create `SwarmOrchestrator(async_engine, _rt_pool, _rt_router)` in lifespan
3. Call `configure_swarm(_swarm)` to inject into router DI
4. Call `register_roundtable(app)` instead of `app.include_router(engine_roundtable_router)` — includes both REST + WS routers
5. Inject orchestrators into ChatEngine: `chat_engine.set_roundtable(_roundtable)`, `.set_swarm(_swarm)`, `.set_escalation_router(_rt_router)`
6. Background tasks: sentiment auto-scorer + session cleanup, both with graceful shutdown

---

## Files Changed

| File | Action | Lines |
|------|--------|-------|
| `aria_engine/swarm.py` | **NEW** | ~580 |
| `aria_engine/chat_engine.py` | Modified | +120 (slash commands, injection) |
| `aria_engine/routing.py` | Modified | +92 (escalation patterns) |
| `aria_engine/roundtable.py` | Modified | +11 (on_turn callback) |
| `src/api/routers/engine_roundtable.py` | Modified | +374 (swarm endpoints, WS, register) |
| `src/api/routers/engine_sessions.py` | Modified | +20 (cleanup endpoint) |
| `src/api/main.py` | Modified | +35 (swarm init, wiring, cleanup task) |
| `src/web/templates/engine_roundtable.html` | Modified | +110 (swarm UI, consensus gauge) |
| `aria_mind/cron_jobs.yaml` | Modified | +18 (2 cron jobs) |

---

## Test Results

```
461 passed, 8 skipped, 0 failures
```

Skips: LLM model unavailable (Moonshot reasoning_content), embedding service, test-order dependencies. Zero regression.

---

## New API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/engine/roundtable/swarm` | Start synchronous swarm decision |
| POST | `/engine/roundtable/swarm/async` | Start background swarm |
| GET | `/engine/roundtable/swarm/status/{key}` | Check async swarm status |
| GET | `/engine/roundtable/swarm/{session_id}` | Get swarm result detail |
| POST | `/engine/sessions/cleanup` | Prune stale sessions |
| WS | `/ws/roundtable` | Stream roundtable/swarm in real-time |

---

## Architecture

```
User types "/roundtable optimise caching"
              │
              ▼
    ChatEngine._handle_slash_command()
              │
    ┌─────────┴──────────┐
    │ /roundtable        │ /swarm
    ▼                    ▼
  Roundtable.discuss()  SwarmOrchestrator.execute()
    │ on_turn callback   │ on_vote callback
    ▼                    ▼
  WebSocket streams     WebSocket streams
  each turn live        each vote live
              │
              ▼
    _make_slash_response() → formatted Markdown

Auto-escalation (passive):
  EngineRouter.assess_escalation(message)
    → {should_escalate: true, mode: "swarm", score: 0.85}
    → ChatEngine can optionally auto-trigger

Background:
  _session_cleanup_loop() → every 6h, prune >30d sessions
  Cron: roundtable_architecture_review → weekly Wed 03:00 UTC
  Cron: session_cleanup → daily 05:00 UTC
```

---

## Hard Constraints ✓

1. ✅ No `os.system()` / `subprocess` — all async ORM
2. ✅ No plaintext secrets — all via env vars / EngineConfig
3. ✅ All new tables use `aria_engine` schema
4. ✅ Every endpoint has error handling (try/except, HTTPException)
5. ✅ No breaking changes to existing API contracts
6. ✅ Tests green: 461 passed, 8 skipped, 0 failures
