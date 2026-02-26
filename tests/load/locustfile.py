"""
Locust load tests for Aria API and Web services (S-30).

Run headless:
    locust -f tests/load/locustfile.py --headless \
        --users 10 --spawn-rate 2 --run-time 60s \
        --html tests/load/report.html

Run with UI:
    locust -f tests/load/locustfile.py
    # Open http://localhost:8089
"""
import json
import os
import uuid

from locust import HttpUser, between, tag, task


API_KEY = os.environ.get("ARIA_API_KEY", "test-api-key")


class AriaChatUser(HttpUser):
    """Simulates API consumers: skills, agents, external integrations."""

    wait_time = between(1, 3)
    host = os.environ.get("ARIA_API_HOST", "http://localhost:8000")

    def on_start(self):
        self.api_headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        }

    # ── Read-heavy workload ──────────────────────────────────────────────

    @task(5)
    @tag("health")
    def health_check(self):
        self.client.get("/api/health")

    @task(4)
    @tag("read")
    def list_activities(self):
        self.client.get(
            "/api/activities?limit=25",
            headers=self.api_headers,
            name="/api/activities",
        )

    @task(4)
    @tag("read")
    def list_thoughts(self):
        self.client.get(
            "/api/thoughts?limit=20",
            headers=self.api_headers,
            name="/api/thoughts",
        )

    @task(3)
    @tag("read")
    def list_memories(self):
        self.client.get(
            "/api/memories?limit=20",
            headers=self.api_headers,
            name="/api/memories",
        )

    @task(3)
    @tag("read")
    def list_goals(self):
        self.client.get(
            "/api/goals?limit=25",
            headers=self.api_headers,
            name="/api/goals",
        )

    @task(2)
    @tag("read")
    def list_sessions(self):
        self.client.get(
            "/api/sessions?limit=10",
            headers=self.api_headers,
            name="/api/sessions",
        )

    @task(1)
    @tag("read")
    def model_usage(self):
        self.client.get(
            "/api/model-usage?limit=10",
            headers=self.api_headers,
            name="/api/model-usage",
        )

    # ── GraphQL ──────────────────────────────────────────────────────────

    @task(2)
    @tag("graphql")
    def graphql_thoughts(self):
        self.client.post(
            "/graphql",
            json={"query": "{ thoughts(limit: 10) { id content category } }"},
            headers=self.api_headers,
            name="/graphql [thoughts]",
        )

    @task(1)
    @tag("graphql")
    def graphql_stats(self):
        self.client.post(
            "/graphql",
            json={"query": "{ stats { activitiesCount thoughtsCount memoriesCount goalsCount } }"},
            headers=self.api_headers,
            name="/graphql [stats]",
        )

    @task(1)
    @tag("graphql")
    def graphql_connection(self):
        self.client.post(
            "/graphql",
            json={
                "query": """
                    { activitiesConnection(first: 10) {
                        edges { cursor node { id action } }
                        pageInfo { hasNextPage endCursor }
                        totalCount
                    }}
                """
            },
            headers=self.api_headers,
            name="/graphql [connection]",
        )

    # ── Write workload ───────────────────────────────────────────────────

    @task(2)
    @tag("write")
    def create_and_delete_thought(self):
        resp = self.client.post(
            "/api/thoughts",
            json={"content": f"load test thought {uuid.uuid4().hex[:8]}", "category": "test"},
            headers=self.api_headers,
            name="/api/thoughts [POST]",
        )
        if resp.status_code in (200, 201):
            data = resp.json()
            thought_id = data.get("id")
            if thought_id:
                self.client.delete(
                    f"/api/thoughts/{thought_id}",
                    headers=self.api_headers,
                    name="/api/thoughts/{id} [DELETE]",
                )

    @task(1)
    @tag("write")
    def create_and_delete_activity(self):
        resp = self.client.post(
            "/api/activities",
            json={
                "action": "load_test",
                "content": f"load test activity {uuid.uuid4().hex[:8]}",
            },
            headers=self.api_headers,
            name="/api/activities [POST]",
        )
        if resp.status_code in (200, 201):
            data = resp.json()
            activity_id = data.get("id")
            if activity_id:
                self.client.delete(
                    f"/api/activities/{activity_id}",
                    headers=self.api_headers,
                    name="/api/activities/{id} [DELETE]",
                )

    # ── Skill health dashboard ───────────────────────────────────────────

    @task(1)
    @tag("read", "dashboard")
    def skill_health_dashboard(self):
        self.client.get(
            "/api/skills/health/dashboard?hours=24",
            headers=self.api_headers,
            name="/api/skills/health/dashboard",
        )


class AriaWebUser(HttpUser):
    """Simulates browser users navigating the web dashboard."""

    wait_time = between(2, 5)
    host = os.environ.get("ARIA_WEB_HOST", "http://localhost:5050")

    @task(5)
    @tag("web")
    def home_page(self):
        self.client.get("/", name="/ [home]")

    @task(3)
    @tag("web")
    def chat_page(self):
        self.client.get("/chat", name="/chat")

    @task(2)
    @tag("web")
    def engine_operations(self):
        self.client.get("/engine/operations", name="/engine/operations")

    @task(2)
    @tag("web")
    def model_manager(self):
        self.client.get("/model-manager", name="/model-manager")

    @task(1)
    @tag("web")
    def sentiment_page(self):
        self.client.get("/sentiment", name="/sentiment")

    @task(1)
    @tag("web")
    def skill_health(self):
        self.client.get("/skill-health", name="/skill-health")

    @task(1)
    @tag("web")
    def skill_catalog(self):
        self.client.get("/skills", name="/skills")

    @task(1)
    @tag("web")
    def sessions_page(self):
        self.client.get("/sessions", name="/sessions")
