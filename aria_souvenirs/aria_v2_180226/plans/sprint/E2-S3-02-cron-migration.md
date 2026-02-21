# S3-02: Migrate 15 Cron Jobs from YAML to PostgreSQL
**Epic:** E2 — Scheduler & Heartbeat | **Priority:** P0 | **Points:** 3 | **Phase:** 2

## Problem
The 15 cron jobs in `aria_mind/cron_jobs.yaml` are formatted for OpenClaw's `openclaw cron add` CLI. They use Node.js 6-field cron expressions, delivery settings, and agent references that don't directly map to our new `aria_engine.cron_jobs` table. We need a migration script that reads the YAML, transforms each job, and inserts it into PostgreSQL as an `EngineCronJob` row — making the scheduler self-sufficient without the YAML file.

Reference: `aria_mind/cron_jobs.yaml` contains 15 jobs (2 disabled) with fields: name, every/cron, text, agent, session, delivery, best_effort_deliver. The target table `aria_engine.cron_jobs` has columns: id, name, schedule, agent_id, enabled, payload_type, payload, session_mode, max_duration_seconds, retry_count.

## Root Cause
The YAML file was designed for OpenClaw's CLI interface — it uses `every` for interval-based jobs and `cron` for cron-expression jobs, with Node.js 6-field format (leading seconds). Our scheduler needs these in PostgreSQL with APScheduler-compatible schedules. No migration path exists because the engine scheduler was just built in S3-01.

