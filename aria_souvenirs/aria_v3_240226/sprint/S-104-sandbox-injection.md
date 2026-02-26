# S-104: Fix Sandbox Code Injection Vulnerabilities
**Epic:** E4 — Security Hardening | **Priority:** P0 | **Points:** 3 | **Phase:** 1

## Problem
`aria_skills/sandbox/__init__.py` constructs Python code via f-string interpolation in `write_file()` and `read_file()`. User-supplied `content` or `path` containing `'''` or `\\` sequences can break out of the triple-quoted string and execute arbitrary code.

Example attack:
```python
# If path = "test.py'; import os; os.system('rm -rf /'); '"
# The f-string becomes executable code
```

## Root Cause
The sandbox skill builds Python code strings using f-string interpolation instead of safe serialization (base64 encoding or argument passing).

## Fix
Replace f-string code construction with base64-encoded content passing:

```python
# BEFORE (vulnerable):
code = f"""
with open('{path}', 'w') as f:
    f.write('''{content}''')
"""

# AFTER (safe):
import base64
encoded_content = base64.b64encode(content.encode()).decode()
code = f"""
import base64
with open('{_sanitize_path(path)}', 'w') as f:
    f.write(base64.b64decode('{encoded_content}').decode())
"""

def _sanitize_path(path: str) -> str:
    """Sanitize file path to prevent injection."""
    # Remove any quotes, semicolons, newlines
    sanitized = path.replace("'", "").replace('"', '').replace(';', '').replace('\n', '')
    # Prevent path traversal
    sanitized = sanitized.replace('..', '')
    return sanitized
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer architecture | ✅ | Sandbox is L3 skill — correct layer |
| 2 | .env for secrets | ❌ | No secrets |
| 3 | models.yaml single source | ❌ | No models |
| 4 | Docker-first testing | ✅ | Test sandbox execution in Docker |
| 5 | aria_memories writable path | ✅ | Sandbox writes to aria_memories/sandbox/ |
| 6 | No soul modification | ❌ | No soul changes |

## Dependencies
- S-102 (sandbox isolation) enhances this fix but is independent

## Verification
```bash
# 1. Verify f-string interpolation is removed
grep -n "f\"\"\"" aria_skills/sandbox/__init__.py | grep -i "write\|read"
# EXPECTED: no matches (or base64 pattern only)

# 2. Test normal write works
python -c "
from aria_skills.sandbox import SandboxSkill
s = SandboxSkill()
# Test normal write
print('Normal write test passed')
"

# 3. Test injection attempt is neutralized
grep -n "base64" aria_skills/sandbox/__init__.py
# EXPECTED: base64 import and encoding present

# 4. Run existing tests
pytest tests/ -k "sandbox" -v
# EXPECTED: all pass
```

## Prompt for Agent
```
Read: aria_skills/sandbox/__init__.py (full file)

Steps:
1. Find all f-string code construction in write_file() and read_file()
2. Replace with base64-encoded content passing
3. Add _sanitize_path() helper to prevent path traversal
4. Test: normal file write/read works
5. Test: injection attempt (content with ''') is neutralized
6. Run: pytest tests/ -k "sandbox" -v

Constraints: Sandbox is L3 skill. Must write only to aria_memories/sandbox/.
```
