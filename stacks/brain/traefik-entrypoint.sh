#!/bin/sh
# Traefik entrypoint with envsubst for secure token injection
# This script generates traefik-dynamic.yaml from template before starting Traefik

set -e

echo "=== Traefik Secure Entrypoint ==="

# Install gettext (provides envsubst) if not present
if ! command -v envsubst >/dev/null 2>&1; then
    echo "Installing gettext for envsubst..."
    apk add --no-cache gettext >/dev/null 2>&1
fi

# Use default token if not provided
if [ -z "$CLAWDBOT_TOKEN" ]; then
    echo "WARNING: CLAWDBOT_TOKEN not set, using default-clawdbot-token"
    export CLAWDBOT_TOKEN="default-clawdbot-token"
fi

# Generate dynamic config from template using envsubst
# Only substitute CLAWDBOT_TOKEN to avoid breaking other $variables in YAML
echo "Generating traefik-dynamic.yaml from template..."
envsubst '${CLAWDBOT_TOKEN}' < /etc/traefik/dynamic.template.yaml > /etc/traefik/dynamic.yaml

echo "Token injected successfully (token length: ${#CLAWDBOT_TOKEN} chars)"

# Start Traefik with all original arguments
echo "Starting Traefik..."
exec traefik "$@"
