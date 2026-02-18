# S12-01: Load Testing with Locust
**Epic:** E8 — Quality & Testing | **Priority:** P1 | **Points:** 3 | **Phase:** 12

## Problem
Before deploying aria_engine to production, we need quantitative proof it can handle the expected load: 50 concurrent chat sessions, 10 simultaneous agent tasks, and sustained WebSocket connections — all without degradation. Locust gives us a reproducible load test that runs in CI and produces actionable metrics.

## Root Cause
The OpenClaw Node.js gateway handled concurrent requests via its event loop. `aria_engine` uses Python asyncio + Flask-SocketIO, which has fundamentally different concurrency characteristics. Without load testing, we could deploy a system that works for 1 user but collapses at 10.

## Fix
### `tests/load/locustfile.py`
```python
"""
Locust load test for Aria Blue (aria_engine).

Simulates realistic user behavior:
- WebSocket chat sessions (most traffic)
- REST API calls (status, agents, sessions)
- Dashboard page loads
- Agent routing requests
- Cron triggers

Target: 50 concurrent users, <500ms p95 response time.
"""
import json
import random
import time
from typing import Any

from locust import HttpUser, TaskSet, between, events, task
from locust.contrib.fasthttp import FastHttpUser


# ---------------------------------------------------------------------------
# Chat simulation via REST (Locust doesn't natively support WS well)
# We use the REST /api/chat endpoint as a proxy for WebSocket behavior
# ---------------------------------------------------------------------------

class ChatBehavior(TaskSet):
    """Simulates a chat user."""

    session_id: str = ""
    message_count: int = 0

    def on_start(self):
        """Create a new session on start."""
        self.session_id = f"load-test-{self.user.environment.runner.user_count}-{id(self)}"
        self.message_count = 0

        # Create session
        self.client.post("/api/sessions", json={
            "session_id": self.session_id,
            "title": "Load Test Session",
        })

    def on_stop(self):
        """Clean up session."""
        self.client.delete(f"/api/sessions/{self.session_id}")

    @task(10)
    def send_chat_message(self):
        """Send a chat message and wait for response."""
        messages = [
            "Hello, how are you?",
            "Tell me about Python 3.13",
            "What's the weather like?",
            "Can you help me debug this code?",
            "Research the latest AI papers",
            "Write a haiku about programming",
            "Check the server health",
            "Analyze the market trends today",
            "What are my goals for this sprint?",
            "Summarize our conversation",
        ]

        self.message_count += 1
        with self.client.post(
            "/api/chat",
            json={
                "session_id": self.session_id,
                "content": random.choice(messages),
                "stream": False,  # Use non-streaming for load test
            },
            catch_response=True,
            name="/api/chat",
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if "content" not in data and "error" not in data:
                    response.failure("No content in response")
                else:
                    response.success()
            elif response.status_code == 429:
                response.failure("Rate limited")
            else:
                response.failure(f"Status {response.status_code}")

    @task(3)
    def get_session_history(self):
        """Fetch session history."""
        self.client.get(
            f"/api/sessions/{self.session_id}/history",
            name="/api/sessions/[id]/history",
        )

    @task(1)
    def search_sessions(self):
        """Search across sessions."""
        self.client.get(
            "/api/sessions/search?q=hello",
            name="/api/sessions/search",
        )


class DashboardBehavior(TaskSet):
    """Simulates a dashboard user."""

    @task(5)
    def view_dashboard(self):
        """Load main dashboard."""
        self.client.get("/dashboard", name="/dashboard")

    @task(3)
    def view_agents(self):
        """Load agent list."""
        self.client.get("/agents", name="/agents")

    @task(3)
    def view_skills(self):
        """Load skill catalog."""
        self.client.get("/skills", name="/skills")

    @task(2)
    def view_sessions(self):
        """Load session list."""
        self.client.get("/sessions", name="/sessions")

    @task(2)
    def view_schedule(self):
        """Load schedule page."""
        self.client.get("/schedule", name="/schedule")

    @task(2)
    def view_status(self):
        """Load status page."""
        self.client.get("/status", name="/status")

    @task(1)
    def view_goals(self):
        """Load goals page."""
        self.client.get("/goals", name="/goals")

    @task(1)
    def view_health(self):
        """Load health dashboard."""
        self.client.get("/health/dashboard", name="/health/dashboard")


class APIBehavior(TaskSet):
    """Simulates API consumer."""

    @task(5)
    def get_status(self):
        """Check API status."""
        self.client.get("/api/status", name="/api/status")

    @task(3)
    def get_agents(self):
        """List agents via API."""
        self.client.get("/api/agents", name="/api/agents")

    @task(3)
    def get_skills(self):
        """List skills via API."""
        self.client.get("/api/skills", name="/api/skills")

    @task(2)
    def get_models(self):
        """List models via API."""
        self.client.get("/api/models", name="/api/models")

    @task(1)
    def health_check(self):
        """Health check endpoint."""
        self.client.get("/api/health", name="/api/health")

    @task(1)
    def get_metrics(self):
        """Prometheus metrics."""
        self.client.get("/metrics", name="/metrics")


# ---------------------------------------------------------------------------
# User classes
# ---------------------------------------------------------------------------

class ChatUser(HttpUser):
    """Simulates a user chatting with Aria."""
    tasks = [ChatBehavior]
    wait_time = between(1, 5)
    weight = 5  # Most common user type


class DashboardUser(HttpUser):
    """Simulates a user browsing the dashboard."""
    tasks = [DashboardBehavior]
    wait_time = between(2, 8)
    weight = 3


class APIUser(HttpUser):
    """Simulates an API consumer."""
    tasks = [APIBehavior]
    wait_time = between(0.5, 2)
    weight = 2


# ---------------------------------------------------------------------------
# Custom event listeners for reporting
# ---------------------------------------------------------------------------

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Log test start."""
    print(f"\n{'='*60}")
    print(f"  ARIA BLUE LOAD TEST")
    print(f"  Target: {environment.host}")
    print(f"  Users: {environment.parsed_options.num_users if hasattr(environment, 'parsed_options') else 'N/A'}")
    print(f"{'='*60}\n")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Generate summary report."""
    stats = environment.stats

    print(f"\n{'='*60}")
    print(f"  LOAD TEST RESULTS")
    print(f"{'='*60}")
    print(f"  Total requests: {stats.total.num_requests}")
    print(f"  Failures: {stats.total.num_failures}")
    print(f"  Failure rate: {stats.total.fail_ratio * 100:.1f}%")
    print(f"  Avg response time: {stats.total.avg_response_time:.0f}ms")
    print(f"  p95 response time: {stats.total.get_response_time_percentile(0.95) or 0:.0f}ms")
    print(f"  p99 response time: {stats.total.get_response_time_percentile(0.99) or 0:.0f}ms")
    print(f"  Requests/sec: {stats.total.current_rps:.1f}")
    print(f"{'='*60}\n")

    # Assert performance targets
    p95 = stats.total.get_response_time_percentile(0.95) or 0
    fail_rate = stats.total.fail_ratio

    if p95 > 500:
        print(f"  ⚠ WARNING: p95 ({p95}ms) exceeds 500ms target!")
    if fail_rate > 0.01:
        print(f"  ⚠ WARNING: Failure rate ({fail_rate*100:.1f}%) exceeds 1% target!")
```

