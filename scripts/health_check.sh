#!/bin/bash
export PATH=/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:$PATH

echo "=== WEB PAGES ==="
for page in / /dashboard /activities /thoughts /memories /records /search /services /models /wallets /goals /heartbeat /knowledge /social /performance /security /operations /sessions /working-memory /skills /soul /model-usage /rate-limits /api-key-rotations; do
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "http://localhost:5000${page}")
  echo "  ${page} -> ${code}"
done
# NOTE: /heartbeat is the health monitoring page (no /health web route exists)

echo "=== API ENDPOINTS ==="
for ep in /api/health /api/status /api/stats /api/activities /api/thoughts /api/memories /api/goals /api/hourly-goals /api/sessions /api/skills /api/social /api/knowledge-graph /api/working-memory/context /api/rate-limits /api/security-events /api/schedule /api/litellm/models /api/litellm/spend /api/models/config /api/admin/soul /api/records/thoughts; do
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "http://localhost:8000${ep}")
  echo "  ${ep} -> ${code}"
done
# NOTE: /api/knowledge-graph is the correct path (not /api/knowledge)

echo "=== CRON JOBS ==="
docker exec clawdbot openclaw cron list 2>/dev/null | head -20

echo "=== MLX INFERENCE TEST ==="
python3 /tmp/test_mlx.py 2>&1

echo "=== TRAEFIK ROUTING ==="
for path in / /api/health /operations /litellm-proxy; do
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "http://localhost${path}")
  echo "  traefik${path} -> ${code}"
done

echo "=== DONE ==="
