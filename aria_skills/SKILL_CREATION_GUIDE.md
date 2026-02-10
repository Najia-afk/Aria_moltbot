# Skill Creation Guide

> How to build, register, and ship a new Aria skill from scratch.

---

## 1. When to Create a Skill

Use this decision tree before writing code:

```
Is this capability reusable across multiple agent focuses?
  ├─ YES → Create a skill
  └─ NO
       └─ Does it need its own config, health check, or rate limiting?
            ├─ YES → Create a skill
            └─ NO  → Add it as a helper function in an existing skill
```

**Create a skill when:**
- The feature talks to an external API or service
- It needs independent health monitoring
- Multiple agents or pipelines will call it
- It has its own authentication or rate limits

**Do NOT create a skill when:**
- It is a pure data transform with no side-effects (use a utility module)
- It duplicates an existing skill's responsibility
- It is a one-off script (use `scripts/` instead)

---

## 2. Architecture — 5-Layer Hierarchy

Every skill belongs to exactly one layer. Lower layers **must not** import higher layers.

| Layer | Name          | Purpose                        | Examples                              |
|-------|---------------|--------------------------------|---------------------------------------|
| 0     | Kernel        | Read-only identity & security  | `input_guard`                         |
| 1     | API Client    | Sole DB / HTTP gateway         | `api_client`                          |
| 2     | Core          | Essential runtime services     | `llm`, `litellm`, `health`, `ollama`  |
| 3     | Domain        | Feature-specific logic         | `goals`, `research`, `social`         |
| 4     | Orchestration | Planning & scheduling          | `schedule`, `pipeline_skill`          |

**Rules:**
- Layer 0 is **read-only** at runtime.
- All database access goes through Layer 1 (`api_client`).
- Skills in the **same layer** may import each other.
- Most new skills belong to **Layer 3**.

---

## 3. Directory Structure

Every skill lives in its own subdirectory under `aria_skills/`:

```
aria_skills/<skill_name>/
    __init__.py     # Skill class with @SkillRegistry.register
    skill.json      # v2 manifest (metadata + tool definitions)
    README.md       # Documentation (recommended)
```

### Naming Convention

| Element            | Format                               | Example                   |
|--------------------|--------------------------------------|---------------------------|
| Directory name     | `snake_case`                         | `market_data`             |
| Class name         | PascalCase + `Skill` suffix          | `MarketDataSkill`         |
| `.name` property   | `snake_case` (matches directory)     | `"market_data"`           |
| Canonical name     | `aria-<kebab-case>`                  | `aria-market-data`        |

All four **must** agree. The `canonical_name` property is derived automatically by `BaseSkill`.

---

## 4. Step-by-Step Tutorial — Create a Layer 3 Skill

We will build a fictional **Weather Skill** that fetches forecasts via an external API.

### Step 1 — Scaffold the directory

```
aria_skills/weather/
    __init__.py
    skill.json
    README.md
```

You can copy the starter files from `aria_skills/_template/`.

### Step 2 — Write `skill.json`

```json
{
  "name": "aria-weather",
  "version": "1.0.0",
  "description": "Fetches weather forecasts from an external API.",
  "author": "Aria Team",
  "layer": 3,
  "dependencies": ["api_client"],
  "focus_affinity": ["data"],
  "tools": [
    {
      "name": "get_forecast",
      "description": "Return the weather forecast for a given city.",
      "input_schema": {
        "type": "object",
        "properties": {
          "city": { "type": "string", "description": "City name" },
          "days": { "type": "integer", "description": "Forecast days (1-7)", "default": 3 }
        },
        "required": ["city"]
      }
    }
  ]
}
```

### Step 3 — Implement `__init__.py`

```python
"""Weather forecast skill."""
from typing import Optional

from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus, logged_method
from aria_skills.api_client import get_api_client
from aria_skills.registry import SkillRegistry


@SkillRegistry.register
class WeatherSkill(BaseSkill):
    """Fetches weather forecasts."""

    def __init__(self, config: SkillConfig):
        super().__init__(config)
        self._api = None

    @property
    def name(self) -> str:
        return "weather"

    async def initialize(self) -> bool:
        self._api = await get_api_client()
        self._api_key = self._get_env_value("api_key")
        if not self._api_key:
            self.logger.warning("WEATHER_API_KEY not set")
            return False
        self._status = SkillStatus.AVAILABLE
        return True

    async def health_check(self) -> SkillStatus:
        return self._status

    @logged_method()
    async def get_forecast(self, city: str, days: int = 3) -> SkillResult:
        """Get weather forecast for *city*."""
        if not 1 <= days <= 7:
            return SkillResult.fail("days must be between 1 and 7")
        try:
            data = await self.safe_execute(
                self._fetch_forecast, "get_forecast", city, days
            )
            return SkillResult.ok(data)
        except Exception as e:
            self._log_usage("get_forecast", False, error=str(e))
            return SkillResult.fail(str(e))

    async def _fetch_forecast(self, city: str, days: int) -> dict:
        """Call the upstream weather API."""
        import httpx
        url = f"https://api.weatherapi.com/v1/forecast.json"
        params = {"key": self._api_key, "q": city, "days": days}
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()
```

