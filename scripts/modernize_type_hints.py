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