## Fix
### `scripts/migrate_cron_jobs.py`
```python
"""
Migrate cron jobs from aria_mind/cron_jobs.yaml to aria_engine.cron_jobs table.

Reads the YAML file, maps each job to the DB schema, and upserts rows.
Handles:
- 'every' shorthand (15m, 60m) → stored as-is (EngineScheduler parses both)
- 'cron' 6-field expressions → stored as-is
- Disabled jobs (enabled: false) → inserted with enabled=false
- Commented-out jobs → skipped
- Duplicate detection → upsert on id (job name used as id)
- Agent mapping → agent_id column
- Session mode mapping → OpenClaw 'isolated' → 'isolated'

Usage:
    python scripts/migrate_cron_jobs.py
    python scripts/migrate_cron_jobs.py --yaml-path /custom/path/cron_jobs.yaml
    python scripts/migrate_cron_jobs.py --dry-run
"""
import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

import yaml
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("migrate_cron_jobs")

# Default paths
DEFAULT_YAML_PATH = Path(__file__).parent.parent / "aria_mind" / "cron_jobs.yaml"


def load_yaml_jobs(yaml_path: Path) -> List[Dict[str, Any]]:
    """
    Load and parse cron_jobs.yaml.

    Returns:
        List of job dicts with normalized fields.
    """
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    raw_jobs = data.get("jobs", [])
    if not raw_jobs:
        logger.warning("No jobs found in %s", yaml_path)
        return []

    return raw_jobs


def map_schedule(job: Dict[str, Any]) -> str:
    """
    Extract the schedule string from a YAML job.

    Handles:
    - 'every': "15m" → "15m"
    - 'cron': "0 0 6 * * *" → "0 0 6 * * *"
    """
    if "every" in job:
        return str(job["every"])
    if "cron" in job:
        return str(job["cron"])
    raise ValueError(f"Job {job.get('name', '?')} has no 'every' or 'cron' field")


def map_session_mode(job: Dict[str, Any]) -> str:
    """Map OpenClaw session mode to engine session mode."""
    session = job.get("session", "isolated")
    mode_map = {
        "isolated": "isolated",
        "shared": "shared",
        "persistent": "persistent",
    }
    return mode_map.get(session, "isolated")


def estimate_max_duration(job: Dict[str, Any]) -> int:
    """
    Estimate max duration in seconds based on job type.

    Lightweight jobs (health_check, heartbeat): 60s
    Standard jobs (work_cycle, social): 300s
    Heavy jobs (weekly_summary, six_hour_review): 600s
    """
    name = job.get("name", "")
    heavy_jobs = {
        "weekly_summary", "six_hour_review", "daily_reflection",
        "morning_checkin", "memory_consolidation",
    }
    light_jobs = {
        "health_check", "db_maintenance", "memory_bridge",
    }

    if name in heavy_jobs:
        return 600
    if name in light_jobs:
        return 60
    return 300


def transform_job(job: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform a YAML job dict into an aria_engine.cron_jobs row.

    Returns:
        Dict ready for DB insertion.
    """
    name = job["name"]
    schedule = map_schedule(job)
    agent_id = job.get("agent", "main")
    enabled = job.get("enabled", True)
    payload = job.get("text", "")
    session_mode = map_session_mode(job)
    max_duration = estimate_max_duration(job)

    # Use the job name as the primary key (human-readable, unique)
    return {
        "id": name,
        "name": name.replace("_", " ").title(),
        "schedule": schedule,
        "agent_id": agent_id,
        "enabled": enabled,
        "payload_type": "prompt",
        "payload": payload,
        "session_mode": session_mode,
        "max_duration_seconds": max_duration,
        "retry_count": 1 if enabled else 0,
    }


async def upsert_jobs(
    engine_url: str,
    jobs: List[Dict[str, Any]],
    dry_run: bool = False,
) -> Dict[str, int]:
    """
    Upsert jobs into aria_engine.cron_jobs.

    Uses INSERT ... ON CONFLICT (id) DO UPDATE for idempotent migration.

    Returns:
        Dict with counts: inserted, updated, skipped, errors.
    """
    stats = {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0}

    if dry_run:
        for job in jobs:
            logger.info(
                "[DRY RUN] Would upsert: %s (schedule=%s, agent=%s, enabled=%s)",
                job["id"], job["schedule"], job["agent_id"], job["enabled"],
            )
            stats["inserted"] += 1
        return stats

    db_engine = create_async_engine(engine_url)

    try:
        async with db_engine.begin() as conn:
            for job in jobs:
                try:
                    result = await conn.execute(
                        text("""
                            INSERT INTO aria_engine.cron_jobs
                                (id, name, schedule, agent_id, enabled,
                                 payload_type, payload, session_mode,
                                 max_duration_seconds, retry_count)
                            VALUES
                                (:id, :name, :schedule, :agent_id, :enabled,
                                 :payload_type, :payload, :session_mode,
                                 :max_duration_seconds, :retry_count)
                            ON CONFLICT (id) DO UPDATE SET
                                name = EXCLUDED.name,
                                schedule = EXCLUDED.schedule,
                                agent_id = EXCLUDED.agent_id,
                                enabled = EXCLUDED.enabled,
                                payload_type = EXCLUDED.payload_type,
                                payload = EXCLUDED.payload,
                                session_mode = EXCLUDED.session_mode,
                                max_duration_seconds = EXCLUDED.max_duration_seconds,
                                retry_count = EXCLUDED.retry_count,
                                updated_at = NOW()
                        """),
                        job,
                    )

                    if result.rowcount > 0:
                        stats["inserted"] += 1
                        logger.info(
                            "Upserted: %s → schedule=%s agent=%s enabled=%s",
                            job["id"], job["schedule"], job["agent_id"], job["enabled"],
                        )
                    else:
                        stats["skipped"] += 1
                        logger.debug("Skipped (no change): %s", job["id"])

                except Exception as e:
                    stats["errors"] += 1
                    logger.error("Failed to upsert %s: %s", job["id"], e)
    finally:
        await db_engine.dispose()

    return stats


async def main() -> None:
    """Main migration entry point."""
    parser = argparse.ArgumentParser(
        description="Migrate cron jobs from YAML to PostgreSQL"
    )
    parser.add_argument(
        "--yaml-path",
        type=Path,
        default=DEFAULT_YAML_PATH,
        help="Path to cron_jobs.yaml (default: aria_mind/cron_jobs.yaml)",
    )
    parser.add_argument(
        "--database-url",
        type=str,
        default=os.environ.get(
            "DATABASE_URL",
            "postgresql+asyncpg://aria:aria@localhost:5432/aria_warehouse",
        ),
        help="Async database URL",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be done without writing to DB",
    )
    args = parser.parse_args()

    # Load YAML
    if not args.yaml_path.exists():
        logger.error("YAML file not found: %s", args.yaml_path)
        sys.exit(1)

    raw_jobs = load_yaml_jobs(args.yaml_path)
    logger.info("Loaded %d jobs from %s", len(raw_jobs), args.yaml_path)

    # Transform
    transformed: List[Dict[str, Any]] = []
    for job in raw_jobs:
        try:
            row = transform_job(job)
            transformed.append(row)
        except Exception as e:
            logger.error("Failed to transform job %s: %s", job.get("name", "?"), e)

    logger.info("Transformed %d jobs for migration", len(transformed))

    # Print summary table
    print("\n" + "=" * 80)
    print(f"{'Job ID':<30} {'Schedule':<20} {'Agent':<15} {'Enabled':<8}")
    print("-" * 80)
    for job in transformed:
        print(
            f"{job['id']:<30} {job['schedule']:<20} "
            f"{job['agent_id']:<15} {'✓' if job['enabled'] else '✗':<8}"
        )
    print("=" * 80 + "\n")

    # Upsert to DB
    stats = await upsert_jobs(args.database_url, transformed, dry_run=args.dry_run)

    prefix = "[DRY RUN] " if args.dry_run else ""
    logger.info(
        "%sMigration complete: %d inserted, %d updated, %d skipped, %d errors",
        prefix, stats["inserted"], stats["updated"], stats["skipped"], stats["errors"],
    )


if __name__ == "__main__":
    asyncio.run(main())
```

