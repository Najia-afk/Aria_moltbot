# S-114: Fix model_switcher Cross-Layer Import
**Epic:** E5 — Architecture Cleanup | **Priority:** P1 | **Points:** 3 | **Phase:** 2

## Problem
`aria_skills/model_switcher/__init__.py` imports from `aria_engine.thinking`:
```python
from aria_engine.thinking import build_thinking_params
```

This is a cross-layer violation: skills (L2) importing from the engine layer (which sits above skills in the architecture). The engine should depend on skills, not the other way around.

Additionally, `model_switcher` is missing from `aria_skills/__init__.py` imports, so it's not auto-loaded.

## Root Cause
The thinking parameter builder was placed in the engine layer but is needed by the skill. The logic should be at the skill layer or in a shared utility.

## Fix
1. Move `build_thinking_params` function from `aria_engine/thinking.py` into the model_switcher skill (or a shared skill-layer utility)
2. Remove the `from aria_engine.thinking import` statement
3. Add `model_switcher` to `aria_skills/__init__.py`

```python
# BEFORE (in model_switcher/__init__.py):
from aria_engine.thinking import build_thinking_params

# AFTER:
# Move the function into the skill module
def build_thinking_params(model: str, budget_tokens: int = 10000) -> dict:
    """Build thinking/extended-thinking params for supported models."""
    # Copy the implementation from aria_engine/thinking.py
    ...
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer architecture | ✅ | This fix RESOLVES a violation |
| 2 | .env for secrets | ❌ | No secrets |
| 3 | models.yaml single source | ✅ | Model names must come from models.yaml |
| 4 | Docker-first testing | ✅ | Test in Docker |
| 5 | aria_memories writable path | ❌ | No memory changes |
| 6 | No soul modification | ❌ | No soul changes |

## Dependencies
- None

## Verification
```bash
# 1. Verify no engine imports in skills
grep -rn "from aria_engine" aria_skills/
# EXPECTED: no matches

# 2. Verify model_switcher is in __init__.py
grep "model_switcher" aria_skills/__init__.py
# EXPECTED: import present

# 3. Run architecture test
pytest tests/test_architecture.py -v
# EXPECTED: all pass

# 4. Run full tests
pytest tests/ -v
# EXPECTED: all pass
```

## Prompt for Agent
```
Read:
- aria_skills/model_switcher/__init__.py (full file)
- aria_engine/thinking.py (full file — find build_thinking_params)
- aria_skills/__init__.py (full file)

Steps:
1. Copy build_thinking_params from aria_engine/thinking.py to model_switcher skill
2. Remove "from aria_engine.thinking import" from model_switcher
3. Verify aria_engine/thinking.py still works (it may have other callers)
4. Add model_switcher import to aria_skills/__init__.py
5. Run: pytest tests/test_architecture.py -v
6. Run: pytest tests/ -v
```
