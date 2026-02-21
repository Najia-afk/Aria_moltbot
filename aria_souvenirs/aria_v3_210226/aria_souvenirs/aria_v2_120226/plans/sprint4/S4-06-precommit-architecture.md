# S4-06: Add Pre-Commit Architecture Check
**Epic:** Sprint 4 — Reliability & Self-Healing | **Priority:** P2 | **Points:** 2 | **Phase:** 4

## Problem
Architecture violations can sneak back in between audit runs:
- A skill imports SQLAlchemy directly (bypassing api_client)
- A model name gets hardcoded instead of using models.yaml
- A secret gets committed to code instead of .env

Currently, `scripts/check_architecture.py` exists and works (0 errors today), but it only runs when someone manually executes it.

## Root Cause
No automated gate prevents architecture violations from being committed.

## Fix
Create a git pre-commit hook that runs the architecture checker:

### Option A: Simple shell hook
```bash
#!/bin/bash
# .git/hooks/pre-commit
# Run architecture checker before every commit

echo "🏗️ Running architecture check..."
python scripts/check_architecture.py 2>&1

ERRORS=$(python scripts/check_architecture.py 2>&1 | grep "ERRORS:" | grep -o "[0-9]*")

if [ "${ERRORS:-0}" -gt 0 ]; then
    echo "❌ Architecture check failed with $ERRORS errors. Fix before committing."
    exit 1
fi

echo "✅ Architecture check passed"
exit 0
```

### Option B: Install script
```bash
#!/bin/bash
# scripts/install_hooks.sh
cp scripts/pre-commit-hook.sh .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
echo "✅ Pre-commit hook installed"
```

Also add a Makefile target:
```makefile
hooks:
	@cp scripts/pre-commit-hook.sh .git/hooks/pre-commit
	@chmod +x .git/hooks/pre-commit
	@echo "✅ Pre-commit hook installed"
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ✅ | This ENFORCES the 5-layer rule |
| 2 | .env secrets | ✅ | Checker validates no secrets in code |
| 3 | models.yaml SSOT | ✅ | Checker validates no hardcoded models |
| 4 | Docker-first | ❌ | Runs on host, not in container |
| 5 | aria_memories writable | ❌ | Code only |
| 6 | No soul modification | ❌ | Not touching soul |

## Dependencies
None — `scripts/check_architecture.py` already exists and works.

## Verification
```bash
# 1. Hook script exists:
ls -la scripts/pre-commit-hook.sh
# EXPECTED: -rwxr-xr-x

# 2. Install script works:
./scripts/install_hooks.sh
ls -la .git/hooks/pre-commit
# EXPECTED: -rwxr-xr-x

# 3. Hook runs on commit:
git add -A && git commit --dry-run 2>&1 | head -5
# EXPECTED: "Running architecture check..." appears

# 4. Hook blocks bad commits (simulate):
# Add a test violation, try to commit, verify it's blocked
echo "from sqlalchemy import Column" > /tmp/test_violation.py
# (don't actually commit this — just verify the checker catches it)

# 5. Makefile target works:
make hooks
# EXPECTED: "Pre-commit hook installed"
```

## Prompt for Agent
```
Add a git pre-commit hook that runs the architecture checker.

**Files to read:**
- scripts/check_architecture.py (what it checks and how it reports)
- Makefile (add a `hooks` target)
- .git/hooks/ (check if any hooks already exist)

**Steps:**
1. Create scripts/pre-commit-hook.sh with architecture check
2. Create scripts/install_hooks.sh for easy installation
3. Add Makefile target `hooks`
4. Install the hook
5. Test with a dry-run commit
6. Verify it catches violations (create a temp test file with SQLAlchemy import)
```