### Step 4 — Register the import

Add one line to `aria_skills/__init__.py`:

```python
from aria_skills.weather import WeatherSkill
```

### Step 5 — Write tests

See the **Test Template** section below.

---

## 5. `skill.json` Template

```json
{
  "name": "aria-<skill_name>",
  "version": "1.0.0",
  "description": "Short human-readable description.",
  "author": "Aria Team",
  "layer": 3,
  "dependencies": ["api_client"],
  "focus_affinity": ["orchestrator"],
  "tools": [
    {
      "name": "tool_method_name",
      "description": "What this tool does and when to use it.",
      "input_schema": {
        "type": "object",
        "properties": {
          "param1": { "type": "string", "description": "Description" }
        },
        "required": ["param1"]
      }
    }
  ]
}
```

| Key              | Type     | Notes                                                |
|------------------|----------|------------------------------------------------------|
| `name`           | string   | `aria-<snake_name>` with hyphens                     |
| `version`        | string   | Semver — start at `1.0.0`                            |
| `description`    | string   | One sentence                                         |
| `author`         | string   | `"Aria Team"` or contributor name                    |
| `layer`          | integer  | 0–4 per hierarchy table                              |
| `dependencies`   | string[] | Skill directory names (not pip packages)             |
| `focus_affinity` | string[] | Agent focuses that benefit: `orchestrator`, `data`, `creative`, `social`, `trader`, `devsecops`, `journalist` |
| `tools`          | object[] | One entry per public method                          |

---

## 6. `__init__.py` Template

```python
"""<skill_name> skill — <short description>."""
from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus, logged_method
from aria_skills.registry import SkillRegistry


@SkillRegistry.register
class <SkillName>Skill(BaseSkill):
    """<One-line docstring>."""

    def __init__(self, config: SkillConfig):
        super().__init__(config)

    @property
    def name(self) -> str:
        return "<skill_name>"          # Must match directory name

    async def initialize(self) -> bool:
        # Validate config, open connections
        self._status = SkillStatus.AVAILABLE
        return True

    async def health_check(self) -> SkillStatus:
        return self._status

    @logged_method()
    async def do_something(self, param: str) -> SkillResult:
        """Public tool method — listed in skill.json tools array."""
        try:
            result = await self._internal_logic(param)
            self._log_usage("do_something", True)
            return SkillResult.ok(result)
        except Exception as e:
            self._log_usage("do_something", False, error=str(e))
            return SkillResult.fail(str(e))

    async def _internal_logic(self, param: str) -> dict:
        """Private helper — not exposed as a tool."""
        return {"echo": param}
```

---

## 7. Test Template

Place tests in `aria_skills/<skill_name>/tests/` or the top-level `tests/` directory.

```python
"""Tests for <skill_name> skill."""
import pytest
from aria_skills.base import SkillConfig, SkillStatus
from aria_skills.<skill_name> import <SkillName>Skill


@pytest.fixture
def config():
    return SkillConfig(name="<skill_name>", config={})


@pytest.fixture
def skill(config):
    return <SkillName>Skill(config)


@pytest.mark.asyncio
async def test_initialize(skill):
    result = await skill.initialize()
    assert result is True
    assert skill.status == SkillStatus.AVAILABLE


@pytest.mark.asyncio
async def test_health_check(skill):
    await skill.initialize()
    status = await skill.health_check()
    assert status == SkillStatus.AVAILABLE


@pytest.mark.asyncio
async def test_name_matches_directory(skill):
    assert skill.name == "<skill_name>"


@pytest.mark.asyncio
async def test_do_something(skill):
    await skill.initialize()
    result = await skill.do_something("hello")
    assert result.success is True
    assert result.data == {"echo": "hello"}
```

Run with:

```bash
pytest aria_skills/<skill_name>/tests/ -v --asyncio-mode=auto
```

---

## 8. Common Patterns from Existing Skills

