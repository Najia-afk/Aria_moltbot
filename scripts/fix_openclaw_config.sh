#!/usr/bin/env bash
set -euo pipefail

DOCKER_BIN="${DOCKER_BIN:-docker}"
if ! command -v "$DOCKER_BIN" >/dev/null 2>&1 && command -v /usr/local/bin/docker >/dev/null 2>&1; then
  DOCKER_BIN="/usr/local/bin/docker"
fi

if ! command -v "$DOCKER_BIN" >/dev/null 2>&1; then
  echo "Docker not found"
  exit 1
fi

VOLUME_NAME="${OPENCLAW_VOLUME:-brain_openclaw_data}"

"$DOCKER_BIN" run --rm -v "$VOLUME_NAME:/root/.openclaw" alpine:3.20 sh -c 'apk add --no-cache jq >/dev/null 2>&1; jq "del(.workspace)" /root/.openclaw/openclaw.json > /root/.openclaw/openclaw.json.tmp; mv /root/.openclaw/openclaw.json.tmp /root/.openclaw/openclaw.json'

"$DOCKER_BIN" run --rm -v "$VOLUME_NAME:/root/.openclaw" alpine:3.20 sh -c 'cat /root/.openclaw/openclaw.json'
