# aria_skills/agent_manager/__init__.py
"""
Agent Manager Skill — runtime agent lifecycle management.

Provides Aria with programmatic control over agent sessions:
spawn, monitor, terminate, prune stale sessions, generate reports.
All data access through aria-api (httpx HTTP client).
"""
import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus
from aria_skills.registry import SkillRegistry

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False


@SkillRegistry.register
class AgentManagerSkill(BaseSkill):
    """
    Runtime agent lifecycle management via aria-api.

    Methods:
        list_agents() — list active agent sessions
        spawn_agent(agent_type, context) — create session with context protocol
        terminate_agent(session_id) — graceful shutdown
        get_agent_stats(session_id) — usage metrics for one session
        prune_stale_sessions(max_age_hours) — bulk cleanup
        get_performance_report() — aggregate metrics
    """

    def __init__(self, config: SkillConfig):
        super().__init__(config)
        self._client: Optional[httpx.AsyncClient] = None
        self._api_url: str = ""

    @property
    def name(self) -> str:
        return "agent_manager"

    async def initialize(self) -> bool:
        """Initialize HTTP client for aria-api."""
        if not HAS_HTTPX:
            self.logger.error("httpx not installed — agent_manager unavailable")
            self._status = SkillStatus.UNAVAILABLE
            return False

        self._api_url = self.config.config.get(
            "api_url",
            os.environ.get("ARIA_API_URL", "http://aria-api:8000/api"),
        )
        self._client = httpx.AsyncClient(
            base_url=self._api_url,
            timeout=30.0,
        )
        self._status = SkillStatus.AVAILABLE
        return True

    async def health_check(self) -> SkillStatus:
        """Check aria-api health."""
        if not self._client:
            return SkillStatus.UNAVAILABLE
        try:
            resp = await self._client.get("/health")
            if resp.status_code == 200:
                self._status = SkillStatus.AVAILABLE
            else:
                self._status = SkillStatus.ERROR
        except Exception:
            self._status = SkillStatus.ERROR
        return self._status

    # ── Core methods ─────────────────────────────────────────────

    async def list_agents(
        self,
        status: Optional[str] = None,
        agent_id: Optional[str] = None,
        limit: int = 50,
    ) -> SkillResult:
        """List agent sessions, optionally filtered by status or agent_id."""
        if not self._client:
            return SkillResult.fail("Not initialized")

        params: dict[str, Any] = {"limit": limit}
        if status:
            params["status"] = status
        if agent_id:
            params["agent_id"] = agent_id

        try:
            resp = await self._client.get("/sessions", params=params)
            resp.raise_for_status()
            data = resp.json()
            self._log_usage("list_agents", True, count=data.get("count", 0))
            return SkillResult.ok(data)
        except Exception as e:
            self._log_usage("list_agents", False, error=str(e))
            return SkillResult.fail(f"Failed to list agents: {e}")

    async def spawn_agent(
        self,
        agent_type: str,
        context: Optional[dict] = None,
    ) -> SkillResult:
        """Spawn an agent session with optional context protocol.

        Args:
            agent_type: Agent ID (e.g. "analyst", "creator", "devops")
            context: Optional dict with context protocol fields:
                task, constraints, budget_tokens, deadline_seconds,
                parent_id, priority, tools_allowed, memory_scope
        """
        if not self._client:
            return SkillResult.fail("Not initialized")

        # Validate context if provided
        if context and not context.get("task"):
            return SkillResult.fail("Context must include a non-empty 'task' field")

        body: dict[str, Any] = {
            "agent_id": agent_type,
            "session_type": "managed",
            "metadata": context or {},
        }

        try:
            resp = await self._client.post("/sessions", json=body)
            resp.raise_for_status()
            data = resp.json()
            self._log_usage("spawn_agent", True, agent_type=agent_type)
            return SkillResult.ok(data)
        except Exception as e:
            self._log_usage("spawn_agent", False, error=str(e))
            return SkillResult.fail(f"Failed to spawn agent: {e}")

    async def terminate_agent(self, session_id: str) -> SkillResult:
        """Terminate an agent session gracefully.

        Args:
            session_id: UUID of the session to terminate
        """
        if not self._client:
            return SkillResult.fail("Not initialized")

        try:
            resp = await self._client.patch(
                f"/sessions/{session_id}",
                json={"status": "terminated"},
            )
            resp.raise_for_status()
            self._log_usage("terminate_agent", True, session_id=session_id)
            return SkillResult.ok({"session_id": session_id, "status": "terminated"})
        except Exception as e:
            self._log_usage("terminate_agent", False, error=str(e))
            return SkillResult.fail(f"Failed to terminate agent: {e}")

    async def get_agent_stats(self, session_id: Optional[str] = None) -> SkillResult:
        """Get session statistics, optionally for a specific session.

        Args:
            session_id: Optional specific session UUID. If None, returns aggregate stats.
        """
        if not self._client:
            return SkillResult.fail("Not initialized")

        try:
            if session_id:
                # Get specific session by listing with agent filter
                # The API doesn't have a GET /sessions/{id} endpoint,
                # so we use the stats endpoint for aggregate and filter list for specific
                resp = await self._client.get("/sessions", params={"limit": 100})
                resp.raise_for_status()
                sessions = resp.json().get("sessions", [])
                match = [s for s in sessions if s.get("id") == session_id]
                if not match:
                    return SkillResult.fail(f"Session {session_id} not found")
                data = match[0]
            else:
                resp = await self._client.get("/sessions/stats")
                resp.raise_for_status()
                data = resp.json()

            self._log_usage("get_agent_stats", True)
            return SkillResult.ok(data)
        except Exception as e:
            self._log_usage("get_agent_stats", False, error=str(e))
            return SkillResult.fail(f"Failed to get agent stats: {e}")

    async def prune_stale_sessions(self, max_age_hours: int = 6) -> SkillResult:
        """Terminate sessions older than max_age_hours that are still active.

        Args:
            max_age_hours: Maximum age in hours before session is considered stale.
        """
        if not self._client:
            return SkillResult.fail("Not initialized")

        try:
            # Fetch active sessions
            resp = await self._client.get(
                "/sessions",
                params={"status": "active", "limit": 200},
            )
            resp.raise_for_status()
            sessions = resp.json().get("sessions", [])

            cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
            pruned = []

            for s in sessions:
                started = s.get("started_at")
                if not started:
                    continue
                # Parse ISO timestamp
                try:
                    started_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    continue

                if started_dt < cutoff:
                    # Terminate stale session
                    term_resp = await self._client.patch(
                        f"/sessions/{s['id']}",
                        json={"status": "terminated"},
                    )
                    if term_resp.status_code == 200:
                        pruned.append(s["id"])

            self._log_usage("prune_stale_sessions", True, pruned_count=len(pruned))
            return SkillResult.ok({
                "pruned": len(pruned),
                "session_ids": pruned,
                "cutoff_hours": max_age_hours,
            })
        except Exception as e:
            self._log_usage("prune_stale_sessions", False, error=str(e))
            return SkillResult.fail(f"Failed to prune sessions: {e}")

    async def get_performance_report(self) -> SkillResult:
        """Generate aggregate performance report across all agents."""
        if not self._client:
            return SkillResult.fail("Not initialized")

        try:
            resp = await self._client.get("/sessions/stats")
            resp.raise_for_status()
            stats = resp.json()

            report = {
                "total_sessions": stats.get("total_sessions", 0),
                "active_sessions": stats.get("active_sessions", 0),
                "total_tokens": stats.get("total_tokens", 0),
                "total_cost_usd": stats.get("total_cost", 0),
                "by_agent": stats.get("by_agent", []),
                "by_status": stats.get("by_status", []),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }

            self._log_usage("get_performance_report", True)
            return SkillResult.ok(report)
        except Exception as e:
            self._log_usage("get_performance_report", False, error=str(e))
            return SkillResult.fail(f"Failed to generate report: {e}")
