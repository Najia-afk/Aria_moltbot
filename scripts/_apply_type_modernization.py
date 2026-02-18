"""
Direct type hint modernization — replaces legacy typing usage with Python 3.13+ builtins.
Handles both import cleanup and usage-site replacements.
"""
import re
import sys
from pathlib import Path

TARGET_DIRS = [
    "aria_engine",
    "aria_mind",
    "aria_skills",
    "aria_agents",
    "aria_models",
    "src",
    "tests",
]

# Simple replacements: old_typing_name -> builtin
SIMPLE_GENERICS = {
    "List": "list",
    "Dict": "dict",
    "Tuple": "tuple",
    "Set": "set",
    "FrozenSet": "frozenset",
    "Type": "type",
}

# These should stay in typing imports (not builtins)
KEEP_TYPING = {
    "Any", "ClassVar", "Final", "Protocol", "TypeVar",
    "TYPE_CHECKING", "TypeAlias", "Self", "Never", "override",
    "dataclass_transform", "NamedTuple", "TypedDict", "Literal",
    "Annotated", "get_type_hints", "runtime_checkable",
    "AsyncIterator", "AsyncGenerator", "Iterator", "Generator",
    "Callable", "Awaitable", "Coroutine", "Sequence", "Mapping",
    "MutableMapping", "MutableSequence", "Deque", "Counter",
    "OrderedDict", "DefaultDict", "ChainMap", "IO", "TextIO",
    "BinaryIO", "Pattern", "Match",
}

BUILTIN_REMOVALS = {"Optional", "Union", "List", "Dict", "Tuple", "Set", "FrozenSet", "Type"}


def replace_optional(content: str) -> str:
    """Replace Optional[X] with X | None, handling nested brackets."""
    # Match Optional[ then track bracket depth
    result = []
    i = 0
    while i < len(content):
        # Check for Optional[ at word boundary
        if content[i:].startswith("Optional["):
            # Make sure it's not part of a bigger word
            if i > 0 and (content[i-1].isalnum() or content[i-1] == '_'):
                result.append(content[i])
                i += 1
                continue
            # Find the matching ]
            start = i + len("Optional[")
            depth = 1
            j = start
            while j < len(content) and depth > 0:
                if content[j] == '[':
                    depth += 1
                elif content[j] == ']':
                    depth -= 1
                j += 1
            inner = content[start:j-1]
            result.append(inner)
            result.append(" | None")
            i = j
        else:
            result.append(content[i])
            i += 1
    return "".join(result)


def replace_union(content: str) -> str:
    """Replace Union[X, Y] with X | Y, handling nested brackets."""
    result = []
    i = 0
    while i < len(content):
        if content[i:].startswith("Union["):
            if i > 0 and (content[i-1].isalnum() or content[i-1] == '_'):
                result.append(content[i])
                i += 1
                continue
            start = i + len("Union[")
            depth = 1
            j = start
            while j < len(content) and depth > 0:
                if content[j] == '[':
                    depth += 1
                elif content[j] == ']':
                    depth -= 1
                j += 1
            inner = content[start:j-1]
            # Split by comma at depth 0
            parts = []
            current = []
            d = 0
            for ch in inner:
                if ch == '[':
                    d += 1
                elif ch == ']':
                    d -= 1
                if ch == ',' and d == 0:
                    parts.append("".join(current).strip())
                    current = []
                else:
                    current.append(ch)
            parts.append("".join(current).strip())
            result.append(" | ".join(parts))
            i = j
        else:
            result.append(content[i])
            i += 1
    return "".join(result)


def replace_simple_generics(content: str) -> str:
    """Replace List[X] -> list[X], Dict[K,V] -> dict[K,V], etc."""
    for old, new in SIMPLE_GENERICS.items():
        # Use word boundary to avoid partial matches
        pattern = re.compile(r'(?<![.\w])' + old + r'\[')
        content = pattern.sub(new + '[', content)
    return content


def clean_typing_import(content: str) -> str:
    """Remove builtin aliases from typing import lines."""
    def replace_import(m: re.Match) -> str:
        imports = [i.strip() for i in m.group(1).split(",")]
        remaining = [i for i in imports if i not in BUILTIN_REMOVALS]
        if not remaining:
            return ""
        return f"from typing import {', '.join(remaining)}\n"

    content = re.sub(
        r"from typing import ([^\n]+)\n",
        replace_import,
        content,
    )
    return content


def process_file(path: Path) -> list[str]:
    """Process a single file."""
    content = path.read_text(encoding="utf-8")
    original = content
    changes = []

    # 1. Remove from __future__ import annotations
    if "from __future__ import annotations\n" in content:
        content = content.replace("from __future__ import annotations\n", "")
        changes.append("Removed from __future__ import annotations")

    # 2. Replace Optional[X] -> X | None
    new = replace_optional(content)
    if new != content:
        content = new
        changes.append("Optional[X] → X | None")

    # 3. Replace Union[X, Y] -> X | Y
    new = replace_union(content)
    if new != content:
        content = new
        changes.append("Union[X, Y] → X | Y")

    # 4. Replace simple generics
    new = replace_simple_generics(content)
    if new != content:
        content = new
        changes.append("List/Dict/Tuple/Set → list/dict/tuple/set")

    # 5. Clean typing imports
    new = clean_typing_import(content)
    if new != content:
        content = new
        changes.append("Cleaned typing imports")

    if content != original:
        path.write_text(content, encoding="utf-8")
    return changes


def main() -> int:
    total = 0
    for d in TARGET_DIRS:
        dp = Path(d)
        if not dp.exists():
            continue
        for f in sorted(dp.rglob("*.py")):
            if "__pycache__" in str(f):
                continue
            changes = process_file(f)
            if changes:
                total += 1
                print(f"{f}: {', '.join(changes)}")

    print(f"\nTotal files modified: {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
