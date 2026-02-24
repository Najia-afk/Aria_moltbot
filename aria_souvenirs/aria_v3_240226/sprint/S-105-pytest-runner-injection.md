# S-105: Fix pytest_runner Command Injection
**Epic:** E4 — Security Hardening | **Priority:** P0 | **Points:** 2 | **Phase:** 1

## Problem
`aria_skills/pytest_runner/__init__.py` passes user-supplied `path`, `markers`, and `keywords` directly to subprocess command without sanitization. Shell metacharacters in these parameters can inject arbitrary commands.

## Root Cause
No input validation or sanitization on subprocess arguments.

## Fix
1. Validate `path` against an allowlist of allowed test directories
2. Sanitize `markers` and `keywords` to alphanumeric + underscores only
3. Use list-based subprocess call (not shell=True)

```python
import re

ALLOWED_TEST_DIRS = ["tests/", "src/api/tests/", "aria_skills/"]

def _validate_path(path: str) -> str:
    """Validate test path against allowlist."""
    path = path.strip().replace("\\", "/")
    if not any(path.startswith(d) for d in ALLOWED_TEST_DIRS):
        raise ValueError(f"Test path must start with one of: {ALLOWED_TEST_DIRS}")
    if ".." in path:
        raise ValueError("Path traversal not allowed")
    return path

def _sanitize_param(value: str) -> str:
    """Sanitize pytest parameter to safe characters."""
    return re.sub(r'[^a-zA-Z0-9_\-\s,]', '', value)
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer architecture | ✅ | L3 domain skill |
| 2 | .env for secrets | ❌ | No secrets |
| 3 | models.yaml single source | ❌ | No models |
| 4 | Docker-first testing | ✅ | Test in Docker |
| 5 | aria_memories writable path | ❌ | No memory writes |
| 6 | No soul modification | ❌ | No soul changes |

## Dependencies
- None

## Verification
```bash
# 1. Verify sanitization exists
grep -n "sanitize\|validate" aria_skills/pytest_runner/__init__.py
# EXPECTED: validation functions present

# 2. Verify allowlist
grep -n "ALLOWED_TEST_DIRS" aria_skills/pytest_runner/__init__.py
# EXPECTED: allowlist defined

# 3. Run tests
pytest tests/ -k "pytest_runner" -v
# EXPECTED: all pass (or no tests exist yet)
```

## Prompt for Agent
```
Read: aria_skills/pytest_runner/__init__.py (full file)

Steps:
1. Find subprocess.run or subprocess.Popen calls
2. Add path validation with allowlist
3. Add markers/keywords sanitization (alphanumeric + underscore only)
4. Ensure subprocess uses list args (not shell=True)
5. Test: normal pytest execution works
6. Test: injection attempt (path with ';rm -rf') is blocked
```
