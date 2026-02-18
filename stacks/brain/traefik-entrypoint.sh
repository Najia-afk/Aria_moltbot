#!/bin/sh
# Traefik entrypoint — copies dynamic config template into place before starting

set -e

echo "=== Traefik Entrypoint ==="

# Copy template as-is (no token substitution needed after OpenClaw removal)
echo "Copying traefik-dynamic.yaml from template..."
cp /etc/traefik/dynamic.template.yaml /etc/traefik/dynamic.yaml

echo "Dynamic config ready."

# Start Traefik with all original arguments
echo "Starting Traefik..."
exec traefik "$@"