### Pattern A — API Client Usage (Layer 3)

All external HTTP and database access should go through the shared `api_client`:

```python
from aria_skills.api_client import get_api_client

async def initialize(self) -> bool:
    self._api = await get_api_client()
    self._status = SkillStatus.AVAILABLE
    return True
```

### Pattern B — `@logged_method()` Decorator

Automatically logs method calls (duration, success/failure) to the activity log:

```python
from aria_skills.base import logged_method

@logged_method()
async def create_goal(self, title: str) -> SkillResult:
    ...
```

You can pass a custom action name: `@logged_method("goals.create")`.

### Pattern C — Environment Variable Resolution

Use `self._get_env_value(key)` to resolve config values that use the `env:` prefix:

```python
# In skill.json or TOOLS.md config:  api_key: env:WEATHER_API_KEY
api_key = self._get_env_value("api_key")   # reads os.environ["WEATHER_API_KEY"]
```

### Pattern D — Safe Execution with Retry + Metrics

Wrap unreliable external calls with `self.safe_execute()`:

```python
data = await self.safe_execute(
    self._fetch_data, "fetch_data",
    url, params,
    with_retry=True, max_attempts=3,
)
```

### Pattern E — Graceful Degradation

Return `SkillResult.fail(...)` instead of raising exceptions so callers always get a predictable response:

```python
try:
    resp = await self._api._client.get(f"/items/{item_id}")
    resp.raise_for_status()
    return SkillResult.ok(resp.json())
except Exception as e:
    self.logger.warning(f"API call failed: {e}")
    return SkillResult.fail(str(e))
```

---

## 9. Anti-Patterns

| Anti-Pattern                    | Why It's Wrong                                | Do This Instead                                |
|---------------------------------|-----------------------------------------------|------------------------------------------------|
| Direct DB/SQL access            | Bypasses Layer 1 gateway                      | Use `api_client` for all data access           |
| Hardcoded URLs                  | Breaks across environments                    | Use config values or `env:` prefix             |
| Returning raw strings           | Callers can't inspect `.success` or `.data`   | Always return `SkillResult`                     |
| Importing higher-layer skills   | Violates layer hierarchy                      | Only import same-layer or lower                |
| Blocking synchronous I/O        | Starves the async event loop                  | Use `httpx.AsyncClient` or `asyncio` wrappers  |
| Swallowing all exceptions       | Hides real errors from monitoring             | Log the error, then return `SkillResult.fail()` |
| Using `SKILL_MAP` dict          | Deprecated pattern                            | Use `@SkillRegistry.register` decorator        |
| Missing `health_check()`        | Skill won't participate in health monitoring  | Always implement — even if it just returns status |
| Giant `__init__` constructors   | Slow startup, hard to test                    | Move setup into `initialize()`                 |

---

## 10. Validation Checklist

Before submitting a PR for a new skill, verify every item:

- [ ] Directory is `aria_skills/<snake_case_name>/`
- [ ] `skill.json` exists and is valid JSON
- [ ] `skill.json` `name` matches `aria-<kebab-case-name>`
- [ ] `skill.json` `layer` is correct (most new skills → 3)
- [ ] `skill.json` `dependencies` lists only skill directory names
- [ ] `skill.json` `tools` array has one entry per public method
- [ ] `__init__.py` uses `@SkillRegistry.register` decorator
- [ ] Class inherits from `BaseSkill`
- [ ] `.name` property returns directory name (snake_case)
- [ ] `initialize()` is async and returns `bool`
- [ ] `health_check()` is async and returns `SkillStatus`
- [ ] All public methods return `SkillResult`
- [ ] No imports from higher layers
- [ ] No direct DB queries — all data goes through `api_client`
- [ ] No hardcoded URLs — use config or `env:` prefix
- [ ] `@logged_method()` on every public tool method
- [ ] At least one test file with `pytest` + `asyncio`
- [ ] `README.md` documents purpose and usage
- [ ] Import added to `aria_skills/__init__.py`
- [ ] `ast.parse` succeeds on `__init__.py` (valid Python)

---

## Quick Start

```bash
# 1. Copy the template
cp -r aria_skills/_template aria_skills/my_new_skill

# 2. Rename placeholders in __init__.py, skill.json, README.md

# 3. Implement your logic

# 4. Add import to aria_skills/__init__.py

# 5. Run tests
pytest aria_skills/my_new_skill/tests/ -v --asyncio-mode=auto

# 6. Validate
python -c "import ast; ast.parse(open('aria_skills/my_new_skill/__init__.py').read()); print('OK')"
```
