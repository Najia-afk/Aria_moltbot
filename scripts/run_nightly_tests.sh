#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if command -v docker >/dev/null 2>&1 && docker ps --format '{{.Names}}' | grep -qx aria-api; then
  docker exec aria-api python3 -m pytest tests/ -q --tb=short --maxfail=1
else
  python3 -m pytest tests/ -q --tb=short --maxfail=1
fi
