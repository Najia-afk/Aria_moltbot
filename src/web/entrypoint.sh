#!/bin/sh
# Aria Web entrypoint — dynamic port binding
set -e

exec gunicorn \
    --bind "0.0.0.0:${WEB_INTERNAL_PORT:-5000}" \
    --workers "${WEB_WORKERS:-4}" \
    --threads 2 \
    --timeout 120 \
    --keep-alive 5 \
    --graceful-timeout 30 \
    --max-requests 1000 \
    --max-requests-jitter 50 \
    "app:create_app()" \
    "$@"
