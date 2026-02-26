#!/bin/sh
# Traefik entrypoint — renders dynamic config template with envsubst before starting

set -e

echo "=== Traefik Entrypoint ==="

# Render template with environment variable substitution
echo "Rendering traefik-dynamic.yaml from template via envsubst..."
envsubst '${SERVICE_HOST} ${CORS_ALLOWED_ORIGINS} ${TRAEFIK_DASHBOARD_USER} ${TRAEFIK_DASHBOARD_PASSWORD_HASH}' \
  < /etc/traefik/dynamic.template.yaml \
  > /etc/traefik/dynamic.yaml

echo "Dynamic config ready."

# Start Traefik with all original arguments
echo "Starting Traefik..."
exec traefik "$@"
