# S9-01: Update pyproject.toml for Python 3.13+
**Epic:** E7 — Python 3.13+ Modernization | **Priority:** P1 | **Points:** 1 | **Phase:** 9

## Problem
`pyproject.toml` still declares `requires-python = ">=3.12"` and includes stale classifiers referencing Python 3.10/3.11. The keywords list mentions "openclaw". New dependencies needed for `aria_engine` (`apscheduler>=4.0`, `aiohttp>=3.9`) are missing. The project must formally target Python 3.13+ to unlock modern stdlib features (TaskGroup, tomllib, JIT) and drop any OpenClaw-era references.

## Root Cause
The project file was last updated during the OpenClaw era. Python 3.13 was listed in classifiers but never enforced as the minimum. The `aria_engine` package needs runtime dependencies that aren't declared. No cleanup pass was done after the OpenClaw phase-out (Sprint 8).

## Fix
### `pyproject.toml`
```toml
[project]
name = "aria-blue"
version = "2.0.0"
description = "Autonomous AI agent platform with local-first LLM inference, modular skills, and multi-agent orchestration"
readme = "README.md"
requires-python = ">=3.13"
license = {file = "LICENSE"}
authors = [
    {name = "Najia-afk"}
]
keywords = ["ai", "agent", "autonomous", "llm", "moltbook", "multi-agent", "aria"]

classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "License :: Other/Proprietary License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.13",
    "Topic :: Scientific/Engineering :: Artificial Intelligence",
]

dependencies = [
    "httpx>=0.25.0",
    "asyncpg>=0.29.0",
    "pyyaml>=6.0",
    "python-dotenv>=1.0.0",
    "structlog>=24.0",
    "litellm>=1.55.0",
    "apscheduler>=4.0",
    "aiohttp>=3.9",
    "sqlalchemy[asyncio]>=2.0.30",
    "alembic>=1.13.0",
    "prometheus-client>=0.21.0",
    "websockets>=13.0",
    "uvicorn[standard]>=0.30.0",
    "fastapi>=0.115.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=4.1.0",
    "requests>=2.31.0",
    "black>=24.0.0",
    "ruff>=0.1.0",
    "mypy>=1.8.0",
    "freezegun>=1.4.0",
    "locust>=2.29.0",
    "memray>=1.14.0",
    "py-spy>=0.3.14",
    "pyupgrade>=3.17.0",
    "testcontainers>=4.0.0",
]

docker = [
    "docker>=7.0.0",
]

all = [
    "aria-blue[dev]",
    "aria-blue[docker]",
]

[project.urls]
Homepage = "https://datascience-adventure.xyz"
Repository = "https://github.com/Najia-afk/Aria_moltbot"
Issues = "https://github.com/Najia-afk/Aria_moltbot/issues"
License = "https://datascience-adventure.xyz/contact"

[project.scripts]
aria = "aria_mind.cli:main"
aria-health = "aria_mind.cli:health_check"
aria-engine = "aria_engine.entrypoint:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["aria_mind", "aria_skills", "aria_agents", "aria_engine"]

# ============================================================================
# pytest
# ============================================================================

[tool.pytest.ini_options]
minversion = "8.0"
addopts = [
    "-ra",
    "-q",
    "--strict-markers",
    "--asyncio-mode=auto",
]
testpaths = ["tests"]
pythonpath = ["."]
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    "unit: fast unit tests",
    "integration: requires mocked services",
    "docker: only runs in Docker container",
    "load: load/performance tests",
]
filterwarnings = [
    "ignore::DeprecationWarning",
]

# ============================================================================
# coverage
# ============================================================================

[tool.coverage.run]
source = ["src", "aria_skills", "aria_mind", "aria_models", "aria_agents", "aria_engine"]
branch = true
omit = ["*/tests/*", "*/__pycache__/*"]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError",
    "if TYPE_CHECKING:",
    "if __name__ == .__main__.:",
]
show_missing = true

# ============================================================================
# black
# ============================================================================

[tool.black]
line-length = 100
target-version = ["py313"]
include = '\.pyi?$'
exclude = '''
/(
    \.eggs
  | \.git
  | \.hatch
  | \.mypy_cache
  | \.tox
  | \.venv
  | _build
  | buck-out
  | build
  | dist
)/
'''

# ============================================================================
# ruff
# ============================================================================

[tool.ruff]
line-length = 100
target-version = "py313"

[tool.ruff.lint]
select = [
    "E",      # pycodestyle errors
    "W",      # pycodestyle warnings
    "F",      # Pyflakes
    "I",      # isort
    "B",      # flake8-bugbear
    "C4",     # flake8-comprehensions
    "UP",     # pyupgrade
    "ARG",    # flake8-unused-arguments
    "SIM",    # flake8-simplify
]
ignore = [
    "E501",   # line too long (handled by black)
    "B008",   # do not perform function calls in argument defaults
    "C901",   # too complex
    "ARG001", # unused function argument
]

[tool.ruff.lint.isort]
known-first-party = ["aria_mind", "aria_skills", "aria_agents", "aria_engine"]

# ============================================================================
# mypy
# ============================================================================

[tool.mypy]
python_version = "3.13"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = false
ignore_missing_imports = true
exclude = [
    "tests/",
    "build/",
    "dist/",
]

[[tool.mypy.overrides]]
module = "tests.*"
ignore_errors = true
```

