# S10-06: Verify No OpenClaw Imports Anywhere
**Epic:** E8 — Quality & Testing | **Priority:** P0 | **Points:** 1 | **Phase:** 10

## Problem
After Sprint 8's "OpenClaw Exorcism," we need a permanent guard test that verifies zero OpenClaw/clawdbot references exist in any Python file, Docker config, or deployment file. This test must pass before every production deployment — it's the final safety net.

## Root Cause
OpenClaw was deeply integrated throughout the codebase. Even after manual cleanup, stray references may survive in comments, docstrings, error messages, config keys, or import statements. A codebase-wide scan catches them all.

## Fix
### `tests/unit/test_no_openclaw.py`
```python
"""
Guard test: Verify ZERO OpenClaw/clawdbot references in the codebase.

This test scans every Python file, YAML, TOML, Dockerfile, and
shell script for any reference to OpenClaw or clawdbot. It MUST
pass before production deployment.

The only allowed exceptions are:
- This test file itself
- Git history / changelogs documenting the migration
- Files in aria_souvenirs/ (historical records)
"""
import os
import re
from pathlib import Path

import pytest

# Project root
ROOT = Path(__file__).resolve().parent.parent.parent

# Patterns to detect OpenClaw references
OPENCLAW_PATTERNS = [
    re.compile(r"\bopenclaw\b", re.IGNORECASE),
    re.compile(r"\bclawdbot\b", re.IGNORECASE),
    re.compile(r"\bopen_claw\b", re.IGNORECASE),
    re.compile(r"\bOPENCLAW\b"),
    re.compile(r"\bCLAWDBOT\b"),
    re.compile(r"openclaw[-_]config", re.IGNORECASE),
    re.compile(r"openclaw[-_]auth", re.IGNORECASE),
    re.compile(r"openclaw[-_]entrypoint", re.IGNORECASE),
    re.compile(r"from\s+openclaw", re.IGNORECASE),
    re.compile(r"import\s+openclaw", re.IGNORECASE),
]

# File extensions to scan
SCAN_EXTENSIONS = {
    ".py", ".yaml", ".yml", ".toml", ".cfg", ".ini",
    ".sh", ".bash", ".env.example", ".md",
}

# Files/directories to EXCLUDE from scanning
EXCLUDE_PATHS = {
    # This test file itself
    "tests/unit/test_no_openclaw.py",
    # Historical records / souvenirs — allowed to mention OpenClaw
    "aria_souvenirs",
    # Git-related
    ".git",
    # Build artifacts
    "__pycache__",
    ".venv",
    "node_modules",
    "build",
    "dist",
    ".eggs",
    # Documentation about the migration (changelogs)
    "CHANGELOG.md",
    # Sprint plans that reference the migration
    "plans/sprint",
}

# Dockerfile is special — scan it too
EXTRA_FILES = [
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
]


def _should_scan(path: Path) -> bool:
    """Check if a file should be scanned."""
    rel = path.relative_to(ROOT)
    rel_str = str(rel).replace("\\", "/")

    # Check exclusions
    for exclude in EXCLUDE_PATHS:
        if rel_str.startswith(exclude) or exclude in rel_str:
            return False

    # Check extension
    if path.suffix in SCAN_EXTENSIONS:
        return True

    # Check extra files by name
    if path.name in EXTRA_FILES:
        return True

    return False


def _scan_file(path: Path) -> list[tuple[int, str, str]]:
    """
    Scan a file for OpenClaw references.
    
    Returns list of (line_number, pattern_matched, line_content).
    """
    violations: list[tuple[int, str, str]] = []

    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except (OSError, UnicodeDecodeError):
        return violations

    for line_num, line in enumerate(content.splitlines(), start=1):
        for pattern in OPENCLAW_PATTERNS:
            if pattern.search(line):
                violations.append((line_num, pattern.pattern, line.strip()))
                break  # One violation per line is enough

    return violations


def _collect_all_files() -> list[Path]:
    """Collect all files to scan."""
    files: list[Path] = []

    for root, dirs, filenames in os.walk(ROOT):
        # Skip excluded directories
        dirs[:] = [
            d for d in dirs
            if d not in {"__pycache__", ".git", ".venv", "node_modules", "build", "dist", ".eggs"}
        ]

        for filename in filenames:
            filepath = Path(root) / filename
            if _should_scan(filepath):
                files.append(filepath)

    return sorted(files)


# ============================================================================
# Tests
# ============================================================================

class TestNoOpenClaw:
    """Guard tests: No OpenClaw references in production code."""

    def test_no_openclaw_in_python_files(self):
        """No Python file imports or references OpenClaw."""
        violations: list[str] = []

        for py_file in ROOT.rglob("*.py"):
            if not _should_scan(py_file):
                continue

            file_violations = _scan_file(py_file)
            if file_violations:
                rel_path = py_file.relative_to(ROOT)
                for line_num, pattern, line in file_violations:
                    violations.append(
                        f"  {rel_path}:{line_num} [{pattern}]: {line[:100]}"
                    )

        assert not violations, (
            f"OpenClaw references found in {len(violations)} Python locations:\n"
            + "\n".join(violations)
        )

    def test_no_openclaw_in_docker_configs(self):
        """No Docker/compose files reference OpenClaw."""
        violations: list[str] = []

        docker_files = [
            ROOT / "Dockerfile",
            ROOT / "stacks" / "brain" / "docker-compose.yml",
        ]
        # Also check any other docker-compose files
        for dc in ROOT.rglob("docker-compose*.yml"):
            if dc not in docker_files:
                docker_files.append(dc)
        for dc in ROOT.rglob("docker-compose*.yaml"):
            docker_files.append(dc)
        for dc in ROOT.rglob("Dockerfile*"):
            if dc not in docker_files:
                docker_files.append(dc)

        for docker_file in docker_files:
            if not docker_file.exists():
                continue
            # Skip if in excluded path
            rel = str(docker_file.relative_to(ROOT)).replace("\\", "/")
            if any(excl in rel for excl in EXCLUDE_PATHS):
                continue

            file_violations = _scan_file(docker_file)
            if file_violations:
                for line_num, pattern, line in file_violations:
                    violations.append(
                        f"  {docker_file.name}:{line_num} [{pattern}]: {line[:100]}"
                    )

        assert not violations, (
            f"OpenClaw references found in Docker configs:\n"
            + "\n".join(violations)
        )

    def test_no_clawdbot_service_in_compose(self):
        """docker-compose.yml must not define a 'clawdbot' service."""
        compose_path = ROOT / "stacks" / "brain" / "docker-compose.yml"
        if not compose_path.exists():
            pytest.skip("docker-compose.yml not found")

        content = compose_path.read_text(encoding="utf-8")

        # Check for clawdbot service definition
        assert "clawdbot:" not in content, (
            "docker-compose.yml still defines 'clawdbot' service — remove it!"
        )

    def test_no_openclaw_config_files(self):
        """OpenClaw config files must not exist."""
        forbidden_files = [
            ROOT / "stacks" / "brain" / "openclaw-config.json",
            ROOT / "stacks" / "brain" / "openclaw-auth-profiles.json",
            ROOT / "stacks" / "brain" / "openclaw-entrypoint.sh",
            ROOT / "aria_models" / "openclaw_config.py",
        ]

        existing = [f for f in forbidden_files if f.exists()]

        assert not existing, (
            f"OpenClaw config files still exist — delete them:\n"
            + "\n".join(f"  {f}" for f in existing)
        )

    def test_no_openclaw_env_vars(self):
        """No OPENCLAW_* environment variables in config files."""
        violations: list[str] = []
        env_pattern = re.compile(r"OPENCLAW_\w+", re.IGNORECASE)

        config_files = list(ROOT.rglob("*.env.example")) + list(ROOT.rglob(".env.example"))
        # Also check Python config files
        config_files.extend(ROOT.rglob("config*.py"))

        for config_file in config_files:
            if not _should_scan(config_file):
                continue
            try:
                content = config_file.read_text(encoding="utf-8", errors="ignore")
                for line_num, line in enumerate(content.splitlines(), start=1):
                    if env_pattern.search(line):
                        violations.append(
                            f"  {config_file.relative_to(ROOT)}:{line_num}: {line.strip()[:100]}"
                        )
            except OSError:
                continue

        assert not violations, (
            f"OPENCLAW_* env vars found:\n" + "\n".join(violations)
        )

    def test_no_openclaw_in_pyproject(self):
        """pyproject.toml has no OpenClaw references."""
        pyproject = ROOT / "pyproject.toml"
        content = pyproject.read_text(encoding="utf-8").lower()

        assert "openclaw" not in content, "pyproject.toml mentions openclaw"
        assert "clawdbot" not in content, "pyproject.toml mentions clawdbot"

    def test_comprehensive_scan(self):
        """Full codebase scan — the definitive check."""
        all_files = _collect_all_files()
        all_violations: list[str] = []

        for filepath in all_files:
            file_violations = _scan_file(filepath)
            if file_violations:
                rel_path = filepath.relative_to(ROOT)
                for line_num, pattern, line in file_violations:
                    all_violations.append(
                        f"  {rel_path}:{line_num} [{pattern}]: {line[:80]}"
                    )

        assert not all_violations, (
            f"OpenClaw references found in {len(all_violations)} locations across "
            f"{len(all_files)} scanned files:\n"
            + "\n".join(all_violations[:50])
            + (f"\n  ... and {len(all_violations) - 50} more" if len(all_violations) > 50 else "")
        )
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ❌ | Code quality guard |
| 2 | .env for secrets (zero in code) | ❌ | No secrets involved |
| 3 | models.yaml single source of truth | ❌ | No model references |
| 4 | Docker-first testing | ✅ | Must pass in Docker CI |
| 5 | aria_memories only writable path | ❌ | Read-only scan |
| 6 | No soul modification | ❌ | No soul access |

## Dependencies
- S8-01 through S8-06 must complete first (OpenClaw removal)
- S9-01 should complete first (pyproject.toml cleaned)

## Verification
```bash
# 1. Run guard test:
pytest tests/unit/test_no_openclaw.py -v
# EXPECTED: All tests pass (after Sprint 8 completion)

