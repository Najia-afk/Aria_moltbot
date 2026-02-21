# S8-06: Data Migration — OpenClaw Sessions to Engine Tables
**Epic:** E6 — OpenClaw Removal | **Priority:** P0 | **Points:** 3 | **Phase:** 8

## Problem
Historical session data exists in the `agent_sessions` table with OpenClaw-sourced metadata (UUID5 IDs, `openclaw_session_id` in metadata_json, source="openclaw_live"). This data must be migrated to the engine's `aria_engine.chat_sessions` table so it is accessible in the new UI. The migration must be idempotent (safe to run multiple times).

## Root Cause
The old sessions router synced data from OpenClaw into `public.agent_sessions`. The engine uses `aria_engine.chat_sessions` with a different schema. A one-time migration is needed to carry forward historical data.

## Fix

### 1. Migration script — `scripts/migrate_sessions_to_engine.py`

```python
#!/usr/bin/env python3
"""
Migrate historical OpenClaw sessions from public.agent_sessions
to aria_engine.chat_sessions.

Usage:
    python scripts/migrate_sessions_to_engine.py [--dry-run] [--batch-size=500]

Idempotent: Uses ON CONFLICT DO NOTHING on the primary key.
"""

import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone
from uuid import UUID

import asyncpg


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://admin:admin@localhost:5432/aria_warehouse",
)


async def get_connection() -> asyncpg.Connection:
    """Connect to the database."""
    return await asyncpg.connect(DATABASE_URL)


async def count_source_sessions(conn: asyncpg.Connection) -> int:
    """Count sessions in the source table."""
    row = await conn.fetchrow("SELECT COUNT(*) AS cnt FROM agent_sessions")
    return row["cnt"] if row else 0


async def count_target_sessions(conn: asyncpg.Connection) -> int:
    """Count sessions already in the target table."""
    row = await conn.fetchrow("SELECT COUNT(*) AS cnt FROM aria_engine.chat_sessions")
    return row["cnt"] if row else 0


async def migrate_batch(
    conn: asyncpg.Connection,
    offset: int,
    batch_size: int,
    dry_run: bool = False,
) -> int:
    """
    Migrate one batch of sessions.
    Returns the number of rows inserted (0 for conflicts / dry-run).
    """
    rows = await conn.fetch(
        """
        SELECT
            id,
            agent_id,
            session_type,
            started_at,
            ended_at,
            status,
            metadata_json
        FROM agent_sessions
        ORDER BY started_at ASC NULLS LAST, id ASC
        OFFSET $1 LIMIT $2
        """,
        offset,
        batch_size,
    )

    if not rows:
        return 0

    if dry_run:
        for row in rows:
            print(f"  [DRY-RUN] Would migrate session {row['id']} "
                  f"(agent={row['agent_id']}, status={row['status']})")
        return len(rows)

    # Prepare batch insert with ON CONFLICT DO NOTHING
    insert_sql = """
        INSERT INTO aria_engine.chat_sessions (
            id,
            agent_id,
            model,
            started_at,
            ended_at,
            status,
            metadata,
            created_at,
            updated_at
        )
        SELECT
            s.id,
            s.agent_id,
            COALESCE(
                s.metadata_json->>'model',
                (s.metadata_json->'openclaw_session'->>'model'),
                'unknown'
            ),
            COALESCE(s.started_at, NOW()),
            s.ended_at,
            COALESCE(s.status, 'completed'),
            jsonb_build_object(
                'migrated_from', 'agent_sessions',
                'migration_date', $3::text,
                'original_type', s.session_type,
                'original_metadata', s.metadata_json,
                'source', COALESCE(s.metadata_json->>'source', 'unknown')
            ),
            COALESCE(s.started_at, NOW()),
            NOW()
        FROM unnest($1::uuid[], $2::text[]) AS input(id_val, agent_id_val)
        JOIN agent_sessions s ON s.id = input.id_val
        ON CONFLICT (id) DO NOTHING
    """

    ids = [row["id"] for row in rows]
    agent_ids = [row["agent_id"] or "main" for row in rows]
    migration_ts = datetime.now(timezone.utc).isoformat()

    result = await conn.execute(insert_sql, ids, agent_ids, migration_ts)

    # Parse "INSERT 0 N" result
    inserted = 0
    if result and result.startswith("INSERT"):
        parts = result.split()
        if len(parts) >= 3:
            try:
                inserted = int(parts[2])
            except ValueError:
                pass

    return inserted


async def migrate_messages(
    conn: asyncpg.Connection,
    dry_run: bool = False,
) -> int:
    """
    Migrate messages if there's a messages table in the public schema.
    Returns count of migrated messages.
    """
    # Check if source messages table exists
    exists = await conn.fetchrow(
        """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'session_messages'
        ) AS exists
        """
    )

    if not exists or not exists["exists"]:
        print("  No public.session_messages table found — skipping message migration.")
        return 0

    count_row = await conn.fetchrow("SELECT COUNT(*) AS cnt FROM session_messages")
    msg_count = count_row["cnt"] if count_row else 0

    if msg_count == 0:
        print("  No messages to migrate.")
        return 0

    if dry_run:
        print(f"  [DRY-RUN] Would migrate {msg_count} messages.")
        return msg_count

    result = await conn.execute(
        """
        INSERT INTO aria_engine.chat_messages (
            id,
            session_id,
            role,
            content,
            model,
            token_count,
            metadata,
            created_at
        )
        SELECT
            id,
            session_id,
            COALESCE(role, 'user'),
            COALESCE(content, ''),
            model,
            token_count,
            COALESCE(metadata_json, '{}'::jsonb),
            COALESCE(created_at, NOW())
        FROM session_messages
        ON CONFLICT (id) DO NOTHING
        """
    )

    migrated = 0
    if result and result.startswith("INSERT"):
        parts = result.split()
        if len(parts) >= 3:
            try:
                migrated = int(parts[2])
            except ValueError:
                pass

    return migrated


async def run_migration(
    dry_run: bool = False,
    batch_size: int = 500,
) -> None:
    """Run the full migration."""
    print("=" * 60)
    print("OpenClaw → Engine Session Migration")
    print("=" * 60)
    print(f"  Database:   {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else DATABASE_URL}")
    print(f"  Dry run:    {dry_run}")
    print(f"  Batch size: {batch_size}")
    print()

    conn = await get_connection()

    try:
        # Verify target schema exists
        schema_exists = await conn.fetchrow(
            "SELECT EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = 'aria_engine') AS exists"
        )
        if not schema_exists or not schema_exists["exists"]:
            print("ERROR: aria_engine schema does not exist. Run the schema migration first (S1-01).")
            sys.exit(1)

        # Count source and target
        source_count = await count_source_sessions(conn)
        target_count = await count_target_sessions(conn)
        print(f"  Source (agent_sessions):           {source_count} sessions")
        print(f"  Target (aria_engine.chat_sessions): {target_count} sessions")
        print()

        if source_count == 0:
            print("No sessions to migrate. Done.")
            return

        # Migrate in batches
        total_inserted = 0
        total_skipped = 0
        offset = 0

        while True:
            inserted = await migrate_batch(conn, offset, batch_size, dry_run)
            if inserted == 0 and offset >= source_count:
                break

            total_inserted += inserted
            batch_skipped = min(batch_size, source_count - offset) - inserted
            total_skipped += max(0, batch_skipped)
            offset += batch_size

            if offset % (batch_size * 10) == 0:
                print(f"  Progress: {offset}/{source_count} processed…")

            if offset >= source_count:
                break

        print()
        print(f"  Sessions inserted:  {total_inserted}")
        print(f"  Sessions skipped:   {total_skipped} (already existed)")

        # Migrate messages
        print()
        print("--- Message Migration ---")
        msg_count = await migrate_messages(conn, dry_run)
        print(f"  Messages migrated: {msg_count}")

        # Final counts
        final_target = await count_target_sessions(conn)
        print()
        print("=" * 60)
        print(f"  Final target count: {final_target} sessions")
        if dry_run:
            print("  (DRY RUN — no data was modified)")
        else:
            print("  Migration complete ✓")
        print("=" * 60)

    finally:
        await conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Migrate OpenClaw sessions to engine tables"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be migrated without making changes",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Number of sessions to process per batch (default: 500)",
    )
    args = parser.parse_args()

    asyncio.run(run_migration(dry_run=args.dry_run, batch_size=args.batch_size))


if __name__ == "__main__":
    main()
```

