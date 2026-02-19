#!/bin/bash
# Run Aria Blue load test
# Usage: ./tests/load/run_load_test.sh [host] [users] [duration]

HOST="${1:-http://localhost:5000}"
USERS="${2:-50}"
DURATION="${3:-120}"  # seconds
SPAWN_RATE=5          # users/sec

echo "=== Aria Blue Load Test ==="
echo "Host: $HOST"
echo "Users: $USERS"
echo "Duration: ${DURATION}s"
echo "Spawn rate: ${SPAWN_RATE}/s"
echo ""

locust \
    -f tests/load/locustfile.py \
    --host "$HOST" \
    --users "$USERS" \
    --spawn-rate "$SPAWN_RATE" \
    --run-time "${DURATION}s" \
    --headless \
    --csv=tests/load/results \
    --html=tests/load/report.html \
    --print-stats \
    --only-summary

echo ""
echo "=== Results ==="
echo "CSV:  tests/load/results_stats.csv"
echo "HTML: tests/load/report.html"
echo ""

# Check results against targets
P95=$(tail -1 tests/load/results_stats.csv | cut -d',' -f9)
FAIL_RATE=$(tail -1 tests/load/results_stats.csv | cut -d',' -f4)

echo "P95 response time: ${P95}ms (target: <500ms)"
echo "Failure rate: ${FAIL_RATE}% (target: <1%)"

if [ "${P95:-0}" -gt 500 ]; then
    echo "FAIL: P95 exceeds target"
    exit 1
fi
echo "PASS: All targets met"
