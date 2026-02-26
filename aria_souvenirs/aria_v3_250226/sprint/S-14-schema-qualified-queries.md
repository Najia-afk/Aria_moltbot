# S-14: Verify Schema-Qualified Table References
**Epic:** E9 — Schema Cleanup | **Priority:** P1 | **Points:** 3 | **Phase:** 2

## Problem
The production DB has 3 schemas: `aria_data`, `aria_engine`, `public`. Some tables appear in both `public` and their correct schema (legacy from early development). If any ORM model or query references `public.table_name` (or just `table_name` without schema, which defaults to `public`), it may be hitting the wrong copy.

This is a data integrity risk: writes may go to `public.sessions` instead of `aria_engine.sessions`, leaving the correct table stale or empty.

## Root Cause
Early development used the `public` schema by default. When `aria_data` and `aria_engine` schemas were introduced, tables were migrated but the `public` copies were not always dropped. ORM models may not have been updated with explicit `__table_args__ = {"schema": "aria_engine"}`.

## Fix

### Fix 1: Audit all ORM models for schema declaration
**Files:** `src/api/` — find all SQLAlchemy model files

For each model, verify:
```python
class Session(Base):
    __tablename__ = "sessions"
    __table_args__ = {"schema": "aria_engine"}  # MUST exist
```

If `__table_args__` is missing or `schema` is not set, the table defaults to `public`.

### Fix 2: Audit all raw SQL (if any exists)
Search the entire codebase for raw SQL:
```bash
grep -rn 'text(' src/ aria_engine/ aria_skills/
grep -rn 'execute(' src/ aria_engine/ aria_skills/
grep -rn 'SELECT\|INSERT\|UPDATE\|DELETE' src/ aria_engine/ aria_skills/ --include='*.py'
```

Any raw SQL MUST use schema-qualified names: `aria_engine.sessions`, not `sessions`.

**NOTE:** Per Constraint #1, there should be ZERO direct SQL. If found, it's a violation — file a sub-ticket.

### Fix 3: Audit GraphQL resolvers
**Files:** `src/api/` — GraphQL resolvers
Ensure all database queries go through the ORM, which uses schema-qualified models. No resolver should construct raw SQL.

### Fix 4: Create verification script
**File:** `scripts/verify_schema_refs.py` (NEW)
```python
"""Verify all ORM models use explicit schema declarations."""
import ast, os, sys

issues = []
for root, dirs, files in os.walk("src/api"):
    for f in files:
        if not f.endswith(".py"):
            continue
        path = os.path.join(root, f)
        with open(path) as fh:
            tree = ast.parse(fh.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                has_tablename = any(
                    isinstance(n, ast.Assign) and any(
                        t.attr == "__tablename__" for t in n.targets if hasattr(t, "attr")
                    ) for n in node.body
                )
                has_schema = any(
                    "__table_args__" in ast.dump(n) and "schema" in ast.dump(n)
                    for n in node.body
                )
                if has_tablename and not has_schema:
                    issues.append(f"{path}:{node.lineno} — {node.name} missing schema in __table_args__")

if issues:
    print("SCHEMA ISSUES FOUND:")
    for i in issues:
        print(f"  ✗ {i}")
    sys.exit(1)
else:
    print("✓ All ORM models have explicit schema declarations")
```

### Fix 5: Fix any models missing schema
For each model found in Fix 1 without explicit schema, add the correct schema:
- Tables in `aria_engine.*` → `{"schema": "aria_engine"}`
- Tables in `aria_data.*` → `{"schema": "aria_data"}`
- No table should target `public`

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer architecture | ✅ | **CRITICAL** — NO direct SQL. All via ORM. |
| 2 | .env for secrets | ❌ | |
| 3 | models.yaml truth | ❌ | |
| 4 | Docker-first testing | ✅ | Test queries hit correct schema |
| 5 | aria_memories writable | ❌ | |
| 6 | No soul modification | ❌ | |

**Direct SQL Violations:** If ANY direct SQL is found, it must be replaced with ORM calls. This is non-negotiable per Constraint #1.

## Dependencies
- None (can be done in parallel with other P1 tickets)
- S-15 (public schema drop) depends on THIS ticket completing first

## Verification
```bash
# 1. Run verification script:
python scripts/verify_schema_refs.py
# EXPECTED: "All ORM models have explicit schema declarations"

# 2. Check for raw SQL:
grep -rn 'text(' src/ aria_engine/ aria_skills/ --include='*.py' | grep -v '#' | grep -v 'test'
# EXPECTED: No matches (or only in test files)

# 3. Verify via psql that public schema has no active writes:
# (Run on prod DB before and after a test cycle)
# SELECT schemaname, relname, n_tup_ins FROM pg_stat_user_tables WHERE schemaname = 'public' ORDER BY n_tup_ins DESC;
# EXPECTED: All inserts = 0 during test window

# 4. Verify ORM queries use correct schema:
# Run the app, create a session, check which schema the row lands in:
curl -X POST http://localhost:8000/engine/chat/sessions -H 'Content-Type: application/json' -d '{}'
# Then check: SELECT * FROM aria_engine.sessions ORDER BY created_at DESC LIMIT 1;
# EXPECTED: Row exists in aria_engine.sessions
```

## Prompt for Agent
```
Read these files FIRST:
- src/api/ — ALL Python files, focusing on SQLAlchemy model definitions
- aria_engine/ — ALL Python files, search for any raw SQL
- aria_skills/ — ALL Python files, search for any execute() calls

CONSTRAINTS: #1 (ZERO direct SQL — absolute rule).

STEPS:
1. Find ALL SQLAlchemy model classes in src/api/
2. For each model, check if __table_args__ includes schema="aria_engine" or schema="aria_data"
3. List all models missing schema declaration
4. Search entire codebase for raw SQL (text(), execute(), SELECT/INSERT/UPDATE/DELETE strings)
5. If raw SQL found: replace with ORM equivalent, DO NOT just add schema prefix
6. Fix all models missing schema — add __table_args__ = {"schema": "correct_schema"}
7. Create scripts/verify_schema_refs.py verification script
8. Run verification
9. Document any direct SQL violations found (for audit trail)
```