### 2. How to run

```bash
# Step 1: Dry run — see what would be migrated
docker compose exec aria-api python /app/scripts/migrate_sessions_to_engine.py --dry-run

# Step 2: Actual migration
docker compose exec aria-api python /app/scripts/migrate_sessions_to_engine.py

# Step 3: Run again to verify idempotency (should show 0 inserted, N skipped)
docker compose exec aria-api python /app/scripts/migrate_sessions_to_engine.py
```

### 3. Post-migration cleanup (optional, after verification)

Once the migration is confirmed successful and the new engine has been running for a sprint:

```sql
-- Optional: Archive the old table (don't delete yet)
ALTER TABLE public.agent_sessions RENAME TO agent_sessions_archived;

-- Optional: After 2 weeks of successful operation
-- DROP TABLE public.agent_sessions_archived;
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | Direct DB access (migration script) |
| 2 | .env for secrets (zero in code) | ✅ | Uses DATABASE_URL from env |
| 3 | models.yaml single source of truth | ❌ | N/A |
| 4 | Docker-first testing | ✅ | Run inside aria-api container |
| 5 | aria_memories only writable path | ❌ | Writes to database |
| 6 | No soul modification | ❌ | N/A |

## Dependencies
- S1-01 (Database schema — aria_engine schema + chat_sessions table must exist)
- S8-05 (Clean sessions router — must be deployed before migration is finalized)

## Verification
```bash
# 1. Dry run succeeds:
python scripts/migrate_sessions_to_engine.py --dry-run
# EXPECTED: Shows session count and "[DRY-RUN]" messages

