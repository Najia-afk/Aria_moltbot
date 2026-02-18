# S9-04: Use tomllib for Config Parsing
**Epic:** E7 — Python 3.13+ Modernization | **Priority:** P2 | **Points:** 1 | **Phase:** 9

## Problem
Some code paths use the third-party `tomli` or `toml` packages to parse TOML files (e.g., `pyproject.toml` for version info, config files). Python 3.11+ includes `tomllib` in the standard library. Since we target 3.13+, we should use the stdlib module and remove the third-party dependency.

## Root Cause
The `tomli` package was needed when supporting Python 3.10 and earlier. Now that the minimum is 3.13, the stdlib `tomllib` provides identical read-only TOML parsing. The third-party dep was never removed from imports.

## Fix
### `aria_engine/config_loader.py`
```python
"""
Config loader using stdlib tomllib (Python 3.11+).

Replaces third-party tomli/toml with stdlib tomllib for
reading pyproject.toml and any .toml configuration files.
"""
import logging
import tomllib
from pathlib import Path
from typing import Any

logger = logging.getLogger("aria.engine.config_loader")


def load_toml(path: str | Path) -> dict[str, Any]:
    """
    Load a TOML file using stdlib tomllib.
    
    Args:
        path: Path to .toml file
        
    Returns:
        Parsed TOML as dict
        
    Raises:
        FileNotFoundError: If path doesn't exist
        tomllib.TOMLDecodeError: If TOML is malformed
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"TOML file not found: {path}")
    
    with open(path, "rb") as f:
        data = tomllib.load(f)
    
    logger.debug("Loaded TOML config: %s (%d keys)", path.name, len(data))
    return data


def load_pyproject() -> dict[str, Any]:
    """
    Load pyproject.toml from project root.
    
    Walks up from current file to find pyproject.toml.
    Returns the full parsed config.
    """
    # Search from current file up to root
    search = Path(__file__).resolve().parent
    for _ in range(10):  # max depth
        candidate = search / "pyproject.toml"
        if candidate.exists():
            return load_toml(candidate)
        search = search.parent
    
    raise FileNotFoundError("pyproject.toml not found in parent directories")


def get_project_version() -> str:
    """Get project version from pyproject.toml."""
    config = load_pyproject()
    return config.get("project", {}).get("version", "0.0.0")


def get_project_name() -> str:
    """Get project name from pyproject.toml."""
    config = load_pyproject()
    return config.get("project", {}).get("name", "aria-blue")


def get_python_requirement() -> str:
    """Get requires-python from pyproject.toml."""
    config = load_pyproject()
    return config.get("project", {}).get("requires-python", ">=3.13")


def load_engine_config(config_path: str | Path | None = None) -> dict[str, Any]:
    """
    Load engine-specific TOML config if it exists.
    
    Looks for `aria_engine.toml` in standard locations:
    1. Explicit path (if provided)
    2. ./aria_engine.toml
    3. ./config/aria_engine.toml
    4. /app/config/aria_engine.toml (Docker)
    
    Returns empty dict if no config file found (uses env vars as fallback).
    """
    if config_path:
        return load_toml(config_path)
    
    candidates = [
        Path("aria_engine.toml"),
        Path("config/aria_engine.toml"),
        Path("/app/config/aria_engine.toml"),
    ]
    
    for candidate in candidates:
        if candidate.exists():
            logger.info("Found engine config: %s", candidate)
            return load_toml(candidate)
    
    logger.debug("No aria_engine.toml found — using environment variables only")
    return {}
```