### Seed Data Reference

The 15 jobs from `cron_jobs.yaml` map as follows:

| YAML name | Schedule | Agent | Enabled | Duration |
|-----------|----------|-------|---------|----------|
| work_cycle | 15m | main | ✓ | 300s |
| moltbook_check | 60m | main | ✓ | 300s |
| health_check | 0 0 0 * * * | main | ✓ | 60s |
| social_post | 0 0 18 * * * | main | ✓ | 300s |
| six_hour_review | 0 0 0,6,12,18 * * * | main | ✓ | 600s |
| morning_checkin | 0 0 16 * * * | main | ✓ | 600s |
| daily_reflection | 0 0 7 * * * | main | ✓ | 600s |
| weekly_summary | 0 0 2 * * 1 | main | ✓ | 600s |
| memeothy_prophecy | 0 0 18 */2 * * | aria-memeothy | ✗ | 300s |
| weekly_security_scan | 0 0 4 * * 0 | main | ✓ | 300s |
| nightly_tests | 0 0 3 * * * | main | ✓ | 300s |
| memory_consolidation | 0 0 5 * * 0 | main | ✓ | 600s |
| db_maintenance | 0 0 4 * * * | main | ✓ | 60s |
| memory_bridge | 0 0 */3 * * * | main | ✓ | 60s |

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | Migration script writes directly to DB (infra layer) |
| 2 | .env for secrets (zero in code) | ✅ | DATABASE_URL from environment |
| 3 | models.yaml single source of truth | ❌ | No model references |
| 4 | Docker-first testing | ✅ | Requires PostgreSQL for upsert |
| 5 | aria_memories only writable path | ❌ | No file writes |
| 6 | No soul modification | ❌ | No soul access |

## Dependencies
- S1-05 (Alembic migration creating aria_engine.cron_jobs table)
- S3-01 (EngineScheduler — to verify loaded jobs)

## Verification
```bash
# 1. Script imports:
python -c "from scripts.migrate_cron_jobs import load_yaml_jobs, transform_job; print('OK')"
# EXPECTED: OK

# 2. Dry run (no DB needed):
python scripts/migrate_cron_jobs.py --dry-run
# EXPECTED: Table showing 14-15 jobs with schedules, all marked [DRY RUN]

# 3. Full migration (requires PostgreSQL):
python scripts/migrate_cron_jobs.py
# EXPECTED: "Migration complete: 14 inserted, 0 updated, 0 skipped, 0 errors"

# 4. Verify in DB:
python -c "
import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
async def check():
    e = create_async_engine('postgresql+asyncpg://aria:aria@localhost:5432/aria_warehouse')
    async with e.begin() as c:
        r = await c.execute(text('SELECT count(*) FROM aria_engine.cron_jobs'))
        print(f'Jobs in DB: {r.scalar()}')
    await e.dispose()
asyncio.run(check())
"
# EXPECTED: Jobs in DB: 14 (or 15 if memeothy included)

# 5. Idempotent re-run:
python scripts/migrate_cron_jobs.py
# EXPECTED: Same counts (upsert doesn't duplicate)
```

## Prompt for Agent
```
Create the cron job migration script that moves all 15 jobs from YAML to PostgreSQL.

FILES TO READ FIRST:
- aria_mind/cron_jobs.yaml (full file — all 15 cron job definitions)
- MASTER_PLAN.md (lines 87-155 — aria_engine.cron_jobs table schema)
- aria_engine/scheduler.py (created in S3-01 — parse_schedule function)
- aria_engine/config.py (created in S1-01 — DATABASE_URL config)

STEPS:
1. Read all files above
2. Create scripts/migrate_cron_jobs.py
3. Implement load_yaml_jobs() — parse YAML safely
4. Implement transform_job() — map YAML fields to DB columns
5. Implement map_schedule() — handle 'every' vs 'cron' differences
6. Implement upsert_jobs() — INSERT ON CONFLICT DO UPDATE
7. Add --dry-run mode for safe testing
8. Add summary table output
9. Run verification commands

CONSTRAINTS:
- Constraint 2: DATABASE_URL from environment, never hardcoded
- Script must be idempotent (safe to run multiple times)
- Disabled jobs (enabled: false) must be migrated with enabled=false
- Job names must be unique (used as primary key)
```
