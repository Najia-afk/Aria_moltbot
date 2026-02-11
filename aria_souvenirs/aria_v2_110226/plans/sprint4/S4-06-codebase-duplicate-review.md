# S4-06: Review Entire Codebase for Duplicates and Violations
**Epic:** E10 — Code Quality | **Priority:** P1 | **Points:** 5 | **Phase:** 3

## Problem
The codebase may have:
1. Duplicate function definitions across templates (escapeHtml, formatDate, etc.)
2. Architecture violations (skills importing SQLAlchemy directly)
3. Hardcoded model names (instead of models.yaml)
4. Hardcoded secrets or API keys
5. Dead code from removed skills
6. Inconsistent API response formats
7. Missing error handling
8. Duplicate routes or endpoints

## Root Cause
Rapid development without systematic code review. Multiple contributors (AI agents) with different patterns.

## Fix

### Step 1: Automated checks
Create `scripts/check_architecture.py` (NEW):

```python
"""Architecture compliance checker for Aria codebase."""
import re
import sys
from pathlib import Path

errors = []

# Check 1: Skills importing SQLAlchemy
for f in Path("aria_skills").rglob("*.py"):
    content = f.read_text()
    if "sqlalchemy" in content.lower() and f.name != "base.py":
        errors.append(f"VIOLATION: {f} imports SQLAlchemy directly")

# Check 2: Hardcoded model names
model_names = ["gpt-4", "claude", "kimi", "moonshot", "deepseek"]
for pattern in ["src/", "aria_skills/", "aria_mind/"]:
    for f in Path(pattern).rglob("*.py"):
        content = f.read_text()
        for name in model_names:
            if f'"{name}' in content and "models.yaml" not in str(f) and "test_" not in f.name:
                errors.append(f"HARDCODED MODEL: {f} references '{name}'")

# Check 3: Secrets in code
for pattern in ["src/", "aria_skills/"]:
    for f in Path(pattern).rglob("*.py"):
        content = f.read_text()
        if re.search(r'(sk-[a-zA-Z0-9]{20,}|AKIA[A-Z0-9]{12,})', content):
            errors.append(f"SECRET: {f} may contain hardcoded secret")

# Check 4: Duplicate function definitions in templates
func_defs = {}
for f in Path("src/web/templates").glob("*.html"):
    content = f.read_text()
    for match in re.finditer(r'function\s+(\w+)\s*\(', content):
        func_name = match.group(1)
        if func_name in func_defs:
            errors.append(f"DUPLICATE: {func_name}() defined in both {func_defs[func_name]} and {f.name}")
        else:
            func_defs[func_name] = f.name

# Check 5: Skills calling other skills directly
for f in Path("aria_skills").rglob("*.py"):
    if f.parent.name in ("api_client", "_template", "__pycache__"):
        continue
    content = f.read_text()
    if re.search(r'from aria_skills\.(?!base|registry|api_client)', content):
        errors.append(f"DIRECT CALL: {f} imports from another skill (should use api_client → API)")

if errors:
    print(f"\n{'='*60}")
    print(f"ARCHITECTURE CHECK: {len(errors)} issues found")
    print(f"{'='*60}\n")
    for e in errors:
        print(f"  ❌ {e}")
    sys.exit(1)
else:
    print("✅ Architecture check passed — no violations found")
    sys.exit(0)
```

### Step 2: Run and fix all violations found

### Step 3: Add to CI pipeline (optional)

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ✅ | Checking compliance |
| 2 | .env secrets | ✅ | Checking for leaked secrets |
| 3 | models.yaml | ✅ | Checking for hardcoded models |
| 4 | Docker-first | ✅ | Run in Docker |
| 5 | aria_memories | ❌ | Script outputs to stdout |
| 6 | No soul mod | ❌ | No soul files |

## Dependencies
- S2-11 (deduplicate JS) should complete first to reduce noise.

## Verification
```bash
# Run architecture check:
python scripts/check_architecture.py
# EXPECTED: 0 issues (or documented known exceptions)

# Run grep checks:
grep -rn 'from db\|from sqlalchemy' aria_skills/ --include='*.py' | grep -v 'base.py\|__pycache__\|api_client'
# EXPECTED: 0 results

grep -rn '"gpt-4\|"claude\|"kimi"' src/ aria_skills/ --include='*.py' | grep -v 'test_\|models.yaml\|#'
# EXPECTED: 0 results
```

## Prompt for Agent
```
Create an architecture compliance checker and fix all violations.

FILES TO READ:
- Full codebase scan via grep
- aria_skills/ (all .py files)
- src/ (all .py and .html files)

STEPS:
1. Create scripts/check_architecture.py
2. Run it and collect all violations
3. Fix each violation
4. Re-run until clean
5. Update tasks/lessons.md

CONSTRAINTS: Fix violations, don't introduce new ones. 5-layer compliance.
```
