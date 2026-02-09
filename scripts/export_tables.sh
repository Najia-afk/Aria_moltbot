#!/bin/bash
# Export Aria tables to JSON for aria_memories sync
export PATH=/Applications/Docker.app/Contents/Resources/bin:/usr/bin:$PATH

# Source environment from .env if available
ENV_FILE="/Users/najia/aria/stacks/brain/.env"
if [ -f "${ENV_FILE}" ]; then
    set -a
    source "${ENV_FILE}"
    set +a
fi

OUTPUT_DIR="/Users/najia/aria/aria_memories/db_snapshots"
mkdir -p "$OUTPUT_DIR"

TABLES=(memories thoughts goals activity_log social_posts knowledge_entities)

echo "=== Exporting Aria Tables to JSON ==="
echo "Output: $OUTPUT_DIR"

for table in "${TABLES[@]}"; do
    echo "Exporting: $table"
    docker exec aria-db psql -U "${DB_USER:-admin}" -d aria_warehouse -t -A -c \
        "SELECT COALESCE(json_agg(row_to_json(t)), '[]') FROM $table t;" \
        > "${OUTPUT_DIR}/${table}.json"
    
    # Pretty print with python if available
    if command -v python3 &>/dev/null; then
        python3 -m json.tool "${OUTPUT_DIR}/${table}.json" > "${OUTPUT_DIR}/${table}_pretty.json" 2>/dev/null
        if [ $? -eq 0 ]; then
            mv "${OUTPUT_DIR}/${table}_pretty.json" "${OUTPUT_DIR}/${table}.json"
        fi
    fi
    
    count=$(docker exec aria-db psql -U "${DB_USER:-admin}" -d aria_warehouse -t -A -c "SELECT COUNT(*) FROM $table;")
    echo "  → $table: $count rows"
done

echo ""
echo "=== Export Complete ==="
ls -lh "$OUTPUT_DIR/"
