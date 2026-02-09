#!/bin/bash
export PATH=/Applications/Docker.app/Contents/Resources/bin:/usr/local/bin:/opt/homebrew/bin:$PATH

# Self-locate: resolve paths relative to this script
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ARIA_DIR="$(dirname "$SCRIPT_DIR")"

# Source environment from .env if available
ENV_FILE="${ARIA_DIR}/stacks/brain/.env"
if [ -f "${ENV_FILE}" ]; then
    set -a
    source "${ENV_FILE}"
    set +a
fi

DB_USER="${DB_USER:-aria_admin}"
DB_NAME="${DB_NAME:-aria_warehouse}"

echo "=== Aria Database Table Counts ==="
for tbl in activity_log agent_sessions api_key_rotations bubble_monetization goals heartbeat_log hourly_goals key_value_memory knowledge_entities knowledge_relations memories model_cost_reference model_discovery_log model_usage moltbook_users opportunities pending_complex_tasks performance_log rate_limits schedule_tick scheduled_jobs schema_migrations secops_work security_events social_posts spending_alerts spending_log thoughts yield_positions; do
    count=$(docker exec aria-db psql -U "${DB_USER}" -d "${DB_NAME}" -t -c "SELECT count(*) FROM $tbl" 2>/dev/null | tr -d ' ')
    echo "$tbl: $count"
done

echo ""
echo "=== Recent Activity (last 10) ==="
docker exec aria-db psql -U "${DB_USER}" -d "${DB_NAME}" -c "SELECT action, skill, created_at FROM activity_log ORDER BY created_at DESC LIMIT 10"

echo ""
echo "=== Recent Thoughts (last 10) ==="
docker exec aria-db psql -U "${DB_USER}" -d "${DB_NAME}" -c "SELECT category, LEFT(content, 80) as content, created_at FROM thoughts ORDER BY created_at DESC LIMIT 10"

echo ""
echo "=== Goals ==="
docker exec aria-db psql -U "${DB_USER}" -d "${DB_NAME}" -c "SELECT goal_id, title, status, priority, progress FROM goals ORDER BY priority DESC LIMIT 15"

echo ""
echo "=== Memories ==="
docker exec aria-db psql -U "${DB_USER}" -d "${DB_NAME}" -c "SELECT key, category, updated_at FROM memories ORDER BY updated_at DESC LIMIT 15"

echo ""
echo "=== Social Posts ==="
docker exec aria-db psql -U "${DB_USER}" -d "${DB_NAME}" -c "SELECT platform, LEFT(content, 80) as content, posted_at FROM social_posts ORDER BY posted_at DESC LIMIT 10"

echo ""
echo "=== Cron Jobs ==="
docker exec aria-db psql -U "${DB_USER}" -d "${DB_NAME}" -c "SELECT * FROM scheduled_jobs LIMIT 20"

echo ""
echo "=== OpenClaw Cron Jobs ==="
docker exec clawdbot openclaw cron list 2>/dev/null || echo "Failed to list cron jobs"

echo ""
echo "=== OpenClaw Agents ==="
docker exec clawdbot openclaw agent list 2>/dev/null || echo "Failed to list agents"

echo ""
echo "=== Files modified by Aria (in aria_mind) ==="
docker exec clawdbot find /root/.openclaw/workspace -name "*.md" -newer /root/.openclaw/.awakened -type f 2>/dev/null | head -30

echo ""
echo "=== Files in aria_memories ==="
docker exec clawdbot find /root/.openclaw/aria_memories -type f 2>/dev/null | head -30

echo ""
echo "=== Files in mounted repo ==="
docker exec clawdbot find /root/repo -maxdepth 2 -name "*.md" -newer /root/.openclaw/.awakened -type f 2>/dev/null | head -30

echo ""
echo "=== Traefik logs (last 20) ==="
docker logs traefik --tail 20 2>&1

echo ""
echo "=== OpenClaw version ==="
docker exec clawdbot openclaw --version 2>/dev/null || echo "Failed to get version"
