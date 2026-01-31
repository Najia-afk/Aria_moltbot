#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STACK_DIR="$ROOT_DIR/stacks/brain"
DOCKER_BIN="${DOCKER_BIN:-docker}"

if ! command -v "$DOCKER_BIN" >/dev/null 2>&1; then
  if command -v /usr/local/bin/docker >/dev/null 2>&1; then
    DOCKER_BIN="/usr/local/bin/docker"
  fi
fi

if ! command -v "$DOCKER_BIN" >/dev/null 2>&1; then
  echo "Docker not found in PATH. Set DOCKER_BIN or install Docker."
  exit 1
fi

cd "$STACK_DIR"

if [ ! -f .env ]; then
  echo "Missing .env in $STACK_DIR"
  exit 1
fi

echo "🧹 Stopping stack and removing volumes..."
"$DOCKER_BIN" compose down -v

echo "🚀 Building and starting stack..."
"$DOCKER_BIN" compose up -d --build

echo "⏳ Waiting for API health..."
for i in {1..60}; do
  if curl -fsS http://localhost:8000/health >/dev/null 2>&1; then
    echo "✅ API is healthy"
    break
  fi
  sleep 2
  if [ "$i" -eq 60 ]; then
    echo "❌ API did not become healthy"
    docker compose ps
    exit 1
  fi
done

echo "⏳ Waiting for Aria brain to be healthy..."
for i in {1..60}; do
  if "$DOCKER_BIN" compose ps --format json | grep -q '"Service":"aria-brain"' && "$DOCKER_BIN" compose ps | grep -q 'aria-brain' && "$DOCKER_BIN" compose ps | grep -q 'healthy'; then
    echo "✅ Aria brain is healthy"
    break
  fi
  sleep 2
  if [ "$i" -eq 60 ]; then
    echo "❌ Aria brain not healthy yet"
    "$DOCKER_BIN" compose ps
    exit 1
  fi
done

echo "✅ One-click deploy complete."
