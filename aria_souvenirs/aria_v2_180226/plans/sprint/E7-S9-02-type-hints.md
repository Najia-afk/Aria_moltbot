# S9-02: Modernize Type Hints (Python 3.13+ Syntax)
**Epic:** E7 — Python 3.13+ Modernization | **Priority:** P2 | **Points:** 3 | **Phase:** 9

## Problem
The codebase uses legacy `typing` module imports everywhere: `Optional[X]`, `Union[X, Y]`, `List[X]`, `Dict[K, V]`, `Tuple[X, ...]`. Python 3.10+ supports `X | None`, `X | Y`, `list[X]`, `dict[K, V]`, `tuple[X, ...]` natively. Python 3.12+ adds the `type` statement for aliases. Since we now target 3.13+, all code should use modern syntax for readability and consistency.

## Root Cause
Code was written over multiple Python versions (3.10–3.12). Contributors used `from typing import ...` out of habit. No automated enforcement existed. The `pyupgrade` tool was in dev dependencies but never enforced in CI.

## Fix
### `scripts/modernize_type_hints.py`
```python
"""
Automated type hint modernization for Python 3.13+.

Runs pyupgrade on all Python files, then applies manual fixes
for patterns pyupgrade doesn't catch.

Usage:
    python scripts/modernize_type_hints.py [--dry-run] [--path aria_engine]
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

# Directories to process in priority order
TARGET_DIRS = [
    "aria_engine",
    "aria_mind",
    "aria_skills",
    "aria_agents",
    "aria_models",
    "src",
    "tests",
]

# Regex patterns for manual fixes pyupgrade may miss
MANUAL_PATTERNS: list[tuple[re.Pattern[str], str, str]] = [
    # Remove unused typing imports after pyupgrade
    (
        re.compile(r"^from typing import\s*$", re.MULTILINE),
        "",
        "Remove empty typing import",
    ),
    # Clean up single-item typing imports that are now builtins
    (
        re.compile(
            r"from typing import (Any|ClassVar|Final|Protocol|TypeVar|"
            r"TYPE_CHECKING|TypeAlias|Self|Never|override|dataclass_transform|"
            r"NamedTuple|TypedDict|Literal|Annotated|get_type_hints|"
            r"runtime_checkable|AsyncIterator|AsyncGenerator|Iterator|Generator|"
            r"Callable|Awaitable|Coroutine|Sequence|Mapping|MutableMapping|"
            r"MutableSequence|Set|FrozenSet|Deque|Counter|OrderedDict|"
            r"DefaultDict|ChainMap|IO|TextIO|BinaryIO|Pattern|Match)\b"
        ),
        None,  # Keep these — they're still needed from typing
        "Keep valid typing imports",
    ),
]


def run_pyupgrade(path: Path, dry_run: bool = False) -> int:
    """Run pyupgrade on a single file."""
    cmd = [
        sys.executable, "-m", "pyupgrade",
        "--py313-plus",
        str(path),
    ]
    if dry_run:
        cmd.insert(-1, "--keep-percent-format")  # conservative in dry-run
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode


def apply_manual_fixes(path: Path, dry_run: bool = False) -> list[str]:
    """Apply regex-based fixes that pyupgrade doesn't handle."""
    content = path.read_text(encoding="utf-8")
    original = content
    changes: list[str] = []

    # Remove `from __future__ import annotations` — not needed on 3.13+
    if "from __future__ import annotations" in content:
        content = content.replace("from __future__ import annotations\n", "")
        changes.append("Removed `from __future__ import annotations`")

    # Replace `typing.Optional[X]` inline references
    optional_pat = re.compile(r"typing\.Optional\[([^\]]+)\]")
    if optional_pat.search(content):
        content = optional_pat.sub(r"\1 | None", content)
        changes.append("Replaced typing.Optional[X] → X | None")

    # Replace `typing.Union[X, Y]` inline references
    union_pat = re.compile(r"typing\.Union\[([^\]]+)\]")
    if union_pat.search(content):
        def union_repl(m: re.Match[str]) -> str:
            args = [a.strip() for a in m.group(1).split(",")]
            return " | ".join(args)
        content = union_pat.sub(union_repl, content)
        changes.append("Replaced typing.Union[X, Y] → X | Y")

    # Clean up typing imports that are no longer needed
    # After pyupgrade converts Optional→X|None, List→list, etc.,
    # the imports may be orphaned
    typing_import_pat = re.compile(
        r"from typing import ([^\n]+)\n"
    )
    match = typing_import_pat.search(content)
    if match:
        imports = [i.strip() for i in match.group(1).split(",")]
        # These are now builtins in 3.13+
        builtins_313 = {
            "Optional", "Union", "List", "Dict", "Tuple",
            "Set", "FrozenSet", "Type",
        }
        remaining = [i for i in imports if i not in builtins_313]
        if len(remaining) < len(imports):
            removed = [i for i in imports if i in builtins_313]
            changes.append(f"Removed builtin type imports: {', '.join(removed)}")
            if remaining:
                new_import = f"from typing import {', '.join(remaining)}\n"
                content = typing_import_pat.sub(new_import, content, count=1)
            else:
                content = typing_import_pat.sub("", content, count=1)

    if content != original:
        if not dry_run:
            path.write_text(content, encoding="utf-8")
        return changes
    return []


def process_directory(dir_path: Path, dry_run: bool = False) -> dict[str, list[str]]:
    """Process all Python files in a directory."""
    results: dict[str, list[str]] = {}
    if not dir_path.exists():
        return results

    for py_file in sorted(dir_path.rglob("*.py")):
        if "__pycache__" in str(py_file):
            continue

        changes: list[str] = []

        # Step 1: Run pyupgrade
        rc = run_pyupgrade(py_file, dry_run=dry_run)
        if rc == 0:
            changes.append("pyupgrade: applied fixes")

        # Step 2: Manual fixes
        manual = apply_manual_fixes(py_file, dry_run=dry_run)
        changes.extend(manual)

        if changes:
            results[str(py_file)] = changes

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Modernize type hints to Python 3.13+")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without applying")
    parser.add_argument("--path", type=str, default=None, help="Process a specific directory")
    args = parser.parse_args()

    dirs = [args.path] if args.path else TARGET_DIRS
    total_files = 0

    for dir_name in dirs:
        dir_path = Path(dir_name)
        print(f"\n{'='*60}")
        print(f"Processing: {dir_path}")
        print(f"{'='*60}")

        results = process_directory(dir_path, dry_run=args.dry_run)
        total_files += len(results)

        for filepath, changes in results.items():
            print(f"\n  {filepath}:")
            for change in changes:
                print(f"    - {change}")

    print(f"\n{'='*60}")
    print(f"Total files modified: {total_files}")
    if args.dry_run:
        print("(dry-run mode — no files were changed)")
    print(f"{'='*60}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

### Example transformations applied across codebase:

#### Before (`aria_engine/llm_gateway.py`):
```python
from typing import Any, AsyncIterator, Dict, List, Optional

