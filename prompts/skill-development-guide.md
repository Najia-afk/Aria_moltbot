# Aria Skill Development Guide

> Complete reference for creating skills for Aria's cognitive architecture, including the Python implementation (`aria_skills`) and OpenClaw manifests (`openclaw_skills`).

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Creating a Python Skill](#creating-a-python-skill)
3. [Creating an OpenClaw Manifest](#creating-an-openclaw-manifest)
4. [Agent Integration](#agent-integration)
5. [Mind Integration](#mind-integration)
6. [Testing & Verification](#testing--verification)
7. [Deployment Checklist](#deployment-checklist)
8. [Best Practices](#best-practices)
9. [Reference: Existing Skills](#reference-existing-skills)

---

## Architecture Overview

Aria's skill system has two components that work together:

```
┌────────────────────────────────────────────────────────────────┐
│                         OpenClaw Brain                         │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    openclaw_skills/                       │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │  │
│  │  │ skill.json  │  │ skill.json  │  │ skill.json  │ ...   │  │
│  │  │  SKILL.md   │  │  SKILL.md   │  │  SKILL.md   │       │  │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘       │  │
│  └─────────┼────────────────┼────────────────┼──────────────┘  │
│            │                │                │                  │
│            ▼                ▼                ▼                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                      aria_skills/                         │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │  │
│  │  │  llm.py     │  │ database.py │  │  health.py  │ ...   │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘       │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────┘
```

### Component Roles

| Component | Location | Purpose |
|-----------|----------|---------|
| **Python Skills** | `aria_skills/` | Actual implementation logic |
| **OpenClaw Manifests** | `openclaw_skills/` | Tool definitions for LLM to discover and invoke |
| **Skill Registry** | `aria_skills/registry.py` | Runtime skill loading and management |
| **Agents** | `aria_agents/` | Orchestrate skills to accomplish tasks |
| **Mind** | `aria_mind/` | Cognitive layer that decides when/how to use skills |

---

## Creating a Python Skill

### Step 1: Create the Skill File

Create a new file in `aria_skills/`:

```python
# aria_skills/my_skill.py

"""
My Skill - Description of what this skill does.

This skill provides functionality for [purpose].

Config:
    api_url: Base API URL for the service
    api_key: API authentication key (use env:MY_API_KEY)
    timeout: Request timeout in seconds (default: 30)
"""

from typing import Any, Dict, List, Optional
from datetime import datetime

import httpx

from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus
from aria_skills.registry import SkillRegistry


@SkillRegistry.register
class MySkill(BaseSkill):
    """
    Skill for [purpose].
    
    Provides:
    - my_action: Do the main thing
    - my_query: Query for data
    - my_status: Check status
    """
    
    def __init__(self, config: SkillConfig):
        super().__init__(config)
        # Initialize from config with defaults
        self._api_url = config.config.get("api_url", "http://localhost:8000")
        self._timeout = config.config.get("timeout", 30)
        self._token: Optional[str] = None
    
    @property
    def name(self) -> str:
        """Unique skill identifier - must match module name."""
        return "my_skill"
    
    @property
    def _headers(self) -> dict:
        """Standard headers for API requests."""
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }
    
    async def initialize(self) -> bool:
        """
        Initialize the skill.
        
        - Load credentials from environment
        - Validate configuration
        - Test connectivity
        
        Returns:
            True if initialization successful, False otherwise
        """
        # Get API key from config (supports env:VAR_NAME syntax)
        self._token = self._get_env_value("api_key")
        
        if not self._token:
            self.logger.error("No api_key configured for my_skill")
            self._status = SkillStatus.UNAVAILABLE
            return False
        
        # Verify connectivity
        status = await self.health_check()
        return status == SkillStatus.AVAILABLE
    
    async def health_check(self) -> SkillStatus:
        """
        Check if the skill's external service is reachable.
        
        Returns:
            SkillStatus indicating availability
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self._api_url}/health",
                    headers=self._headers,
                    timeout=10,
                )
                
                if response.status_code == 200:
                    self._status = SkillStatus.AVAILABLE
                elif response.status_code == 429:
                    self._status = SkillStatus.RATE_LIMITED
                else:
                    self.logger.warning(f"Health check returned {response.status_code}")
                    self._status = SkillStatus.ERROR
                    
        except httpx.TimeoutException:
            self.logger.error("Health check timed out")
            self._status = SkillStatus.ERROR
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            self._status = SkillStatus.ERROR
            
        return self._status
    
    # ─────────────────────────────────────────────────────────────
    # Tool Methods (exposed to OpenClaw)
    # ─────────────────────────────────────────────────────────────
    
    async def my_action(
        self,
        input_data: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> SkillResult:
        """
        Perform the main action.
        
        Args:
            input_data: The input to process
            options: Optional configuration dict
            
        Returns:
            SkillResult with success/failure and data
        """
        # Always check availability first
        if not self.is_available:
            return SkillResult.fail("Skill not available")
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self._api_url}/action",
                    headers=self._headers,
                    json={
                        "input": input_data,
                        "options": options or {},
                    },
                    timeout=self._timeout,
                )
                
                if response.status_code == 200:
                    self._log_usage("my_action", True)
                    return SkillResult.ok(response.json())
                elif response.status_code == 429:
                    self._status = SkillStatus.RATE_LIMITED
                    return SkillResult.fail("Rate limited - try again later")
                else:
                    self._log_usage("my_action", False)
                    return SkillResult.fail(f"API error: {response.status_code}")
                    
        except Exception as e:
            self._log_usage("my_action", False)
            self.logger.error(f"my_action failed: {e}")
            return SkillResult.fail(str(e))
    
    async def my_query(
        self,
        query: str,
        limit: int = 10,
    ) -> SkillResult:
        """
        Query for data.
        
        Args:
            query: Search query string
            limit: Maximum results to return
            
        Returns:
            SkillResult with list of results
        """
        if not self.is_available:
            return SkillResult.fail("Skill not available")
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self._api_url}/query",
                    headers=self._headers,
                    params={"q": query, "limit": limit},
                    timeout=self._timeout,
                )
                
                if response.status_code == 200:
                    self._log_usage("my_query", True)
                    return SkillResult.ok(response.json())
                else:
                    self._log_usage("my_query", False)
                    return SkillResult.fail(f"Query failed: {response.status_code}")
                    
        except Exception as e:
            self._log_usage("my_query", False)
            return SkillResult.fail(str(e))
    
    async def my_status(self) -> SkillResult:
        """
        Get current status information.
        
        Returns:
            SkillResult with status dict
        """
        return SkillResult.ok({
            "status": self._status.value,
            "operations": self._operation_count,
            "errors": self._error_count,
            "last_used": self._last_used.isoformat() if self._last_used else None,
        })
```

### Step 2: Register the Skill

Add to `aria_skills/__init__.py`:

```python
# Add import
from aria_skills.my_skill import MySkill

# Add to __all__
__all__ = [
    # ... existing skills
    "MySkill",
]
```

### Step 3: Add Configuration to TOOLS.md

Add a YAML block to `aria_mind/TOOLS.md`:

```yaml
my_skill:
  enabled: true
  api_url: http://localhost:8000
  api_key: env:MY_API_KEY
  timeout: 30
```

---

## Skill Base Class Reference

### Required Abstract Methods

| Method | Signature | Purpose |
|--------|-----------|---------|
| `name` | `@property -> str` | Unique identifier (must match module name) |
| `initialize()` | `async -> bool` | Setup, validation, connectivity test |
| `health_check()` | `async -> SkillStatus` | Check external service availability |

### Inherited Functionality

| Member | Type | Purpose |
|--------|------|---------|
| `config` | `SkillConfig` | Access configuration |
| `logger` | `Logger` | Pre-configured logger |
| `_status` | `SkillStatus` | Current status |
| `is_available` | `bool` | True if status is AVAILABLE |
| `status` | `SkillStatus` | Property: current status |
| `_log_usage()` | method | Track operation metrics |
| `_get_env_value()` | method | Resolve `env:VAR_NAME` configs |
| `get_stats()` | method | Return usage statistics |

### SkillStatus Enum

```python
class SkillStatus(Enum):
    AVAILABLE = "available"      # Ready to use
    UNAVAILABLE = "unavailable"  # Missing config/credentials
    RATE_LIMITED = "rate_limited" # Temporarily blocked
    ERROR = "error"              # Persistent failure
```

### SkillResult Dataclass

```python
@dataclass
class SkillResult:
    success: bool
    data: Any = None
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    @classmethod
    def ok(cls, data: Any) -> "SkillResult"
    
    @classmethod
    def fail(cls, error: str) -> "SkillResult"
```

---

## Creating an OpenClaw Manifest

### Folder Structure

```
openclaw_skills/
└── aria-my-skill/
    ├── skill.json    # Machine-readable manifest
    └── SKILL.md      # Human-readable documentation
```

### Step 1: Create skill.json

```json
{
  "name": "aria-my-skill",
  "version": "1.0.0",
  "description": "Description of what this skill does.",
  "author": "Aria Team",
  "tools": [
    {
      "name": "my_action",
      "description": "Perform the main action. Use this when you need to [purpose].",
      "parameters": {
        "type": "object",
        "properties": {
          "input_data": {
            "type": "string",
            "description": "The input text to process"
          },
          "options": {
            "type": "object",
            "description": "Optional configuration object"
          }
        },
        "required": ["input_data"]
      }
    },
    {
      "name": "my_query",
      "description": "Query for data matching the search criteria.",
      "parameters": {
        "type": "object",
        "properties": {
          "query": {
            "type": "string",
            "description": "Search query string"
          },
          "limit": {
            "type": "integer",
            "description": "Maximum results to return (default: 10)"
          }
        },
        "required": ["query"]
      }
    },
    {
      "name": "my_status",
      "description": "Get current skill status and statistics.",
      "parameters": {
        "type": "object",
        "properties": {}
      }
    }
  ],
  "run": "python3 /root/.openclaw/workspace/skills/run_skill.py my_skill {{tool}} '{{args_json}}'"
}
```

### Step 2: Create SKILL.md

```markdown
---
name: aria-my-skill
description: Brief description of the skill
metadata: {"openclaw": {"emoji": "🔧", "requires": {"env": ["MY_API_KEY"]}, "primaryEnv": "MY_API_KEY"}}
---

# My Skill 🔧

This skill provides [purpose] for Aria Blue.

## Usage

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py my_skill <function> '<args_json>'
```

## Functions

### my_action
Perform the main action.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py my_skill my_action '{"input_data": "example"}'
```

**Parameters:**
- `input_data` (required): The input text to process
- `options`: Optional configuration object

### my_query
Query for data.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py my_skill my_query '{"query": "search term", "limit": 5}'
```

**Parameters:**
- `query` (required): Search query string
- `limit`: Maximum results (default: 10)

### my_status
Get current status.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py my_skill my_status '{}'
```

## Configuration

Required environment variables:
- `MY_API_KEY`: API authentication key

## Python Module

Implementation: `aria_skills/my_skill.py`
```

### Parameter Types Reference

| JSON Type | Python Type | Example |
|-----------|-------------|---------|
| `string` | `str` | `"hello"` |
| `integer` | `int` | `42` |
| `number` | `float` | `3.14` |
| `boolean` | `bool` | `true` |
| `array` | `List` | `["a", "b"]` |
| `object` | `Dict` | `{"key": "value"}` |

### Array Items Example

```json
{
  "messages": {
    "type": "array",
    "items": {
      "type": "object",
      "properties": {
        "role": { "type": "string" },
        "content": { "type": "string" }
      }
    },
    "description": "List of chat messages"
  }
}
```

### Enum Constraints Example

```json
{
  "status": {
    "type": "string",
    "enum": ["active", "completed", "paused", "all"],
    "description": "Filter by status"
  }
}
```

---

## Agent Integration

Skills are made available to agents through the `AgentCoordinator`:

### How Agents Access Skills

```python
# In an agent's process method:
async def process(self, message: str, **kwargs) -> AgentMessage:
    # Use skill via registry
    skill = self._skills.get("my_skill")
    if skill and skill.is_available:
        result = await skill.my_action(input_data=message)
        if result.success:
            return AgentMessage(
                role="assistant",
                content=result.data,
                agent_id=self.config.agent_id,
            )
```

### Skill Permission Model

Agents declare which skills they can use in their config:

```yaml
# In aria_mind/AGENTS.md
## my_agent
- skills: [my_skill, database, llm]
```

### Agent Lifecycle with Skills

```
Startup Sequence:
1. SkillRegistry.load_from_config("TOOLS.md")
2. AgentCoordinator(registry)
3. coordinator.load_from_file("AGENTS.md")
4. coordinator.initialize_all()  # Links skills to agents
5. coordinator.set_skills(registry)  # Injects registry
```

---

## Mind Integration

The `AriaMind` orchestrates skills through cognition:

### Cognition Flow

```
User Input
    │
    ▼
┌─────────────────────┐
│ Boundary Check      │ ← Soul validates request
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│ Memory Store        │ ← Short-term memory
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│ Agent Coordinator   │ ← Routes to appropriate agent
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│ Skill Execution     │ ← Agent calls skill methods
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│ Response            │ ← Logged to memory
└─────────────────────┘
```

### Mind Integration Points

```python
# aria_mind/cognition.py

class Cognition:
    def set_skill_registry(self, registry: SkillRegistry):
        """Inject skill registry for fallback processing."""
        self._skills = registry
    
    def set_agent_coordinator(self, coordinator: AgentCoordinator):
        """Inject agent coordinator for delegated processing."""
        self._agents = coordinator
```

### Direct Skill Usage (Fallback)

When agents are unavailable, cognition can use skills directly:

```python
async def _fallback_process(self, message: str) -> str:
    llm = self._skills.get("ollama") or self._skills.get("moonshot")
    if llm:
        result = await llm.generate(prompt=message)
        return result.data if result.success else result.error
    return "No LLM skill available"
```

---

## Testing & Verification

### Step 1: Unit Test

Create `tests/test_my_skill.py`:

```python
"""Tests for MySkill."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from aria_skills.base import SkillConfig, SkillStatus
from aria_skills.my_skill import MySkill


@pytest.fixture
def skill_config():
    return SkillConfig(
        name="my_skill",
        enabled=True,
        config={
            "api_url": "http://localhost:8000",
            "api_key": "test-key",
            "timeout": 10,
        },
    )


@pytest.fixture
def skill(skill_config):
    return MySkill(skill_config)


class TestMySkill:
    
    def test_name(self, skill):
        assert skill.name == "my_skill"
    
    @pytest.mark.asyncio
    async def test_initialize_success(self, skill):
        with patch.object(skill, 'health_check', return_value=SkillStatus.AVAILABLE):
            result = await skill.initialize()
            assert result is True
            assert skill._status == SkillStatus.AVAILABLE
    
    @pytest.mark.asyncio
    async def test_initialize_no_api_key(self, skill_config):
        skill_config.config["api_key"] = None
        skill = MySkill(skill_config)
        result = await skill.initialize()
        assert result is False
        assert skill._status == SkillStatus.UNAVAILABLE
    
    @pytest.mark.asyncio
    async def test_my_action_success(self, skill):
        skill._status = SkillStatus.AVAILABLE
        skill._token = "test-token"
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"result": "success"}
            
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )
            
            result = await skill.my_action(input_data="test")
            
            assert result.success is True
            assert result.data == {"result": "success"}
    
    @pytest.mark.asyncio
    async def test_my_action_unavailable(self, skill):
        skill._status = SkillStatus.UNAVAILABLE
        
        result = await skill.my_action(input_data="test")
        
        assert result.success is False
        assert "not available" in result.error
```

### Step 2: Integration Test

```python
# tests/test_integration.py

@pytest.mark.asyncio
async def test_skill_registration():
    """Verify skill registers with registry."""
    from aria_skills.registry import SkillRegistry
    
    # Registry should have my_skill after import
    assert "my_skill" in SkillRegistry.available_skills()
```

### Step 3: Run Tests

```bash
# Run all skill tests
pytest tests/test_my_skill.py -v

# Run with coverage
pytest tests/ --cov=aria_skills --cov-report=html
```

---

## Deployment Checklist

### Pre-Deployment

- [ ] Python skill file created in `aria_skills/`
- [ ] Skill imported and added to `__init__.py`
- [ ] Configuration added to `aria_mind/TOOLS.md`
- [ ] OpenClaw manifest created (`skill.json`)
- [ ] OpenClaw documentation created (`SKILL.md`)
- [ ] Unit tests written and passing
- [ ] Integration tests passing
- [ ] Environment variables documented
- [ ] No secrets in code (use `env:VAR_NAME`)

### Deployment Steps

```bash
# 1. Commit locally
git add .
git commit -m "feat: add my_skill for [purpose]"
git push origin main

# 2. SSH to server
ssh -i .\najia_mac_key najia@192.168.1.53

# 3. Deploy
cd ~/aria-blue
git pull origin main
cd stacks/brain
./deploy.sh rebuild

# 4. Verify
docker compose logs -f clawdbot | grep my_skill
```

### Post-Deployment Verification

```bash
# Test skill health
exec python3 /root/.openclaw/workspace/skills/run_skill.py my_skill my_status '{}'

# Check skill registration
exec python3 -c "from aria_skills import MySkill; print(MySkill)"
```

---

## Best Practices

### 1. Error Handling

```python
# Always wrap external calls
try:
    result = await external_api_call()
except httpx.TimeoutException:
    return SkillResult.fail("Request timed out")
except httpx.HTTPStatusError as e:
    return SkillResult.fail(f"HTTP error: {e.response.status_code}")
except Exception as e:
    self.logger.error(f"Unexpected error: {e}")
    return SkillResult.fail(str(e))
```

### 2. Rate Limiting

```python
from datetime import datetime, timedelta

class RateLimitedSkill(BaseSkill):
    POST_COOLDOWN_MINUTES = 30
    
    def __init__(self, config: SkillConfig):
        super().__init__(config)
        self._last_action_time: Optional[datetime] = None
    
    def _can_perform_action(self) -> tuple[bool, Optional[int]]:
        if self._last_action_time is None:
            return True, None
        
        elapsed = datetime.utcnow() - self._last_action_time
        if elapsed >= timedelta(minutes=self.POST_COOLDOWN_MINUTES):
            return True, None
        
        remaining = self.POST_COOLDOWN_MINUTES - int(elapsed.total_seconds() / 60)
        return False, remaining
```

### 3. Optional Dependencies

```python
try:
    import some_optional_lib
    HAS_OPTIONAL = True
except ImportError:
    HAS_OPTIONAL = False

class MySkill(BaseSkill):
    async def initialize(self) -> bool:
        if not HAS_OPTIONAL:
            self.logger.error("some_optional_lib not installed")
            self._status = SkillStatus.UNAVAILABLE
            return False
        # ...
```

### 4. Resource Cleanup

```python
from contextlib import asynccontextmanager

class DatabaseSkill(BaseSkill):
    @asynccontextmanager
    async def connection(self):
        conn = await self._pool.acquire()
        try:
            yield conn
        finally:
            await self._pool.release(conn)
```

### 5. Logging

```python
# Use the built-in logger
self.logger.debug("Detailed trace info")
self.logger.info("Normal operation")
self.logger.warning("Something unexpected but recoverable")
self.logger.error("Operation failed")

# Include context in error logs
self.logger.error(f"my_action failed for input={input_data[:50]}: {e}")
```

### 6. Security

```python
# NEVER log secrets
self.logger.info(f"Using API URL: {self._api_url}")  # ✅
self.logger.info(f"Using token: {self._token}")       # ❌ NEVER

# Always use env: prefix for secrets in config
# api_key: env:MY_API_KEY  # Resolved at runtime
```

---

## Reference: Existing Skills

### Skill Categories

| Category | Skills | Purpose |
|----------|--------|---------|
| **LLM** | `llm`, `litellm`, `moonshot` | Text generation, chat |
| **Database** | `database` | PostgreSQL operations |
| **Social** | `moltbook`, `social` | Social media posting |
| **Monitoring** | `health`, `performance` | System health checks |
| **Goals** | `goals`, `hourly_goals` | Task/goal management |
| **Knowledge** | `knowledge_graph` | Entity relationships |
| **Scheduling** | `schedule` | Job scheduling |
| **Development** | `pytest_runner` | Run test suite |
| **Model** | `model_switcher` | LLM model selection |

### Module Name Mapping

| OpenClaw Name | Module Name | Python Class |
|---------------|-------------|--------------|
| `aria-llm` | `llm` | `LLMSkill` |
| `aria-database` | `database` | `DatabaseSkill` |
| `aria-health` | `health` | `HealthSkill` |
| `aria-goals` | `goals` | `GoalsSkill` |
| `aria-schedule` | `schedule` | `ScheduleSkill` |
| `aria-knowledge-graph` | `knowledge_graph` | `KnowledgeGraphSkill` |
| `aria-model-switcher` | `model_switcher` | `ModelSwitcherSkill` |
| `aria-hourly-goals` | `hourly_goals` | `HourlyGoalsSkill` |
| `aria-pytest` | `pytest` | `PytestSkill` |
| `aria-moltbook` | `moltbook` | `MoltbookSkill` |
| `aria-social` | `social` | `SocialSkill` |
| `aria-performance` | `performance` | `PerformanceSkill` |
| `aria-litellm` | `litellm` | `LiteLLMSkill` |

---

## Quick Reference Templates

### Minimal Skill Template

```python
from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus
from aria_skills.registry import SkillRegistry

@SkillRegistry.register
class MinimalSkill(BaseSkill):
    @property
    def name(self) -> str:
        return "minimal"
    
    async def initialize(self) -> bool:
        self._status = SkillStatus.AVAILABLE
        return True
    
    async def health_check(self) -> SkillStatus:
        return self._status
    
    async def do_thing(self, input: str) -> SkillResult:
        return SkillResult.ok({"processed": input})
```

### Minimal skill.json

```json
{
  "name": "aria-minimal",
  "version": "1.0.0",
  "description": "Minimal example skill.",
  "author": "Aria Team",
  "tools": [
    {
      "name": "do_thing",
      "description": "Process input.",
      "parameters": {
        "type": "object",
        "properties": {
          "input": {"type": "string", "description": "Input to process"}
        },
        "required": ["input"]
      }
    }
  ],
  "run": "python3 /root/.openclaw/workspace/skills/run_skill.py minimal {{tool}} '{{args_json}}'"
}
```

---

## Troubleshooting

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Skill not found | Not imported in `__init__.py` | Add import and `__all__` entry |
| `env:VAR_NAME` not resolved | Var not set | Add to `.env` file on server |
| Tool not appearing | Manifest error | Validate JSON syntax |
| Health check failing | Network/auth issue | Check logs, verify credentials |
| Rate limited | Too many requests | Implement cooldown logic |

### Debug Commands

```bash
# Check skill loaded
python3 -c "from aria_skills import *; print([s for s in dir() if 'Skill' in s])"

# Test skill directly
python3 -c "
import asyncio
from aria_skills.base import SkillConfig
from aria_skills.my_skill import MySkill

async def test():
    config = SkillConfig(name='my_skill', config={'api_key': 'test'})
    skill = MySkill(config)
    print(await skill.initialize())
    print(await skill.health_check())

asyncio.run(test())
"

# Check OpenClaw manifest
cat openclaw_skills/aria-my-skill/skill.json | python3 -m json.tool
```

---

> **Remember**: Skills are Aria's hands. They must be reliable, secure, and well-documented. Each skill should do one thing well.
