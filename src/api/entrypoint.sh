#!/bin/sh
# Aria API entrypoint — structured JSON logging configuration (S-24)
set -e

echo "=== Aria API Entrypoint ==="

# Configure structured JSON logging via environment
export LOG_FORMAT="${LOG_FORMAT:-json}"
export LOG_LEVEL="${LOG_LEVEL:-info}"

# Apply JSON access log format for uvicorn
if [ "$LOG_FORMAT" = "json" ]; then
    export UVICORN_ACCESS_LOG="--no-access-log"
    echo "Structured JSON logging enabled (level=$LOG_LEVEL)"
else
    export UVICORN_ACCESS_LOG=""
    echo "Plain text logging enabled (level=$LOG_LEVEL)"
fi

# Run database migrations or health check if requested
if [ "${RUN_MIGRATIONS:-false}" = "true" ]; then
    echo "Running database migrations..."
    python -c "from db.init import run_migrations; import asyncio; asyncio.run(run_migrations())" 2>/dev/null || echo "Migration skipped (module not available)"
fi

echo "Starting Aria API..."
exec uvicorn main:app \
    --host 0.0.0.0 \
    --port "${API_INTERNAL_PORT:-8000}" \
    --workers "${API_WORKERS:-2}" \
    --timeout-keep-alive 300 \
    --log-level "$LOG_LEVEL" \
    $UVICORN_ACCESS_LOG \
    "$@"
