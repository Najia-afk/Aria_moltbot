"""
TICKET-33 · Column Coverage Report
====================================
Reads the ORM models from src.api.db.models and introspects every table's
columns.  Then inspects each API router to infer which columns appear in the
JSON responses.  Prints a coverage matrix.

This is a *reporting* test — it always passes but prints useful diagnostics.
Gracefully skips if SQLAlchemy or the models can't be imported (e.g. missing
psycopg / asyncpg at import time).
"""


import importlib
import inspect
import re
import sys
import textwrap
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Try to import the ORM models
# ---------------------------------------------------------------------------

_MODELS_MODULE = None
_IMPORT_ERROR: str | None = None

try:
    # Ensure the src/api package is importable
    _api_root = Path(__file__).resolve().parent.parent / "src" / "api"
    if str(_api_root) not in sys.path:
        sys.path.insert(0, str(_api_root))

    from db.models import Base  # type: ignore[import-untyped]
    _MODELS_MODULE = importlib.import_module("db.models")
except Exception as exc:
    _IMPORT_ERROR = str(exc)


def _get_orm_tables() -> dict[str, list[str]]:
    """Return {tablename: [col1, col2, …]} for every ORM model."""
    if _MODELS_MODULE is None:
        return {}
    tables: dict[str, list[str]] = {}
    for name, cls in inspect.getmembers(_MODELS_MODULE, inspect.isclass):
        tablename = getattr(cls, "__tablename__", None)
        if tablename is None:
            continue
        # Use SQLAlchemy's column introspection
        try:
            cols = [c.name for c in cls.__table__.columns]
        except Exception:
            cols = []
        tables[tablename] = cols
    return tables


def _scan_router_files() -> dict[str, set[str]]:
    """Regex-scan each router .py file for column / key names used in dicts.

    Returns {router_name: {col_name, …}}.
    """
    routers_dir = Path(__file__).resolve().parent.parent / "src" / "api" / "routers"
    if not routers_dir.is_dir():
        return {}

    # Pattern captures quoted keys in dict literals and .get("key") calls
    key_pattern = re.compile(
        r'''(?:["'](\w+)["']\s*:|\.get\(\s*["'](\w+)["'])'''
    )
    results: dict[str, set[str]] = {}
    for py_file in sorted(routers_dir.glob("*.py")):
        if py_file.name.startswith("__"):
            continue
        router_name = py_file.stem
        text = py_file.read_text(encoding="utf-8", errors="ignore")
        keys: set[str] = set()
        for m in key_pattern.finditer(text):
            keys.add(m.group(1) or m.group(2))
        results[router_name] = keys
    return results


# ============================================================================
#  Test
# ============================================================================

@pytest.mark.integration
class TestColumnCoverage:

    def test_orm_tables_discovered(self):
        """Verify we can discover ORM tables (skip if import fails)."""
        if _IMPORT_ERROR:
            pytest.skip(f"ORM import failed: {_IMPORT_ERROR}")
        tables = _get_orm_tables()
        assert len(tables) > 0, "No ORM tables discovered"
        print(f"\n{'='*60}")
        print(f" ORM Tables: {len(tables)}")
        print(f"{'='*60}")
        for tbl, cols in sorted(tables.items()):
            print(f"  {tbl:<30} ({len(cols)} cols): {', '.join(cols)}")

    def test_router_key_scan(self):
        """Scan router files for referenced column names."""
        router_keys = _scan_router_files()
        if not router_keys:
            pytest.skip("No router files found")
        print(f"\n{'='*60}")
        print(f" Router files scanned: {len(router_keys)}")
        print(f"{'='*60}")
        for name, keys in sorted(router_keys.items()):
            print(f"  {name:<25} ({len(keys)} keys)")

    def test_coverage_matrix(self):
        """Build and print the coverage matrix: table → exposed columns."""
        if _IMPORT_ERROR:
            pytest.skip(f"ORM import failed: {_IMPORT_ERROR}")

        tables = _get_orm_tables()
        router_keys = _scan_router_files()
        all_router_keys = set()
        for keys in router_keys.values():
            all_router_keys |= keys

        print(f"\n{'='*72}")
        print(f" COLUMN COVERAGE MATRIX")
        print(f"{'='*72}")
        total_cols = 0
        covered_cols = 0

        for tbl, cols in sorted(tables.items()):
            exposed = [c for c in cols if c in all_router_keys]
            not_exposed = [c for c in cols if c not in all_router_keys]
            pct = (len(exposed) / len(cols) * 100) if cols else 0
            total_cols += len(cols)
            covered_cols += len(exposed)

            print(f"\n  {tbl} — {len(exposed)}/{len(cols)} ({pct:.0f}%)")
            if exposed:
                print(f"    ✓ exposed : {', '.join(exposed)}")
            if not_exposed:
                print(f"    ✗ missing : {', '.join(not_exposed)}")

        overall = (covered_cols / total_cols * 100) if total_cols else 0
        print(f"\n{'─'*72}")
        print(f"  OVERALL: {covered_cols}/{total_cols} columns referenced ({overall:.0f}%)")
        print(f"{'─'*72}")

        # This test always passes — it's a reporting tool
        assert True
