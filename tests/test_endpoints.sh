#!/bin/bash
# Test all endpoints from Mac
HOST="http://localhost"
HOST_S="https://localhost"

endpoints=(
    "/ Portal"
    "/api/health API-Health"
    "/api/models API-Models"
    "/api/status API-Status"
    "/api/cron-jobs API-CronJobs"
    "/api/services API-Services"
    "/api/activity API-Activity"
    "/api/db-health API-DBHealth"
    "/grafana/api/health Grafana"
    "/prometheus/api/v1/status/runtimeinfo Prometheus"
    "/pgadmin/ PgAdmin"
    "/litellm/health LiteLLM"
    "/traefik/api/overview Traefik-Dashboard"
)

echo "=== HTTP Tests (port 80) ==="
for entry in "${endpoints[@]}"; do
    path=$(echo "$entry" | cut -d' ' -f1)
    name=$(echo "$entry" | cut -d' ' -f2)
    code=$(curl -sk -o /tmp/ep_test.txt -w '%{http_code}' "${HOST}${path}" 2>/dev/null)
    size=$(wc -c < /tmp/ep_test.txt 2>/dev/null | tr -d ' ')
    snippet=$(head -c 100 /tmp/ep_test.txt 2>/dev/null | tr '\n' ' ')
    echo "$name: $code [${size}b] $snippet"
done

echo ""
echo "=== HTTPS Tests (port 443) ==="
for entry in "${endpoints[@]}"; do
    path=$(echo "$entry" | cut -d' ' -f1)
    name=$(echo "$entry" | cut -d' ' -f2)
    code=$(curl -sk -o /tmp/ep_test.txt -w '%{http_code}' "${HOST_S}${path}" 2>/dev/null)
    size=$(wc -c < /tmp/ep_test.txt 2>/dev/null | tr -d ' ')
    snippet=$(head -c 100 /tmp/ep_test.txt 2>/dev/null | tr '\n' ' ')
    echo "$name: $code [${size}b] $snippet"
done

echo ""
echo "=== Testing from external IP perspective ==="
echo "Checking Traefik entrypoints binding..."
curl -sk http://localhost:8081/api/entrypoints 2>/dev/null | python3 -m json.tool 2>/dev/null | head -30 || echo "Traefik API not reachable on 8081"