### `scripts/remove_tomli_imports.py`
```python
"""
Remove all third-party tomli/toml imports and replace with stdlib tomllib.

Scans all Python files and replaces:
  - `import tomli` → `import tomllib`
  - `import toml` → `import tomllib`
  - `from tomli import ...` → removed (use tomllib directly)
  - `tomli.load(...)` → `tomllib.load(...)`
  - `tomli.loads(...)` → `tomllib.loads(...)`
  - `toml.load(...)` → `tomllib.load(...)` (with binary mode fix)
"""
import re
import sys
from pathlib import Path


TARGET_DIRS = ["aria_engine", "aria_mind", "aria_skills", "aria_agents", "aria_models", "src", "tests"]


def process_file(path: Path) -> list[str]:
    """Process a single Python file, replacing tomli/toml with tomllib."""
    content = path.read_text(encoding="utf-8")
    original = content
    changes: list[str] = []

    # Replace import statements
    if "import tomli" in content:
        content = content.replace("import tomli\n", "import tomllib\n")
        content = content.replace("from tomli ", "# removed: from tomli ")
        changes.append("Replaced `import tomli` → `import tomllib`")

    if re.search(r"^import toml\b", content, re.MULTILINE):
        content = re.sub(r"^import toml\b", "import tomllib", content, flags=re.MULTILINE)
        changes.append("Replaced `import toml` → `import tomllib`")

    # Replace function calls
    if "tomli.load(" in content:
        content = content.replace("tomli.load(", "tomllib.load(")
        changes.append("Replaced tomli.load() → tomllib.load()")

    if "tomli.loads(" in content:
        content = content.replace("tomli.loads(", "tomllib.loads(")
        changes.append("Replaced tomli.loads() → tomllib.loads()")

    if "toml.load(" in content:
        content = content.replace("toml.load(", "tomllib.load(")
        changes.append("Replaced toml.load() → tomllib.load() (ensure binary mode!)")

    if "toml.loads(" in content:
        content = content.replace("toml.loads(", "tomllib.loads(")
        changes.append("Replaced toml.loads() → tomllib.loads()")

    # Fix file open mode: tomllib requires binary mode
    # Replace: open(path) or open(path, "r") with open(path, "rb") when followed by tomllib.load
    text_open_pat = re.compile(
        r'open\(([^,)]+)\)\s*as\s+(\w+):\s*\n(\s+)(\w+)\s*=\s*tomllib\.load\(\2\)'
    )
    if text_open_pat.search(content):
        content = text_open_pat.sub(
            r'open(\1, "rb") as \2:\n\3\4 = tomllib.load(\2)',
            content,
        )
        changes.append("Fixed file open to binary mode for tomllib")

    if content != original:
        path.write_text(content, encoding="utf-8")

    return changes


def main() -> int:
    total = 0
    for dir_name in TARGET_DIRS:
        dir_path = Path(dir_name)
        if not dir_path.exists():
            continue
        for py_file in dir_path.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            changes = process_file(py_file)
            if changes:
                total += 1
                print(f"{py_file}:")
                for c in changes:
                    print(f"  - {c}")

    print(f"\nTotal files modified: {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ❌ | Config utility — infrastructure layer |
| 2 | .env for secrets (zero in code) | ✅ | Config files must not contain secrets |
| 3 | models.yaml single source of truth | ❌ | TOML config, not model config |
| 4 | Docker-first testing | ✅ | Must work in Docker (Python 3.13 stdlib) |
| 5 | aria_memories only writable path | ❌ | Config reading only |
| 6 | No soul modification | ❌ | No soul access |

## Dependencies
- S9-01 must complete first (pyproject.toml declares 3.13+)
- S1-01 must complete first (aria_engine package exists)

## Verification
```bash
# 1. No tomli/toml imports remain:
python -c "
import subprocess, sys
for pkg in ['tomli', 'import toml']:
    result = subprocess.run(
        ['grep', '-rn', pkg, '--include=*.py',
         'aria_engine/', 'aria_mind/', 'aria_skills/', 'aria_agents/', 'aria_models/', 'src/'],
        capture_output=True, text=True
    )
    lines = [l for l in result.stdout.strip().split('\n') if l and 'tomllib' not in l]
    if lines:
        print(f'FAIL: {pkg} still imported:')
        for l in lines:
            print(f'  {l}')
        sys.exit(1)
print('OK: No third-party TOML imports')
"
# EXPECTED: OK: No third-party TOML imports

# 2. tomllib works:
python -c "
import tomllib
from pathlib import Path
with open('pyproject.toml', 'rb') as f:
    data = tomllib.load(f)
print('version:', data['project']['version'])
print('requires-python:', data['project']['requires-python'])
"
# EXPECTED: version: 2.0.0, requires-python: >=3.13

# 3. Config loader works:
python -c "
from aria_engine.config_loader import get_project_version, get_python_requirement
print('version:', get_project_version())
print('python:', get_python_requirement())
"
# EXPECTED: version: 2.0.0, python: >=3.13

# 4. tomli not in dependencies:
python -c "
with open('pyproject.toml') as f:
    text = f.read()
assert 'tomli' not in text.lower() or 'tomllib' in text, 'tomli still in pyproject.toml!'
print('OK: No tomli dependency')
"
# EXPECTED: OK: No tomli dependency
```

## Prompt for Agent
```
Replace all third-party tomli/toml usage with stdlib tomllib (Python 3.11+).

FILES TO READ FIRST:
- pyproject.toml (check for tomli in dependencies)
- aria_engine/config.py (may use toml parsing)
- aria_models/loader.py (may parse models.yaml — uses PyYAML not TOML, but check)
- grep -rn "import tomli\|import toml\|from tomli\|from toml" --include=*.py

STEPS:
1. Search codebase for all tomli/toml imports
2. Create aria_engine/config_loader.py with stdlib tomllib
3. Run scripts/remove_tomli_imports.py to replace all references
4. Remove tomli from pyproject.toml dependencies if present
5. Verify no third-party TOML packages remain
6. Run verification commands

CONSTRAINTS:
- tomllib.load() requires binary mode ("rb") — fix any text-mode opens
- tomllib is READ-ONLY — if any code writes TOML, keep tomli-w or use json instead
- Do not touch models.yaml — it uses PyYAML (YAML, not TOML)
```
