# S-52: Mount Engine Chat Router — Fix Aria Chat
**Epic:** E9 — Database Integration | **Priority:** P0 | **Points:** 5 | **Phase:** 1

## Problem

The Aria chat system is **completely non-functional**. The web UI at `/chat/` renders
(`src/web/templates/engine_chat.html`) and the API router exists
(`src/api/routers/engine_chat.py` — 467 lines), but:

1. The `engine_chat` router is **never mounted** in `src/api/main.py` (line 240–295).
   24 routers are imported and mounted, but `engine_chat` is absent.
2. `configure_engine()` (line 135 of `engine_chat.py`) is **never called** in the lifespan
   handler, so even if mounted, all endpoints would return 503 "Engine not initialized".
3. The router has a `register_engine_chat(app)` helper at line 453 with documentation
   saying "Called from src/api/main.py" — but this call was never added.

## Root Cause

`src/api/main.py` imports and mounts 24 routers (lines 240-292) but does NOT include:
```python
from routers.engine_chat import register_engine_chat, configure_engine
```

The `engine_chat.py` file uses module-level globals (`_chat_engine`, `_stream_manager`, etc.)
that must be initialized via `configure_engine()` before any endpoint can serve requests.

The lifespan handler (lines 38-87) runs `ensure_schema()`, `sync_skill_graph()`,
`run_skill_invocation_backfill()`, and `run_autoscorer_loop()` — but never initializes
the engine chat components.

## Fix

### Change 1: Mount the router in main.py

**File:** `src/api/main.py`, after line 263 (engine_sessions import):

BEFORE:
```python
from routers.engine_sessions import router as engine_sessions_router
```

AFTER:
```python
from routers.engine_sessions import router as engine_sessions_router
from routers.engine_chat import register_engine_chat, configure_engine
```

And after line 292 (engine_sessions mount):

BEFORE:
```python
app.include_router(engine_sessions_router)
```

AFTER:
```python
app.include_router(engine_sessions_router)

# Engine Chat — REST + WebSocket
register_engine_chat(app)
```

### Change 2: Initialize engine in lifespan

**File:** `src/api/main.py`, in the lifespan handler, after `ensure_schema()` block (~line 47):

Add engine initialization:
```python
    # Engine Chat initialization
    try:
        from aria_engine.config import EngineConfig
        from aria_engine.chat_engine import ChatEngine
        from aria_engine.streaming import StreamManager
        from aria_engine.context_manager import ContextManager
        from aria_engine.prompts import PromptAssembler
        from routers.engine_chat import configure_engine

        engine_config = EngineConfig()
        chat_engine = ChatEngine(config=engine_config)
        stream_manager = StreamManager(chat_engine=chat_engine)
        context_manager = ContextManager(config=engine_config)
        prompt_assembler = PromptAssembler(config=engine_config)
        configure_engine(
            config=engine_config,
            chat_engine=chat_engine,
            stream_manager=stream_manager,
            context_manager=context_manager,
            prompt_assembler=prompt_assembler,
        )
        print("✅ Engine Chat initialized")
    except Exception as e:
        print(f"⚠️  Engine Chat init failed (non-fatal): {e}")
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | Adding API layer route — correct layer |
| 2 | .env for secrets (zero in code) | ✅ | EngineConfig reads from env — no secrets in code |
| 3 | models.yaml single source of truth | ✅ | EngineConfig may reference models — must use models.yaml |
| 4 | Docker-first testing | ✅ | Must test via Docker Compose |
| 5 | aria_memories only writable path | ❌ | No file writes involved |
| 6 | No soul modification | ❌ | No soul files involved |

## Dependencies
- None — can be executed independently.
- S-57 depends on this (Web UI fix needs working API endpoints).

## Verification
```bash
# 1. Router is imported:
grep -n "engine_chat" src/api/main.py
# EXPECTED: import line + register_engine_chat(app) call

# 2. configure_engine called in lifespan:
grep -n "configure_engine" src/api/main.py
# EXPECTED: at least 2 matches (import + call)

# 3. API starts without error:
cd src/api && python -c "from main import app; print('OK')"
# EXPECTED: OK (no import errors)

# 4. Chat endpoints registered:
docker compose exec aria-api python -c "
from main import app
routes = [r.path for r in app.routes]
print('/api/engine/chat/sessions' in routes or any('/engine/chat' in str(r.path) for r in app.routes))
"
# EXPECTED: True

# 5. Chat session creation works:
curl -s -X POST http://localhost:8000/api/engine/chat/sessions \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"main","title":"Test"}' | python -m json.tool
# EXPECTED: JSON with session id, status "active"
```

## Prompt for Agent
Read these files first:
- `src/api/main.py` (all 296 lines)
- `src/api/routers/engine_chat.py` (all 467 lines — especially lines 125-170 for configure_engine and lines 453-467 for register_engine_chat)
- `aria_engine/config.py` (first 50 lines — EngineConfig constructor)
- `aria_engine/chat_engine.py` (first 50 lines — ChatEngine constructor)
- `aria_engine/streaming.py` (first 50 lines — StreamManager constructor)
- `aria_engine/context_manager.py` (first 50 lines — ContextManager constructor)
- `aria_engine/prompts.py` (first 50 lines — PromptAssembler constructor)

Steps:
1. In `src/api/main.py`, add `from routers.engine_chat import register_engine_chat, configure_engine` after the engine_sessions import (line ~263)
2. Add `register_engine_chat(app)` after the engine_sessions mount (line ~292)
3. In the lifespan handler, after the ensure_schema block (~line 47), add engine initialization with try/except (non-fatal on failure)
4. Verify constructors of EngineConfig, ChatEngine, StreamManager, ContextManager, PromptAssembler match the configure_engine signature
5. Run verification commands

Constraints: #1 (API layer), #2 (secrets from env), #3 (models.yaml), #4 (Docker test)
