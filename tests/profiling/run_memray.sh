#!/bin/bash
# Run memray profiling for Aria Blue
# Captures C-level allocations that tracemalloc misses

DURATION="${1:-300}"  # seconds
OUTPUT_DIR="tests/profiling/results"
mkdir -p "$OUTPUT_DIR"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
MEMRAY_FILE="$OUTPUT_DIR/memray_${TIMESTAMP}.bin"

echo "=== Aria Blue Memray Profile ==="
echo "Duration: ${DURATION}s"
echo "Output: $MEMRAY_FILE"
echo ""

# Run with memray
python -m memray run --output "$MEMRAY_FILE" \
    tests/profiling/memory_profile.py --duration "$DURATION" --interval 30

# Generate reports
echo ""
echo "Generating reports..."
python -m memray stats "$MEMRAY_FILE" > "$OUTPUT_DIR/memray_stats_${TIMESTAMP}.txt"
python -m memray flamegraph "$MEMRAY_FILE" --output "$OUTPUT_DIR/memray_flamegraph_${TIMESTAMP}.html"
python -m memray table "$MEMRAY_FILE" --output "$OUTPUT_DIR/memray_table_${TIMESTAMP}.html"

echo ""
echo "Reports generated:"
echo "  Stats: $OUTPUT_DIR/memray_stats_${TIMESTAMP}.txt"
echo "  Flamegraph: $OUTPUT_DIR/memray_flamegraph_${TIMESTAMP}.html"
echo "  Table: $OUTPUT_DIR/memray_table_${TIMESTAMP}.html"
