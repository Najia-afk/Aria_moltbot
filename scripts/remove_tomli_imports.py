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
