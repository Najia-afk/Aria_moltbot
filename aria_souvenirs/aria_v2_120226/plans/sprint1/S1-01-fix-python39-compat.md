# S1-01: Upgrade Host Python to 3.12+ & Align Everything to 3.13
**Epic:** Sprint 1 — Critical Bugs | **Priority:** P0 | **Points:** 5 | **Phase:** 1

## Problem
The host Mac Mini runs **Python 3.9.6** (Apple system Python) while Docker containers already run **Python 3.13.12**. This mismatch causes:

1. `aria_agents/context.py` uses `str | None` (PEP 604, 3.10+) — works in Docker, breaks on host
2. `pytest` is run from the **host** shell, so it uses 3.9.6 → ImportError → **entire test suite broken**
3. `pyproject.toml` says `requires-python = ">=3.10"` and mypy targets `python_version = "3.10"` — the host doesn't even meet the project's own minimums
4. Any script/tool run locally (not in Docker) is stuck on 3.9

The real fix is **not** downgrading syntax — it's upgrading the host Python to match the containers.

## Current State
| Component | Python Version | Status |
|-----------|---------------|--------|
| Dockerfile (aria-api, aria-brain) | 3.13-slim | ✅ |
| stacks/sandbox/Dockerfile | 3.13-alpine | ✅ |
| pyproject.toml requires-python | >=3.10 | ⚠️ Should be >=3.12 |
| pyproject.toml classifiers | 3.10, 3.11, 3.12 | ⚠️ Missing 3.13 |
| pyproject.toml mypy target | 3.10 | ⚠️ Should be 3.12 |
| Host Mac Mini (system Python) | **3.9.6** | ❌ BROKEN |

## Root Cause
Apple ships Python 3.9.6 with Command Line Tools. The project evolved inside Docker (3.13) but the host was never upgraded. Tests and local scripts still invoke `/usr/bin/python3` (3.9.6).

## Fix

### Step 1: Install Python 3.12+ on the host
```bash
# Option A: Homebrew (recommended for macOS)
brew install python@3.13
# This installs to /opt/homebrew/bin/python3.13

# Create a symlink or alias so `python3` resolves to 3.13:
echo 'alias python3="/opt/homebrew/bin/python3.13"' >> ~/.zshrc
# OR add /opt/homebrew/bin first in PATH

# Verify:
python3 --version
# EXPECTED: Python 3.13.x
```

### Step 2: Update pyproject.toml
```toml
[project]
requires-python = ">=3.12"

classifiers = [
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
]

[tool.mypy]
python_version = "3.12"
```

### Step 3: Create/update venv with the new Python
```bash
# Create a project venv using the new Python:
/opt/homebrew/bin/python3.13 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Verify:
python3 --version   # 3.13.x inside venv
pytest --version     # works
```

### Step 4: Leave the modern syntax ALONE
`aria_agents/context.py` already uses correct modern Python (`str | None`, `dict[str, Any]`). **Do NOT downgrade it.** Once the host runs 3.12+, this syntax works everywhere.

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ❌ | Infrastructure change only |
| 2 | .env for secrets (zero in code) | ❌ | No secrets involved |
| 3 | models.yaml single source of truth | ❌ | No model references |
| 4 | Docker-first testing | ✅ | Docker already 3.13 — no change needed there |
| 5 | aria_memories only writable path | ❌ | Config change only |
| 6 | No soul modification | ❌ | Not touching soul files |

## Dependencies
None — this is the first ticket to execute. S1-08 depends on this.

## Verification
```bash
# 1. Host Python is 3.12+:
python3 --version
# EXPECTED: Python 3.12.x or Python 3.13.x

# 2. Docker Python matches:
docker exec aria-api python3 --version
# EXPECTED: Python 3.13.x

# 3. context.py imports cleanly on host:
python3 -c "from aria_agents.context import AgentContext; print('OK:', AgentContext(task='test'))"
# EXPECTED: OK: AgentContext(task='test', ...)

# 4. pytest can collect tests:
python3 -m pytest tests/ --collect-only 2>&1 | head -5
# EXPECTED: <Module ...> or collected N items (NOT ImportError)

# 5. pyproject.toml requires 3.12:
grep "requires-python" pyproject.toml
# EXPECTED: requires-python = ">=3.12"

# 6. mypy target updated:
grep "python_version" pyproject.toml
# EXPECTED: python_version = "3.12"

# 7. No need to check for PEP 604 — it's valid syntax on 3.12+
```

## Prompt for Agent
```
Upgrade the host Python to 3.12+ and align all project configs.

**Context:**
- Docker containers already run Python 3.13.12 — no changes needed there
- Host Mac Mini has Python 3.9.6 (Apple system) — this is the problem
- The code already uses modern syntax (str | None, dict[str, Any]) — do NOT downgrade it
- The fix is upgrading the host, not patching the code

**Files to modify:**
- pyproject.toml — update requires-python to ">=3.12", classifiers to include 3.13, mypy python_version to "3.12"

**Host setup (interactive — needs Shiva):**
1. brew install python@3.13
2. Verify: /opt/homebrew/bin/python3.13 --version
3. Update shell config so python3 resolves to 3.13
4. Create venv: /opt/homebrew/bin/python3.13 -m venv .venv
5. Install deps: source .venv/bin/activate && pip install -e ".[dev]"
6. Run tests: pytest tests/ --collect-only

**Verification:**
python3 --version  # must show 3.12+
python3 -c "from aria_agents.context import AgentContext; print('OK')"
python3 -m pytest tests/ --collect-only 2>&1 | head -5
```
