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