### Verification script: `scripts/verify_pyproject.py`
```python
"""Verify pyproject.toml is correct for Python 3.13+ and has no OpenClaw references."""
import sys
import tomllib
from pathlib import Path


def main() -> int:
    pyproject_path = Path(__file__).resolve().parent.parent / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        config = tomllib.load(f)

    project = config["project"]
    errors: list[str] = []

    # 1. Check requires-python
    req_python = project.get("requires-python", "")
    if "3.13" not in req_python:
        errors.append(f"requires-python should target >=3.13, got: {req_python}")

    # 2. Check no OpenClaw keywords
    keywords = project.get("keywords", [])
    for kw in keywords:
        if "openclaw" in kw.lower() or "clawdbot" in kw.lower():
            errors.append(f"OpenClaw keyword found: {kw}")

    # 3. Check classifiers only list 3.13+
    classifiers = project.get("classifiers", [])
    for cls in classifiers:
        if "Python :: 3.10" in cls or "Python :: 3.11" in cls or "Python :: 3.12" in cls:
            errors.append(f"Stale Python classifier: {cls}")

    # 4. Check new dependencies present
    deps = project.get("dependencies", [])
    dep_names = [d.split(">=")[0].split("[")[0].strip() for d in deps]
    required = ["apscheduler", "aiohttp", "litellm", "sqlalchemy", "prometheus-client"]
    for req in required:
        if req not in dep_names:
            errors.append(f"Missing dependency: {req}")

    # 5. Check aria_engine in wheel packages
    wheel_packages = config.get("tool", {}).get("hatch", {}).get("build", {}).get("targets", {}).get("wheel", {}).get("packages", [])
    if "aria_engine" not in wheel_packages:
        errors.append("aria_engine not in wheel packages")

    # 6. Check version bumped
    version = project.get("version", "")
    if version.startswith("1."):
        errors.append(f"Version should be 2.x for v2 release, got: {version}")

    if errors:
        for e in errors:
            print(f"FAIL: {e}", file=sys.stderr)
        return 1

    print("OK: pyproject.toml validated for Python 3.13+")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ❌ | Config-only change |
| 2 | .env for secrets (zero in code) | ❌ | No secrets in pyproject.toml |
| 3 | models.yaml single source of truth | ❌ | No model references |
| 4 | Docker-first testing | ✅ | Dockerfile uses python:3.13-slim — must match |
| 5 | aria_memories only writable path | ❌ | No file writes |
| 6 | No soul modification | ❌ | No soul access |

## Dependencies
- S8-03 must complete first (OpenClaw Python module deleted)
- S8-04 must complete first (OPENCLAW_* constants removed)

## Verification
```bash
# 1. Parse with stdlib tomllib (proves 3.13+ syntax):
python -c "
import tomllib
from pathlib import Path
config = tomllib.loads(Path('pyproject.toml').read_text())
print('requires-python:', config['project']['requires-python'])
print('version:', config['project']['version'])
print('keywords:', config['project']['keywords'])
"
# EXPECTED: requires-python: >=3.13, version: 2.0.0, no "openclaw" keyword

# 2. No OpenClaw references:
python -c "
text = open('pyproject.toml').read().lower()
assert 'openclaw' not in text, 'OpenClaw reference found!'
assert 'clawdbot' not in text, 'Clawdbot reference found!'
print('OK: No OpenClaw references')
"
# EXPECTED: OK: No OpenClaw references

# 3. Verify all deps install:
pip install --dry-run -e ".[dev]" 2>&1 | tail -5
# EXPECTED: Would install ... (no errors)

# 4. Run verification script:
python scripts/verify_pyproject.py
# EXPECTED: OK: pyproject.toml validated for Python 3.13+
```

## Prompt for Agent
```
Update pyproject.toml for Python 3.13+ and remove all OpenClaw references.

FILES TO READ FIRST:
- pyproject.toml (full file — current config)
- Dockerfile (line 2 — confirms python:3.13-slim base)
- aria_engine/__init__.py (verify package exists)

STEPS:
1. Read all files above
2. Update pyproject.toml with all changes from the Fix section
3. Create scripts/verify_pyproject.py
4. Run verification commands

CONSTRAINTS:
- Constraint 4: Dockerfile already uses python:3.13-slim — pyproject.toml must match
- Version bump: 1.2.0 → 2.0.0 (major release — OpenClaw removed)
- Remove ALL OpenClaw/clawdbot references from keywords, description, comments
- Add aria_engine to wheel packages and isort known-first-party
- Add load test marker to pytest config
```
