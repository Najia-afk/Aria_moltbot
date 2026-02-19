# S-56: Skills & api_client Audit + Fix
**Epic:** E9 — Database Integration | **Priority:** P1 | **Points:** 5 | **Phase:** 2

## Problem

While initial investigation shows the skills layer is architecturally clean (no SQLAlchemy
violations found), a comprehensive audit is needed to verify:

1. **All skills** have working `run()` / `execute()` methods with the modern BaseSkill pattern
2. **api_client methods** exist for every persistence path (lesson from S-47: if a table exists
   in the DB, there must be a corresponding api_client method)
3. **No import errors** when loading the full skill registry
4. **Skill configurations** (skill.json + skill.yaml) are valid and consistent
5. **Pipeline executor** works with the current skill registry (not empty constructor bug)

Known risk areas from lessons:
- `PipelineExecutor(SkillRegistry())` creates a fresh empty registry (line in lessons.md)
- 9 skills were known to bypass api_client as of v1.1 (may have been fixed since)
- SkillConfig.settings is a dict, not an object — use `.get()` not `.attr`

## Root Cause

The skill ecosystem has grown to 30+ skills. Some were created before the v2 standard, and
incremental changes to the api_client or base skill class may have left some skills behind.
No automated CI check validates that all registered skills can actually be instantiated and
pass health checks.

## Fix

### Phase 1: Automated Import Audit

Create a verification script that:
```python
# scripts/audit_skills.py
import importlib
from aria_skills import __all__ as skill_exports
from aria_skills.registry import SkillRegistry

errors = []
for name in skill_exports:
    try:
        cls = getattr(__import__('aria_skills', fromlist=[name]), name)
        if hasattr(cls, 'health_check'):
            print(f"✅ {name}: importable, has health_check")
        else:
            print(f"⚠️  {name}: importable, missing health_check")
    except Exception as e:
        errors.append((name, str(e)))
        print(f"❌ {name}: {e}")

print(f"\n{len(skill_exports) - len(errors)}/{len(skill_exports)} skills OK")
```

### Phase 2: api_client Coverage Audit

Verify that every ORM table has a corresponding api_client method:

| Table | api_client method | Status |
|-------|------------------|--------|
| `memories` | `get_memories()`, `create_memory()` | Verify |
| `thoughts` | `get_thoughts()`, `create_thought()` | Verify |
| `goals` | `get_goals()`, `create_goal()` | Verify |
| `heartbeat_log` | `create_heartbeat()` | Added in S-55 |
| `engine_cron_jobs` | `get_cron_jobs()`, etc. | Verify |
| `engine_agent_state` | `get_agents()`, etc. | Verify |
| ... | ... | Full audit needed |

### Phase 3: Fix Any Broken Skills

For each broken skill found, apply the minimal fix:
- Missing imports → add imports
- api_client method mismatch → update method name
- SkillConfig pattern violation → fix `.settings.get()` usage
- health_check missing → add basic health_check method

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | Core constraint being audited |
| 2 | .env for secrets (zero in code) | ✅ | Skills read API_BASE_URL from env |
| 3 | models.yaml single source of truth | ✅ | Skills using LLM must use models.yaml |
| 4 | Docker-first testing | ✅ | Must run in Docker |
| 5 | aria_memories only writable path | ✅ | Skills writing files must use aria_memories/ |
| 6 | No soul modification | ❌ | No soul files |

## Dependencies
- S-55 should complete first (adds `create_heartbeat()` to api_client).
- Independent of S-50, S-51, S-52, S-53.

## Verification
```bash
# 1. Audit script runs clean:
python scripts/audit_skills.py
# EXPECTED: All skills OK, zero errors

# 2. No SQLAlchemy imports in skills:
grep -r "from sqlalchemy\|import sqlalchemy" aria_skills/ --include="*.py"
# EXPECTED: no matches

# 3. No direct DB imports in skills:
grep -r "from db\.\|from src.api.db\|from database" aria_skills/ --include="*.py"
# EXPECTED: no matches

# 4. Registry loads all skills:
python -c "
from aria_skills.registry import SkillRegistry
reg = SkillRegistry()
reg.discover()
print(f'{len(reg.skills)} skills registered')
"
# EXPECTED: 30+ skills registered (no errors)

# 5. Tests pass:
pytest tests/ -k "skill" -v --tb=short
# EXPECTED: all skill tests pass
```

## Prompt for Agent
Read these files first:
- `aria_skills/__init__.py` (full file — all skill exports)
- `aria_skills/base.py` (full file — BaseSkill, SkillConfig, SkillResult)
- `aria_skills/registry.py` (full file — SkillRegistry)
- `aria_skills/api_client/__init__.py` (full file — 1496 lines, all API methods)
- `aria_skills/pipeline_executor.py` (first 50 lines — check registry usage)
- `tasks/lessons.md` (full file — known bugs and patterns)

Steps:
1. Create `scripts/audit_skills.py` verification script
2. Run the script and collect results
3. For each broken skill, read the skill's `__init__.py` and fix the issue
4. Verify api_client has methods for all major DB tables
5. Add any missing api_client methods
6. Run full test suite

Constraints: #1 (NO direct DB access from skills), #2 (secrets from env), #3 (models.yaml for LLM), #5 (writable path = aria_memories only)