# 2. Migration succeeds:
python scripts/migrate_sessions_to_engine.py
# EXPECTED: "Migration complete ✓" with insert count

# 3. Idempotent — second run inserts 0:
python scripts/migrate_sessions_to_engine.py
# EXPECTED: "Sessions inserted: 0", "Sessions skipped: N"

# 4. Data integrity:
psql -c "SELECT COUNT(*) FROM aria_engine.chat_sessions WHERE metadata->>'migrated_from' = 'agent_sessions';"
# EXPECTED: Same as source count

# 5. Metadata preserved:
psql -c "SELECT id, agent_id, metadata->>'source' FROM aria_engine.chat_sessions LIMIT 5;"
# EXPECTED: Rows with original source info
```

## Prompt for Agent
```
Create the migration script for OpenClaw sessions → engine tables.

FILES TO READ FIRST:
- db/models.py (AgentSession model — source table)
- aria_engine/models.py or schema SQL (chat_sessions — target table)
- src/api/routers/sessions.py (old file — see _normalize_live_session for metadata format)
- scripts/ (check for existing migration patterns)

STEPS:
1. Create scripts/migrate_sessions_to_engine.py
2. Read from public.agent_sessions (source)
3. Transform and insert into aria_engine.chat_sessions (target)
4. Preserve metadata in a migration envelope: migrated_from, migration_date, original fields
5. Use ON CONFLICT (id) DO NOTHING for idempotency
6. Process in batches (default 500)
7. Support --dry-run flag
8. Handle messages if public.session_messages exists
9. Print progress summary

IDEMPOTENCY:
- Uses ON CONFLICT DO NOTHING — safe to run multiple times
- Does NOT delete source data
- Does NOT modify source data
- Tracks migration via metadata->>'migrated_from' = 'agent_sessions'

SAFETY:
- Always do --dry-run first
- Never DROP the source table in this script
- The source table rename is documented but done manually after verification
```
