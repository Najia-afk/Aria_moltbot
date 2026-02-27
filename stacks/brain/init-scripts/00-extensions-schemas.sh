#!/bin/bash
set -e

# ============================================================================
# Bootstrap: PostgreSQL extensions + schema namespaces
# Runs once on first DB init inside aria_warehouse.
# ============================================================================

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Extensions
    CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
    CREATE EXTENSION IF NOT EXISTS "pg_trgm";
    CREATE EXTENSION IF NOT EXISTS vector;

    -- Schema namespaces
    CREATE SCHEMA IF NOT EXISTS aria_data;
    CREATE SCHEMA IF NOT EXISTS aria_engine;
    CREATE SCHEMA IF NOT EXISTS litellm;
EOSQL

echo "Extensions + schemas (aria_data, aria_engine, litellm) created in $POSTGRES_DB"