@dataclass
class LLMResponse:
    content: str
    thinking: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    model: str = ""

class LLMGateway:
    def __init__(self, config: EngineConfig):
        self._circuit_opened_at: Optional[float] = None
        self._latency_samples: List[float] = []

    def _load_models(self) -> Dict[str, Any]: ...
    def _get_fallback_chain(self) -> List[str]: ...

    async def complete(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> LLMResponse: ...
```

#### After:
```python
from typing import Any, AsyncIterator

@dataclass
class LLMResponse:
    content: str
    thinking: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    model: str = ""

class LLMGateway:
    def __init__(self, config: EngineConfig):
        self._circuit_opened_at: float | None = None
        self._latency_samples: list[float] = []

    def _load_models(self) -> dict[str, Any]: ...
    def _get_fallback_chain(self) -> list[str]: ...

    async def complete(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse: ...
```

#### Complex type alias (Python 3.12+ `type` statement):
```python
# Before:
from typing import TypeAlias
MessageList: TypeAlias = list[dict[str, str]]
ToolDefinitions: TypeAlias = list[dict[str, Any]]

# After:
type MessageList = list[dict[str, str]]
type ToolDefinitions = list[dict[str, Any]]
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ❌ | Syntax-only refactor |
| 2 | .env for secrets (zero in code) | ❌ | No secrets involved |
| 3 | models.yaml single source of truth | ❌ | No model references |
| 4 | Docker-first testing | ✅ | Must pass `ruff check` and `mypy` in Docker |
| 5 | aria_memories only writable path | ❌ | Source code edits only |
| 6 | No soul modification | ❌ | No soul access |

## Dependencies
- S9-01 must complete first (pyproject.toml targets 3.13+)
- All Sprint 1–8 code must be merged (we modernize the final codebase)

## Verification
```bash
# 1. Run the modernization script (dry-run first):
python scripts/modernize_type_hints.py --dry-run
# EXPECTED: List of files and changes

# 2. Apply changes:
python scripts/modernize_type_hints.py
# EXPECTED: Files modified with modern type hints

# 3. Verify no legacy typing imports remain for builtins:
python -c "
import subprocess, sys
result = subprocess.run(
    ['grep', '-rn', 'from typing import.*Optional', '--include=*.py',
     'aria_engine/', 'aria_mind/', 'aria_skills/', 'aria_agents/'],
    capture_output=True, text=True
)
if result.stdout.strip():
    print('FAIL: Legacy Optional imports found:')
    print(result.stdout)
    sys.exit(1)
print('OK: No legacy Optional imports')
"
# EXPECTED: OK: No legacy Optional imports

# 4. Verify ruff passes:
ruff check aria_engine/ aria_mind/ aria_skills/ aria_agents/ --select UP
# EXPECTED: All checks passed!

# 5. Verify mypy passes:
mypy aria_engine/ --python-version 3.13
# EXPECTED: Success: no issues found
```

## Prompt for Agent
```
Modernize all type hints across the codebase to Python 3.13+ native syntax.

FILES TO READ FIRST:
- pyproject.toml (verify requires-python >= 3.13)
- scripts/modernize_type_hints.py (the automation script from this ticket)
- aria_engine/llm_gateway.py (example file with heavy typing usage)
- aria_engine/chat_engine.py (example file with heavy typing usage)
- aria_engine/agent_pool.py (example file with heavy typing usage)
- aria_skills/base.py (skill base class with typing)

STEPS:
1. Read all files above to understand current type hint usage
2. Create scripts/modernize_type_hints.py
3. Run in dry-run mode to review changes
4. Apply changes
5. Fix any ruff/mypy errors introduced
6. Run verification commands

CONSTRAINTS:
- Keep `from typing import Any` — Any is still needed
- Keep `from typing import TYPE_CHECKING` — used for circular imports
- Keep `from typing import TypeVar, Protocol, Self` — not builtins
- Keep `from typing import AsyncIterator, AsyncGenerator` — still from typing
- Replace ONLY: Optional, Union, List, Dict, Tuple, Set, FrozenSet, Type
- Process aria_engine/ first, then aria_mind/, aria_skills/, aria_agents/
- Do NOT touch files in aria_souvenirs/ or docs/
```
