#!/bin/bash
set -e

# Create 'litellm' SCHEMA inside the main aria_warehouse database.
# LiteLLM tables live in the same DB, isolated by schema.
# The search_path on LiteLLM's connection URL makes it transparent.
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE SCHEMA IF NOT EXISTS litellm;
    -- Extensions needed by LiteLLM (uuid generation)
    CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
    CREATE EXTENSION IF NOT EXISTS "pg_trgm";
    CREATE EXTENSION IF NOT EXISTS vector;
    -- Schemas for Aria
    CREATE SCHEMA IF NOT EXISTS aria_data;
    CREATE SCHEMA IF NOT EXISTS aria_engine;
EOSQL

echo "LiteLLM schema + extensions created in $POSTGRES_DB"
