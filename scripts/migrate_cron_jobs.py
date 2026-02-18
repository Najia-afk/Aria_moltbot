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
- Session mode mapping → legacy 'isolated' → 'isolated'

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
    """Map legacy session mode to engine session mode."""
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
            "postgresql+asyncpg://admin:admin@localhost:5432/aria_warehouse",
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
