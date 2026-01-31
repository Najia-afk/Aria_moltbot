#!/bin/bash
# Quick status check for Aria stack
# Run on Mac Mini

DOCKER="/Applications/Docker.app/Contents/Resources/bin/docker"

echo "=== Aria Blue Status ==="
echo ""
echo "Containers:"
$DOCKER ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "aria|NAME"

echo ""
echo "Health Checks:"
curl -s http://localhost/api/health 2>/dev/null && echo " - API: OK" || echo " - API: DOWN"
curl -s http://localhost:8080/api/overview 2>/dev/null >/dev/null && echo " - Traefik: OK" || echo " - Traefik: DOWN"
curl -s http://localhost/grafana/api/health 2>/dev/null >/dev/null && echo " - Grafana: OK" || echo " - Grafana: DOWN"

echo ""
echo "Database:"
$DOCKER exec aria-db psql -U aria_admin -d aria_bubble -c "SELECT COUNT(*) as thoughts FROM thought;" 2>/dev/null || echo "DB: Cannot connect"
