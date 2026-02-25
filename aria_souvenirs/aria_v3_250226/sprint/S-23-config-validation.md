# S-23: Config Validation with Pydantic BaseSettings
**Epic:** E12 — Engine Resilience | **Priority:** P1 | **Points:** 3 | **Phase:** 2

## Problem
`aria_engine/config.py` L1-64: `EngineConfig` is a plain dataclass with `field(default_factory=lambda: os.environ.get(...))`. There is **no validation**:
- `DATABASE_URL` could be empty string `""` → silent connection failure at runtime
- `db_pool_size` could be non-numeric → crash
- `LITELLM_MASTER_KEY` defaults to `""` → LiteLLM auth failures
- Default credentials `admin:admin` in `config.py` L14-15 → dangerous in production

Misconfiguration produces cryptic runtime errors instead of a clear startup failure.

## Root Cause
Config was built as a simple dataclass wrapper around os.environ. No validation layer.

## Fix

### Fix 1: Replace dataclass with Pydantic BaseSettings
**File:** `aria_engine/config.py`

**BEFORE:**
```python
@dataclass
class EngineConfig:
    database_url: str = field(default_factory=lambda: os.environ.get("DATABASE_URL", "postgresql+asyncpg://admin:admin@localhost/aria_warehouse"))
    db_pool_size: int = field(default_factory=lambda: int(os.environ.get("DB_POOL_SIZE", "10")))
    litellm_url: str = field(default_factory=lambda: os.environ.get("LITELLM_URL", "http://localhost:4000"))
    ...
```

**AFTER:**
```python
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator

class EngineConfig(BaseSettings):
    database_url: str = Field(
        default="postgresql+asyncpg://admin:admin@localhost/aria_warehouse",
        description="PostgreSQL connection string"
    )
    db_pool_size: int = Field(default=10, ge=1, le=100)
    db_max_overflow: int = Field(default=20, ge=0, le=200)
    litellm_url: str = Field(default="http://localhost:4000")
    litellm_master_key: str = Field(default="")
    engine_debug: bool = Field(default=False)
    
    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v):
        if not v or v == "":
            raise ValueError("DATABASE_URL must not be empty")
        if "admin:admin" in v and not os.environ.get("ENGINE_DEBUG"):
            import warnings
            warnings.warn("Using default credentials in non-debug mode!")
        return v
    
    @field_validator("litellm_master_key")
    @classmethod  
    def validate_litellm_key(cls, v):
        if v == "sk-change-me":
            import warnings
            warnings.warn("Using default LiteLLM master key — change in production!")
        return v
    
    class Config:
        env_prefix = ""
        case_sensitive = False
```

### Fix 2: Add startup validation
**File:** `aria_engine/entrypoint.py`
```python
def main():
    try:
        config = EngineConfig()
    except ValidationError as e:
        logger.critical(f"Configuration error:\n{e}")
        sys.exit(1)
    # ... continue startup
```

### Fix 3: Add pydantic-settings dependency
**File:** `pyproject.toml`
```toml
dependencies = [
    ...
    "pydantic-settings>=2.0",
]
```

### Fix 4: Update all config consumers
Find all `EngineConfig()` instantiations and call sites. Verify they work with the new Pydantic model (attribute access is the same, so most should work unchanged).

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer architecture | ✅ | Engine config layer |
| 2 | .env for secrets | ✅ | All config from .env |
| 3 | models.yaml truth | ❌ | |
| 4 | Docker-first testing | ✅ | |
| 5 | aria_memories writable | ❌ | |
| 6 | No soul modification | ❌ | |

## Dependencies
- None — standalone.

## Verification
```bash
# 1. Invalid config fails fast:
DATABASE_URL="" python -c "from aria_engine.config import EngineConfig; EngineConfig()"
# EXPECTED: ValidationError

# 2. Non-numeric pool size fails:
DB_POOL_SIZE=abc python -c "from aria_engine.config import EngineConfig; EngineConfig()"
# EXPECTED: ValidationError

# 3. Valid config works:
python -c "from aria_engine.config import EngineConfig; c = EngineConfig(); print(c.db_pool_size)"
# EXPECTED: 10

# 4. Default creds warning:
python -c "from aria_engine.config import EngineConfig; EngineConfig()" 2>&1 | grep -i 'default'
# EXPECTED: Warning about default credentials (unless ENGINE_DEBUG)
```

## Prompt for Agent
```
Read these files FIRST:
- aria_engine/config.py (full)
- aria_engine/entrypoint.py (L80-L120 — config loading)
- pyproject.toml (dependencies)

CONSTRAINTS: #2 (.env for all config).

STEPS:
1. Add pydantic-settings to pyproject.toml dependencies
2. Replace EngineConfig dataclass with Pydantic BaseSettings
3. Add field validators for: database_url (non-empty), db_pool_size (positive int), litellm_master_key (warn on default)
4. Add startup validation in entrypoint.py with clear error message
5. Grep for all EngineConfig() usage — verify compatibility
6. Keep all existing default values for backward compat
7. Run tests to verify no regressions
8. Test invalid config scenarios
```
