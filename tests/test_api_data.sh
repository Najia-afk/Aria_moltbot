#!/bin/bash
# Test all API data endpoints
HOST="http://localhost"

endpoints=(
    "/api/health"
    "/api/stats"
    "/api/activities?limit=1"
    "/api/thoughts?limit=1"
    "/api/memories?limit=1"
    "/api/status"
    "/api/litellm/models"
    "/api/litellm/health"
    "/api/litellm/global-spend"
    "/api/providers/balances"
    "/api/goals?limit=1"
    "/api/security-events/stats"
    "/api/security-events?limit=1"
    "/api/sessions/stats"
    "/api/sessions?limit=1"
    "/api/model-usage/stats"
    "/api/model-usage?limit=1"
    "/api/rate-limits"
    "/api/api-key-rotations?limit=1"
    "/api/jobs/live"
    "/api/schedule"
    "/api/heartbeat/latest"
    "/api/knowledge-graph"
    "/api/social"
    "/api/performance"
    "/api/hourly-goals"
    "/api/tasks"
    "/api/activity"
    "/api/host-stats"
    "/api/records?table=activity_log&limit=1"
    "/api/interactions?limit=1"
    "/api/stats-extended"
)

echo "=== API Data Endpoints ==="
for ep in "${endpoints[@]}"; do
    code=$(curl -sk -o /tmp/ep_test.txt -w '%{http_code}' "${HOST}${ep}" 2>/dev/null)
    size=$(wc -c < /tmp/ep_test.txt 2>/dev/null | tr -d ' ')
    snip=$(head -c 100 /tmp/ep_test.txt 2>/dev/null | tr '\n' ' ')
    if [ "$code" = "200" ]; then
        echo "OK  $code [${size}b] $ep"
    else
        echo "ERR $code [${size}b] $ep -> $snip"
    fi
done
