# S2-05: Fix GraphQL upsert_memory Race Condition
**Epic:** E1 — Bug Fixes | **Priority:** P1 | **Points:** 2 | **Phase:** 1

## Problem
`src/api/gql/resolvers.py` in `resolve_upsert_memory` (~line 209-225): uses SELECT-then-INSERT/UPDATE pattern which is not atomic. Two concurrent upserts for the same key could both see "not found" and both INSERT, causing a unique constraint violation. The REST endpoint in `src/api/routers/memories.py` uses proper `ON CONFLICT DO UPDATE`.

## Root Cause
The GraphQL resolver does:
1. `SELECT * FROM memories WHERE key = ?` 
2. If found → `UPDATE`; if not → `INSERT`

This is a classic TOCTOU (Time-of-check-to-time-of-use) race condition. Two concurrent requests with the same key could both pass step 1 (both see "not found") and both try to INSERT, causing a `UniqueViolation` error.

The REST endpoint correctly uses PostgreSQL's `INSERT ... ON CONFLICT (key) DO UPDATE` which is atomic.

## Fix

### File: `src/api/gql/resolvers.py`
Replace the SELECT-then-INSERT pattern with PostgreSQL's INSERT ON CONFLICT:

BEFORE (resolve_upsert_memory):
```python
async def resolve_upsert_memory(input: MemoryInput) -> MemoryType:
    async with AsyncSessionLocal() as db:
        # Check if exists
        result = await db.execute(select(Memory).where(Memory.key == input.key))
        existing = result.scalar_one_or_none()
        
        if existing:
            existing.value = input.value
            existing.category = input.category
            await db.commit()
            await db.refresh(existing)
            mem = existing
        else:
            mem = Memory(
                id=uuid.uuid4(),
                key=input.key,
                value=input.value,
                category=input.category,
            )
            db.add(mem)
            await db.commit()
```
AFTER:
```python
async def resolve_upsert_memory(input: MemoryInput) -> MemoryType:
    async with AsyncSessionLocal() as db:
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        stmt = pg_insert(Memory).values(
            id=uuid.uuid4(),
            key=input.key,
            value=input.value,
            category=input.category,
        ).on_conflict_do_update(
            index_elements=["key"],
            set_={"value": input.value, "category": input.category, "updated_at": text("NOW()")},
        ).returning(Memory)
        result = await db.execute(stmt)
        mem = result.scalar_one()
        await db.commit()
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | Change is in API/GQL layer (correct) |
| 2 | .env for secrets (zero in code) | ❌ | No secrets involved |
| 3 | models.yaml single source of truth | ❌ | No model references |
| 4 | Docker-first testing | ✅ | Test via GraphQL mutation |
| 5 | aria_memories only writable path | ❌ | DB writes, not file writes |
| 6 | No soul modification | ❌ | No soul files touched |

## Dependencies
None — standalone fix.

## Verification
```bash
# 1. Verify ON CONFLICT is used:
grep -n 'on_conflict' src/api/gql/resolvers.py
# EXPECTED: on_conflict_do_update

# 2. Test concurrent upserts don't crash:
for i in $(seq 1 5); do
  curl -s -X POST http://localhost:8000/api/graphql -H 'Content-Type: application/json' \
    -d '{"query":"mutation { upsertMemory(input: {key: \"race_test\", value: \"v'$i'\", category: \"test\"}) { id key } }"}' &
done
wait
# EXPECTED: All 5 succeed (no 500 errors)

# 3. Only one record exists:
curl -s http://localhost:8000/api/memories/race_test | python3 -c "import sys,json; print(json.load(sys.stdin))"
# EXPECTED: Single memory record
```

## Prompt for Agent
```
You are fixing a race condition in the Aria GraphQL resolver.

FILES TO READ FIRST:
- src/api/gql/resolvers.py (find resolve_upsert_memory)
- src/api/routers/memories.py (reference — uses ON CONFLICT correctly)

STEPS:
1. Read resolvers.py, find resolve_upsert_memory
2. Replace SELECT-then-INSERT/UPDATE with pg_insert().on_conflict_do_update()
3. Import pg_insert from sqlalchemy.dialects.postgresql
4. Run verification commands (concurrent curl requests)

CONSTRAINTS: API/GQL layer only. Use PostgreSQL-native ON CONFLICT.
```
