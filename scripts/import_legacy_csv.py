"""
Import legacy Aria CSV data into aria_warehouse.

- Users -> memories (category: legacy_user)
- Interactions -> activity_log (observations) or social_posts (legacy posts)
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
from datetime import datetime
from typing import Any, Dict, Optional

import asyncpg

POST_TYPES = {"post", "status", "moltbook_post", "moltbook"}


def _parse_int(value: str) -> Optional[int]:
    if value is None or value == "":
        return None
    return int(value)


def _parse_dt(value: str) -> Optional[datetime]:
    if value is None or value == "":
        return None
    return datetime.fromisoformat(value)


def _parse_json(value: str) -> Optional[Dict[str, Any]]:
    if value is None or value == "":
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return {"raw": value}


async def _import_users(conn: asyncpg.Connection, path: str) -> int:
    count = 0
    with open(path, "r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            legacy_id = row.get("id")
            if not legacy_id:
                continue
            payload = {
                "legacy_id": int(legacy_id),
                "username": row.get("username") or None,
                "display_name": row.get("display_name") or None,
                "bio": row.get("bio") or None,
                "follower_count": _parse_int(row.get("follower_count", "")),
                "simp_score": _parse_int(row.get("simp_score", "")),
                "last_interaction": row.get("last_interaction") or None,
                "meta": _parse_json(row.get("meta", "")),
            }
            key = f"legacy_user:{legacy_id}"
            await conn.execute(
                """
                INSERT INTO memories (key, value, category)
                VALUES ($1, $2::jsonb, 'legacy_user')
                ON CONFLICT (key)
                DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
                """,
                key,
                json.dumps(payload),
            )
            count += 1
    return count


async def _import_interactions(conn: asyncpg.Connection, path: str) -> Dict[str, int]:
    activity_count = 0
    post_count = 0

    with open(path, "r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            legacy_type = (row.get("type") or "").strip()
            content = row.get("content") or ""
            created_at = _parse_dt(row.get("created_at", ""))
            details = {
                "source": "aria_bubble.interactions",
                "legacy_type": legacy_type,
                "legacy_id": _parse_int(row.get("id", "")),
                "user_id": _parse_int(row.get("user_id", "")),
                "tweet_id": row.get("tweet_id") or None,
                "sentiment_score": _parse_int(row.get("sentiment_score", "")),
                "vector_embedding": _parse_json(row.get("vector_embedding", "")),
                "content": content,
            }

            if legacy_type in POST_TYPES:
                await conn.execute(
                    """
                    INSERT INTO social_posts
                        (platform, post_id, content, visibility, reply_to, url, posted_at, metadata)
                    VALUES
                        ('moltbook', $1, $2, 'public', NULL, NULL, $3, $4::jsonb)
                    """,
                    row.get("tweet_id") or None,
                    content,
                    created_at,
                    json.dumps(details),
                )
                post_count += 1
            else:
                await conn.execute(
                    """
                    INSERT INTO activity_log (action, skill, details, success, created_at)
                    VALUES ('legacy_observation', 'import', $1::jsonb, true, $2)
                    """,
                    json.dumps(details),
                    created_at,
                )
                activity_count += 1

    return {"activity": activity_count, "posts": post_count}


async def main() -> None:
    parser = argparse.ArgumentParser(description="Import legacy CSV data into aria_warehouse")
    parser.add_argument(
        "--users",
        default="aria_memory/db_dumps/legacy_users.csv",
        help="Path to legacy users CSV",
    )
    parser.add_argument(
        "--interactions",
        default="aria_memory/db_dumps/legacy_interactions.csv",
        help="Path to legacy interactions CSV",
    )
    args = parser.parse_args()

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is required")

    conn = await asyncpg.connect(database_url)
    try:
        users_count = await _import_users(conn, args.users)
        counts = await _import_interactions(conn, args.interactions)
    finally:
        await conn.close()

    print(f"Imported users: {users_count}")
    print(f"Imported activities: {counts['activity']}")
    print(f"Imported posts: {counts['posts']}")


if __name__ == "__main__":
    asyncio.run(main())
