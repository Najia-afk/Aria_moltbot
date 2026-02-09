#!/usr/bin/env bash
# entrypoint.sh — Starts the sandbox exec server on port 9999
set -euo pipefail

echo "Starting Aria Sandbox exec server on :${SANDBOX_PORT:-9999}"
exec python /sandbox/server.py
