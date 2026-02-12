#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STACK_DIR="$ROOT_DIR/stacks/brain"

cd "$STACK_DIR"

echo "[backfill] Inserting missing skill_invocations from agent_sessions/model_usage/activity_log..."

docker compose exec -T aria-db psql -U aria_admin -d aria_warehouse <<'SQL'
BEGIN;

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
  FROM agent_sessions
  WHERE session_type = 'skill_exec'
    AND metadata ? 'skill'
), ins AS (
  INSERT INTO skill_invocations (skill_name, tool_name, duration_ms, success, error_type, tokens_used, model_used, created_at)
  SELECT s.*
  FROM src s
  WHERE NOT EXISTS (
    SELECT 1
    FROM skill_invocations si
    WHERE si.skill_name = s.skill_name
      AND si.tool_name = s.tool_name
      AND si.created_at = s.created_at
  )
  RETURNING 1
)
SELECT 'agent_sessions' AS source, count(*) AS inserted FROM ins;

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
  FROM model_usage
  WHERE model LIKE 'skill:%:%'
), ins AS (
  INSERT INTO skill_invocations (skill_name, tool_name, duration_ms, success, error_type, tokens_used, model_used, created_at)
  SELECT s.*
  FROM src s
  WHERE NOT EXISTS (
    SELECT 1
    FROM skill_invocations si
    WHERE si.skill_name = s.skill_name
      AND si.tool_name = s.tool_name
      AND si.created_at = s.created_at
  )
  RETURNING 1
)
SELECT 'model_usage' AS source, count(*) AS inserted FROM ins;

WITH src AS (
  SELECT
    LEFT(COALESCE(NULLIF(skill, ''), 'unknown'), 100) AS skill_name,
    LEFT(COALESCE(NULLIF(action, ''), 'unknown'), 100) AS tool_name,
    CASE
      WHEN COALESCE(details->>'duration_ms', '') ~ '^[0-9]+$' THEN (details->>'duration_ms')::int
      ELSE NULL
    END AS duration_ms,
    COALESCE(success, true) AS success,
    LEFT(NULLIF(error_message, ''), 100) AS error_type,
    NULL::int AS tokens_used,
    NULL::text AS model_used,
    created_at
  FROM activity_log
  WHERE COALESCE(skill, '') <> ''
    AND (action = 'skill_used' OR action ILIKE '%skill%')
), ins AS (
  INSERT INTO skill_invocations (skill_name, tool_name, duration_ms, success, error_type, tokens_used, model_used, created_at)
  SELECT s.*
  FROM src s
  WHERE NOT EXISTS (
    SELECT 1
    FROM skill_invocations si
    WHERE si.skill_name = s.skill_name
      AND si.tool_name = s.tool_name
      AND si.created_at = s.created_at
  )
  RETURNING 1
)
SELECT 'activity_log' AS source, count(*) AS inserted FROM ins;

COMMIT;
SQL

echo "[backfill] Done. Current skill_invocations summary:"
docker compose exec -T aria-db psql -U aria_admin -d aria_warehouse -c "SELECT count(*) AS total_invocations, count(DISTINCT skill_name) AS unique_skills, min(created_at) AS oldest, max(created_at) AS newest FROM skill_invocations;"
