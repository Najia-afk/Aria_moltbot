# S8-03: Delete `openclaw_config.py` and Clean Imports
**Epic:** E6 — OpenClaw Removal | **Priority:** P0 | **Points:** 1 | **Phase:** 8

## Problem
`aria_models/openclaw_config.py` (88 lines) is a Python script that renders OpenClaw's `openclaw-config.json` from a template + `models.yaml`. With OpenClaw removed, this file and all references to it must be deleted.

## Root Cause
This module was exclusively used by `openclaw-entrypoint.sh` (deleted in S8-02) to generate the OpenClaw gateway configuration at container startup. No other Python code imports it.

## Fix

### 1. Delete the file

```bash
rm aria_models/openclaw_config.py
```

### 2. Clean references in documentation

**`MODELS.md`** (line ~57):
```markdown
# REMOVE this line:
- OpenClaw integration: [`aria_models/openclaw_config.py`](aria_models/openclaw_config.py)
```

**`aria_models/README.md`** (line ~7):
```markdown
# REMOVE this line:
- OpenClaw generator: `aria_models/openclaw_config.py`
```

**`STRUCTURE.md`** (line ~128):
```markdown
# REMOVE this line:
│   ├── openclaw_config.py        # OpenClaw model config
```

### 3. Clean all "openclaw" references project-wide

Run a comprehensive grep to find and clean remaining references:

```bash
#!/bin/bash
# scripts/clean_openclaw_refs.sh

echo "=== Scanning for 'openclaw' references ==="

# Search Python files
echo "--- Python files ---"
grep -rn "openclaw" --include="*.py" \
    aria_agents/ aria_mind/ aria_models/ aria_skills/ src/ scripts/ \
    | grep -v __pycache__ \
    | grep -v "plans/" \
    | grep -v ".pyc"

# Search YAML/YML files
echo "--- YAML files ---"
grep -rn "openclaw" --include="*.yaml" --include="*.yml" \
    aria_mind/ stacks/ src/ \
    | grep -v "plans/"

# Search Markdown docs (excluding plan tickets)
echo "--- Documentation ---"
grep -rn "openclaw\|OpenClaw" --include="*.md" \
    *.md aria_models/ aria_mind/ docs/ \
    | grep -v "plans/" \
    | grep -v "aria_souvenirs/"

# Search shell scripts
echo "--- Shell scripts ---"
grep -rn "openclaw" --include="*.sh" \
    scripts/ stacks/ deploy/ \
    | grep -v "plans/"

echo ""
echo "Review each match and decide: delete line, update reference, or leave (if historical context)."
```

### 4. Verify `aria_models/__init__.py` doesn't export it

```python
# aria_models/__init__.py — verify no openclaw_config import exists
# If found, remove lines like:
#   from aria_models.openclaw_config import render_openclaw_config
```

### 5. Verify `aria_models/loader.py` functions still used

The functions `build_agent_aliases`, `build_agent_routing`, `build_litellm_models`, `get_timeout_seconds` in `aria_models/loader.py` were imported by `openclaw_config.py`. Check if they are used elsewhere:

```bash
grep -rn "build_agent_aliases\|build_agent_routing\|build_litellm_models\|get_timeout_seconds" \
    --include="*.py" aria_models/ aria_mind/ aria_skills/ src/ \
    | grep -v openclaw_config.py \
    | grep -v __pycache__
```

If these functions are ONLY used by `openclaw_config.py`, mark them as candidates for removal in a future cleanup ticket (but don't delete in this ticket — they may be useful for the engine's model routing).

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ❌ | Deleting dead code |
| 2 | .env for secrets (zero in code) | ❌ | N/A |
| 3 | models.yaml single source of truth | ✅ | models.yaml remains — only the OpenClaw renderer is deleted |
| 4 | Docker-first testing | ✅ | Run tests to verify no import errors |
| 5 | aria_memories only writable path | ❌ | N/A |
| 6 | No soul modification | ❌ | N/A |

## Dependencies
- S8-01 (Remove clawdbot service — entrypoint.sh called this script)
- S8-02 (Delete OpenClaw configs — entrypoint.sh deleted)

## Verification
```bash
# 1. File deleted:
test ! -f aria_models/openclaw_config.py && echo "PASS" || echo "FAIL"
# EXPECTED: PASS

# 2. No Python import errors:
python -c "import aria_models" && echo "PASS" || echo "FAIL"
# EXPECTED: PASS

# 3. No openclaw references in Python code (excluding plans/souvenirs):
grep -rn "openclaw" --include="*.py" aria_agents/ aria_mind/ aria_models/ aria_skills/ src/ | grep -v __pycache__ | grep -v "plans/" | wc -l
# EXPECTED: 0

# 4. models.yaml still loads:
python -c "from aria_models.loader import load_catalog; c = load_catalog(); print(f'Models: {len(c.get(\"models\", {}))}')"
# EXPECTED: Models: <N> (some positive number)
```

## Prompt for Agent
```
Delete aria_models/openclaw_config.py and clean all references to it.

FILES TO READ FIRST:
- aria_models/openclaw_config.py (to confirm what it does, then delete it)
- aria_models/__init__.py (check for imports to remove)
- aria_models/README.md (remove openclaw_config reference)
- MODELS.md (remove OpenClaw integration line)
- STRUCTURE.md (remove openclaw_config.py from tree)

STEPS:
1. Delete aria_models/openclaw_config.py
2. Remove any import of openclaw_config from aria_models/__init__.py
3. Remove documentation references in MODELS.md, aria_models/README.md, STRUCTURE.md
4. Run: grep -rn "openclaw" --include="*.py" to find remaining Python references
5. Clean any found references
6. Verify: python -c "import aria_models" passes without error

SAFETY:
- This file was ONLY called from openclaw-entrypoint.sh (deleted in S8-02)
- No other Python module imports it
- The functions it imports from loader.py may still be used elsewhere — do NOT delete those
- models.yaml is NOT affected — only the renderer is removed
```
