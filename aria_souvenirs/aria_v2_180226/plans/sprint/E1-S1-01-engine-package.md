# S1-01: Create `aria_engine` Package Structure
**Epic:** E1 — Engine Core | **Priority:** P0 | **Points:** 2 | **Phase:** 1

## Problem
There is no `aria_engine/` package in the repository. The entire agent runtime currently depends on OpenClaw's Node.js gateway (`clawdbot` container at port 18789). To replace OpenClaw, we need a standalone Python package that provides the engine runtime.

## Root Cause
The project was originally built on OpenClaw as the primary orchestration runtime. No standalone engine package was ever created because OpenClaw handled session management, agent spawning, cron scheduling, and LLM routing. Now that we're phasing out OpenClaw, we need this foundational package.

## Fix
Create the following files:

### `aria_engine/__init__.py`
```python
"""
Aria Engine — Standalone Python runtime for Aria Blue.

Replaces OpenClaw with native:
- LLM gateway (direct litellm SDK)
- Chat engine (session lifecycle + streaming)
- Scheduler (APScheduler + PostgreSQL)
- Agent pool (async task management)
- Context manager (sliding window + importance)
"""

__version__ = "2.0.0"

from aria_engine.config import EngineConfig
from aria_engine.exceptions import EngineError, LLMError, SessionError, SchedulerError

__all__ = ["EngineConfig", "EngineError", "LLMError", "SessionError", "SchedulerError"]
```

### `aria_engine/config.py`
```python
"""Engine configuration — all settings from environment + models.yaml."""

import os
from dataclasses import dataclass, field
from typing import Any
from pathlib import Path

@dataclass
class EngineConfig:
    """Runtime configuration for Aria Engine."""
    
    # Database
    database_url: str = field(default_factory=lambda: os.environ.get(
        "DATABASE_URL", "postgresql://admin:admin@localhost:5432/aria_warehouse"
    ))
    
    # LLM
    litellm_base_url: str = field(default_factory=lambda: os.environ.get(
        "LITELLM_BASE_URL", "http://litellm:4000/v1"
    ))
    litellm_master_key: str = field(default_factory=lambda: os.environ.get(
        "LITELLM_MASTER_KEY", ""
    ))
    default_model: str = "step-35-flash-free"
    default_temperature: float = 0.7
    default_max_tokens: int = 4096
    
    # Agent pool
    max_concurrent_agents: int = 5
    agent_context_limit: int = 50
    
    # Scheduler
    scheduler_enabled: bool = True
    heartbeat_interval_seconds: int = 3600
    
    # Paths
    models_yaml_path: str = field(default_factory=lambda: str(
        Path(__file__).parent.parent / "aria_models" / "models.yaml"
    ))
    soul_path: str = field(default_factory=lambda: str(
        Path(__file__).parent.parent / "aria_mind" / "soul"
    ))
    memories_path: str = field(default_factory=lambda: os.environ.get(
        "ARIA_MEMORIES_PATH", str(Path(__file__).parent.parent / "aria_memories")
    ))
    
    # WebSocket
    ws_ping_interval: int = 30
    ws_ping_timeout: int = 10
    
    @classmethod
    def from_env(cls) -> "EngineConfig":
        """Create config from environment variables."""
        return cls()
```

### `aria_engine/exceptions.py`
```python
"""Engine-specific exceptions."""

class EngineError(Exception):
    """Base exception for aria_engine."""
    pass

class LLMError(EngineError):
    """LLM gateway errors (model unavailable, timeout, etc.)."""
    pass

class SessionError(EngineError):
    """Session management errors."""
    pass

class SchedulerError(EngineError):
    """Scheduler errors (job execution, scheduling)."""
    pass

class AgentError(EngineError):
    """Agent pool errors (spawn, terminate, routing)."""
    pass

class ContextError(EngineError):
    """Context assembly errors."""
    pass

class ToolError(EngineError):
    """Tool calling errors."""
    pass
```

### Additional stub files
```
aria_engine/llm_gateway.py       — stub with class signature
aria_engine/chat_engine.py       — stub with class signature
aria_engine/context_manager.py   — stub with class signature
aria_engine/scheduler.py         — stub with class signature
aria_engine/agent_pool.py        — stub with class signature
aria_engine/session_manager.py   — stub with class signature
aria_engine/tool_registry.py     — stub with class signature
aria_engine/streaming.py         — stub with class signature
aria_engine/entrypoint.py        — stub with main()
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | aria_engine sits alongside Skills/Agents layer |
| 2 | .env for secrets (zero in code) | ✅ | All secrets from env vars via EngineConfig |
| 3 | models.yaml single source of truth | ✅ | Config loads models_yaml_path |
| 4 | Docker-first testing | ✅ | Must work in Docker container |
| 5 | aria_memories only writable path | ✅ | Engine reads configs, writes only to aria_memories |
| 6 | No soul modification | ✅ | Engine reads soul, never writes |

## Dependencies
None — this is the foundation ticket.

## Verification
```bash
# 1. Package imports correctly:
python -c "from aria_engine import EngineConfig; print(EngineConfig())"
# EXPECTED: EngineConfig(database_url='postgresql://...', ...)

# 2. All modules importable:
python -c "import aria_engine.config, aria_engine.exceptions, aria_engine.llm_gateway, aria_engine.chat_engine"
# EXPECTED: no ImportError

# 3. Exception hierarchy:
python -c "from aria_engine.exceptions import *; assert issubclass(LLMError, EngineError)"
# EXPECTED: no AssertionError
```

## Prompt for Agent
```
You are implementing the foundation package for Aria Engine — a standalone Python runtime that replaces OpenClaw.

FILES TO READ FIRST:
- aria_mind/__init__.py (lines 1-50 for package pattern)
- aria_skills/base.py (lines 1-50 for class structure patterns)
- aria_agents/base.py (lines 1-50 for dataclass patterns)
- pyproject.toml (for project metadata and Python version)

STEPS:
1. Create aria_engine/ directory at repo root
2. Create aria_engine/__init__.py with version, imports, __all__
3. Create aria_engine/config.py with EngineConfig dataclass
4. Create aria_engine/exceptions.py with exception hierarchy
5. Create stub files for all engine modules (llm_gateway, chat_engine, context_manager, scheduler, agent_pool, session_manager, tool_registry, streaming, entrypoint)
6. Each stub must have a docstring explaining its purpose and a TODO comment
7. Run verification commands

CONSTRAINTS TO OBEY:
- Constraint 2: All secrets from environment variables
- Constraint 3: models_yaml_path points to aria_models/models.yaml
- Constraint 5: Only write to aria_memories/

VERIFICATION: Run all 3 verification commands above.
```