# 2. Quick manual check:
grep -rn "openclaw\|clawdbot\|OPENCLAW\|CLAWDBOT" --include="*.py" aria_engine/ aria_mind/ aria_skills/ aria_agents/ aria_models/ src/ | grep -v "aria_souvenirs" | grep -v "__pycache__" | grep -v "test_no_openclaw"
# EXPECTED: No output (zero matches)

# 3. Docker check:
grep -n "clawdbot" stacks/brain/docker-compose.yml || echo "OK: No clawdbot"
# EXPECTED: OK: No clawdbot
```

## Prompt for Agent
```
Create a comprehensive guard test that scans the entire codebase for OpenClaw references.

FILES TO READ FIRST:
- tests/unit/test_no_openclaw.py (this ticket's output)
- stacks/brain/docker-compose.yml (check for clawdbot service)
- pyproject.toml (check for openclaw keyword)
- aria_models/openclaw_config.py (should NOT exist after S8-03)

STEPS:
1. Create tests/unit/test_no_openclaw.py
2. Run the test — it will likely FAIL before Sprint 8 completes
3. After Sprint 8, all tests should pass
4. Add to CI pipeline as a required check

CONSTRAINTS:
- Exclude: this test file, aria_souvenirs/, .git/, __pycache__/
- Scan: .py, .yaml, .yml, .toml, .sh, Dockerfile, docker-compose.yml
- Patterns: openclaw, clawdbot, OPENCLAW, CLAWDBOT, open_claw
- Must catch: imports, config keys, env vars, comments, docstrings
- This is a BLOCKING test — production deploy fails if this test fails
```
