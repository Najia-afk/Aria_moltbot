"""Startup backfill for skill invocation telemetry."""

import logging

from sqlalchemy import text

from db.session import async_engine

logger = logging.getLogger("aria.startup.backfill")


_AGENT_SESSIONS_SQL = text(
    """
    WITH src AS (
      SELECT
        LEFT(COALESCE(NULLIF(metadata->>'skill', ''), 'unknown'), 100) AS skill_name,
        LEFT(COALESCE(NULLIF(metadata->>'function', ''), 'unknown'), 100) AS tool_name,
        CASE
          WHEN COALESCE(metadata->>'duration_ms', '') ~ '^[0-9]+(\\.[0-9]+)?$' THEN ROUND((metadata->>'duration_ms')::numeric)::int
          ELSE NULL
        END AS duration_ms,
        COALESCE(NULLIF(metadata->>'success', '')::boolean, true) AS success,
        LEFT(NULLIF(metadata->>'error', ''), 100) AS error_type,
        NULLIF(tokens_used, 0) AS tokens_used,
        NULL::text AS model_used,
        started_at AS created_at
      FROM aria_data.agent_sessions
      WHERE session_type = 'skill_exec'
        AND metadata ? 'skill'
    ), ins AS (
      INSERT INTO aria_data.skill_invocations (
        skill_name,
        tool_name,
        duration_ms,
        success,
        error_type,
        tokens_used,
        model_used,
        created_at
      )
      SELECT s.*
      FROM src s
      WHERE NOT EXISTS (
        SELECT 1
        FROM aria_data.skill_invocations si
        WHERE si.skill_name = s.skill_name
          AND si.tool_name = s.tool_name
          AND si.created_at = s.created_at
      )
      RETURNING 1
    )
    SELECT count(*) FROM ins;
    """
)

_MODEL_USAGE_SQL = text(
    """
    WITH src AS (
      SELECT
        LEFT(split_part(model, ':', 2), 100) AS skill_name,
        LEFT(split_part(model, ':', 3), 100) AS tool_name,
        latency_ms AS duration_ms,
        COALESCE(success, true) AS success,
        LEFT(NULLIF(error_message, ''), 100) AS error_type,
        NULL::int AS tokens_used,
        LEFT(model, 100) AS model_used,
        created_at
      FROM aria_data.model_usage
      WHERE model LIKE 'skill:%:%'
    ), ins AS (
      INSERT INTO aria_data.skill_invocations (
        skill_name,
        tool_name,
        duration_ms,
        success,
        error_type,
        tokens_used,
        model_used,
        created_at
      )
      SELECT s.*
      FROM src s
      WHERE NOT EXISTS (
        SELECT 1
        FROM aria_data.skill_invocations si
        WHERE si.skill_name = s.skill_name
          AND si.tool_name = s.tool_name
          AND si.created_at = s.created_at
      )
      RETURNING 1
    )
    SELECT count(*) FROM ins;
    """
)

_ACTIVITY_LOG_SQL = text(
    """
    WITH src AS (
      SELECT
        LEFT(COALESCE(NULLIF(skill, ''), 'unknown'), 100) AS skill_name,
        LEFT(COALESCE(NULLIF(action, ''), 'unknown'), 100) AS tool_name,
        CASE
          WHEN COALESCE(details->>'duration_ms', '') ~ '^[0-9]+(\\.[0-9]+)?$' THEN ROUND((details->>'duration_ms')::numeric)::int
          ELSE NULL
        END AS duration_ms,
        COALESCE(success, true) AS success,
        LEFT(NULLIF(error_message, ''), 100) AS error_type,
        NULL::int AS tokens_used,
        NULL::text AS model_used,
        created_at
      FROM aria_data.activity_log
      WHERE COALESCE(skill, '') <> ''
        AND skill <> 'pytest'
    ), ins AS (
      INSERT INTO aria_data.skill_invocations (
        skill_name,
        tool_name,
        duration_ms,
        success,
        error_type,
        tokens_used,
        model_used,
        created_at
      )
      SELECT s.*
      FROM src s
      WHERE NOT EXISTS (
        SELECT 1
        FROM aria_data.skill_invocations si
        WHERE si.skill_name = s.skill_name
          AND si.tool_name = s.tool_name
          AND si.created_at = s.created_at
      )
      RETURNING 1
    )
    SELECT count(*) FROM ins;
    """
)


async def run_skill_invocation_backfill() -> dict[str, int]:
    """Idempotently backfill skill_invocations from historical telemetry sources."""
    async with async_engine.begin() as conn:
        inserted_agent_sessions = int((await conn.execute(_AGENT_SESSIONS_SQL)).scalar() or 0)
        inserted_model_usage = int((await conn.execute(_MODEL_USAGE_SQL)).scalar() or 0)
        inserted_activity_log = int((await conn.execute(_ACTIVITY_LOG_SQL)).scalar() or 0)

    summary = {
        "agent_sessions": inserted_agent_sessions,
        "model_usage": inserted_model_usage,
        "activity_log": inserted_activity_log,
        "total": inserted_agent_sessions + inserted_model_usage + inserted_activity_log,
    }
    logger.info("Skill invocation startup backfill summary: %s", summary)
    return summary
