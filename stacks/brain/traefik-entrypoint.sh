#!/bin/sh
# Traefik entrypoint — renders dynamic config template with sed before starting

set -e

echo "=== Traefik Entrypoint ==="

# Render template with environment variable substitution (using sed, envsubst not available in Alpine)
echo "Rendering traefik-dynamic.yaml from template via sed..."
sed \
  -e "s|\${SERVICE_HOST}|${SERVICE_HOST}|g" \
  -e "s|\${CORS_ALLOWED_ORIGINS}|${CORS_ALLOWED_ORIGINS}|g" \
  -e "s|\${TRAEFIK_DASHBOARD_USER}|${TRAEFIK_DASHBOARD_USER}|g" \
  -e "s|\${TRAEFIK_DASHBOARD_PASSWORD_HASH}|${TRAEFIK_DASHBOARD_PASSWORD_HASH}|g" \
  /etc/traefik/dynamic.template.yaml > /etc/traefik/dynamic.yaml

echo "Dynamic config ready."

# Start Traefik with all original arguments
echo "Starting Traefik..."
exec traefik "$@"
