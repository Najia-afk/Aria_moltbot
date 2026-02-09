#!/usr/bin/env python3
"""Architecture lint — enforce DB ↔ SQLAlchemy ↔ API ↔ api_client ↔ Skills pattern."""
import re
import sys
from pathlib import Path

SCAN_DIRS = ["aria_skills", "aria_mind", "aria_agents"]
ALLOW_LIST = {"aria_skills/database"}  # Deprecated but still present

FORBIDDEN = [
    re.compile(r"^\s*(import|from)\s+(asyncpg|psycopg2|psycopg)\b"),
    re.compile(r"^\s*(import|from)\s+sqlalchemy\b"),  # Skills should not import SQLAlchemy directly
]

def check():
    violations = []
    warnings_list = []
    root = Path(__file__).resolve().parent.parent
    
    for scan_dir in SCAN_DIRS:
        d = root / scan_dir
        if not d.exists():
            continue
        for py_file in d.rglob("*.py"):
            rel = py_file.relative_to(root).as_posix()
            is_allowed = any(rel.startswith(a) for a in ALLOW_LIST)
            
            for i, line in enumerate(py_file.read_text(encoding="utf-8").splitlines(), 1):
                for pattern in FORBIDDEN:
                    if pattern.search(line):
                        entry = f"{rel}:{i}: {line.strip()}"
                        if is_allowed:
                            warnings_list.append(entry)
                        else:
                            violations.append(entry)
    
    if warnings_list:
        print("⚠️  WARNINGS (deprecated paths — allowed but flagged):")
        for w in warnings_list:
            print(f"  {w}")
        print()
    
    if violations:
        print("❌ ARCHITECTURE VIOLATIONS:")
        for v in violations:
            print(f"  {v}")
        print(f"\n{len(violations)} violation(s) found. Skills must use api_client, not direct DB.")
        return 1
    
    print("✅ Architecture check passed — no violations.")
    return 0

if __name__ == "__main__":
    sys.exit(check())