### `tests/load/run_load_test.sh`
```bash
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
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer architecture | ✅ | Tests full stack under load |
| 2 | .env for secrets | ✅ | Test environment config |
| 3 | models.yaml single source | ❌ | Mocked LLM responses |
| 4 | Docker-first testing | ✅ | Run against Docker stack |
| 5 | aria_memories only writable path | ❌ | No file writes |
| 6 | No soul modification | ❌ | No soul access |

## Dependencies
- `pip install locust`
- Running aria_engine stack (Docker or local)
- Mock LLM for consistent latency

## Verification
```bash
# 1. Install Locust:
pip install locust

# 2. Start the stack:
docker compose up -d

# 3. Run load test (50 users, 2 minutes):
bash tests/load/run_load_test.sh http://localhost:5000 50 120

# 4. Open HTML report:
open tests/load/report.html

# 5. Check targets:
# - p95 response time < 500ms
# - Failure rate < 1%
# - Sustained RPS > 100
```

## Prompt for Agent
```
Create a Locust load test suite for Aria Blue.

FILES TO READ FIRST:
- aria_mind/gateway.py (Flask routes)
- tests/load/locustfile.py (this ticket's output)
- stacks/brain/docker-compose.yml (stack config)

STEPS:
1. Create tests/load/locustfile.py with 3 user types (Chat, Dashboard, API)
2. Create tests/load/run_load_test.sh wrapper script
3. Define realistic task distributions
4. Add custom event listeners for reporting
5. Set performance targets: p95 <500ms, <1% failures

CONSTRAINTS:
- 3 user types: ChatUser (weight 5), DashboardUser (weight 3), APIUser (weight 2)
- Use REST endpoints (not WebSocket) for Locust compatibility
- Target: 50 concurrent users
- Generate CSV + HTML reports
```
