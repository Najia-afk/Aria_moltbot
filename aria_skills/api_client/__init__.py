# aria_skills/api_client.py
"""
Aria API Client Skill.

Centralized HTTP client for all aria-api interactions.
Skills should use this instead of direct database access.
"""
import os
from typing import Any, Dict, List, Optional
from datetime import datetime

from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus
from aria_skills.registry import SkillRegistry

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False


@SkillRegistry.register
class AriaAPIClient(BaseSkill):
    """
    HTTP client for Aria's FastAPI backend.
    
    Config:
        api_url: Base URL for aria-api (default: http://aria-api:8000/api)
        timeout: Request timeout in seconds (default: 30)
    """
    
    def __init__(self, config: SkillConfig):
        super().__init__(config)
        self._client: Optional["httpx.AsyncClient"] = None
        self._api_url: str = ""
    
    @property
    def name(self) -> str:
        return "api_client"
    
    async def initialize(self) -> bool:
        """Initialize HTTP client."""
        if not HAS_HTTPX:
            self.logger.error("httpx not installed")
            self._status = SkillStatus.UNAVAILABLE
            return False
        
        self._api_url = self.config.config.get(
            "api_url", 
            os.environ.get("ARIA_API_URL", "http://aria-api:8000/api")
        ).rstrip("/")
        
        timeout = self.config.config.get("timeout", 30)
        
        self._client = httpx.AsyncClient(
            base_url=self._api_url,
            timeout=timeout,
            headers={"Content-Type": "application/json"}
        )
        
        self._status = SkillStatus.AVAILABLE
        self.logger.info(f"API client initialized: {self._api_url}")
        return True
    
    async def health_check(self) -> SkillStatus:
        """Check API connectivity."""
        if not self._client:
            self._status = SkillStatus.UNAVAILABLE
            return self._status
        
        try:
            resp = await self._client.get("/health")
            if resp.status_code == 200:
                self._status = SkillStatus.AVAILABLE
            else:
                self._status = SkillStatus.ERROR
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            self._status = SkillStatus.ERROR
        
        return self._status
    
    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
            self._status = SkillStatus.UNAVAILABLE
    
    # ========================================
    # Activities
    # ========================================
    async def get_activities(self, limit: int = 50, page: int = 1) -> SkillResult:
        """Get recent activities (paginated)."""
        try:
            resp = await self._client.get(f"/activities?limit={limit}&page={page}")
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
        except Exception as e:
            return SkillResult.fail(f"Failed to get activities: {e}")
    
    async def create_activity(
        self, 
        action: str, 
        skill: Optional[str] = None,
        details: Optional[Dict] = None,
        success: bool = True,
        error_message: Optional[str] = None
    ) -> SkillResult:
        """Log an activity."""
        try:
            resp = await self._client.post("/activities", json={
                "action": action,
                "skill": skill,
                "details": details or {},
                "success": success,
                "error_message": error_message
            })
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
        except Exception as e:
            return SkillResult.fail(f"Failed to create activity: {e}")
    
    # ========================================
    # Security Events
    # ========================================
    async def get_security_events(
        self, 
        limit: int = 25, 
        page: int = 1,
        threat_level: Optional[str] = None,
        blocked_only: bool = False
    ) -> SkillResult:
        """Get security events (paginated)."""
        try:
            url = f"/security-events?limit={limit}&page={page}"
            if threat_level:
                url += f"&threat_level={threat_level}"
            if blocked_only:
                url += "&blocked_only=true"
            resp = await self._client.get(url)
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
        except Exception as e:
            return SkillResult.fail(f"Failed to get security events: {e}")
    
    async def create_security_event(
        self,
        threat_level: str = "LOW",
        threat_type: str = "unknown",
        threat_patterns: Optional[List[str]] = None,
        input_preview: Optional[str] = None,
        source: str = "api",
        user_id: Optional[str] = None,
        blocked: bool = False,
        details: Optional[Dict] = None
    ) -> SkillResult:
        """Log a security event."""
        try:
            resp = await self._client.post("/security-events", json={
                "threat_level": threat_level,
                "threat_type": threat_type,
                "threat_patterns": threat_patterns or [],
                "input_preview": input_preview,
                "source": source,
                "user_id": user_id,
                "blocked": blocked,
                "details": details or {}
            })
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
        except Exception as e:
            return SkillResult.fail(f"Failed to create security event: {e}")
    
    async def get_security_stats(self) -> SkillResult:
        """Get security event statistics."""
        try:
            resp = await self._client.get("/security-events/stats")
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
        except Exception as e:
            return SkillResult.fail(f"Failed to get security stats: {e}")
    
    # ========================================
    # Thoughts
    # ========================================
    async def get_thoughts(self, limit: int = 25, page: int = 1) -> SkillResult:
        """Get recent thoughts (paginated)."""
        try:
            resp = await self._client.get(f"/thoughts?limit={limit}&page={page}")
            resp.raise_for_status()
            data = resp.json()
            return SkillResult.ok(data.get("thoughts", data))
        except Exception as e:
            return SkillResult.fail(f"Failed to get thoughts: {e}")
    
    async def create_thought(
        self, 
        content: str, 
        category: str = "general",
        metadata: Optional[Dict] = None
    ) -> SkillResult:
        """Create a thought."""
        try:
            resp = await self._client.post("/thoughts", json={
                "content": content,
                "category": category,
                "metadata": metadata or {}
            })
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
        except Exception as e:
            return SkillResult.fail(f"Failed to create thought: {e}")
    
    # ========================================
    # Memories
    # ========================================
    async def get_memories(
        self, 
        limit: int = 25, 
        page: int = 1,
        category: Optional[str] = None
    ) -> SkillResult:
        """Get memories (paginated)."""
        try:
            url = f"/memories?limit={limit}&page={page}"
            if category:
                url += f"&category={category}"
            resp = await self._client.get(url)
            resp.raise_for_status()
            data = resp.json()
            return SkillResult.ok(data.get("memories", data))
        except Exception as e:
            return SkillResult.fail(f"Failed to get memories: {e}")
    
    async def get_memory(self, key: str) -> SkillResult:
        """Get a specific memory by key."""
        try:
            resp = await self._client.get(f"/memories/{key}")
            if resp.status_code == 404:
                return SkillResult.ok(None)
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
        except Exception as e:
            return SkillResult.fail(f"Failed to get memory: {e}")
    
    async def set_memory(
        self, 
        key: str, 
        value: Any, 
        category: str = "general"
    ) -> SkillResult:
        """Create or update a memory."""
        try:
            resp = await self._client.post("/memories", json={
                "key": key,
                "value": value,
                "category": category
            })
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
        except Exception as e:
            return SkillResult.fail(f"Failed to set memory: {e}")
    
    async def delete_memory(self, key: str) -> SkillResult:
        """Delete a memory."""
        try:
            resp = await self._client.delete(f"/memories/{key}")
            resp.raise_for_status()
            return SkillResult.ok({"deleted": True, "key": key})
        except Exception as e:
            return SkillResult.fail(f"Failed to delete memory: {e}")
    
    # ========================================
    # Goals
    # ========================================
    async def get_goals(
        self, 
        limit: int = 25, 
        page: int = 1,
        status: Optional[str] = None
    ) -> SkillResult:
        """Get goals (paginated)."""
        try:
            url = f"/goals?limit={limit}&page={page}"
            if status:
                url += f"&status={status}"
            resp = await self._client.get(url)
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
        except Exception as e:
            return SkillResult.fail(f"Failed to get goals: {e}")
    
    async def create_goal(
        self,
        title: str,
        description: str = "",
        priority: int = 2,
        status: str = "pending",
        due_date: Optional[str] = None,
        goal_id: Optional[str] = None
    ) -> SkillResult:
        """Create a goal."""
        try:
            data = {
                "title": title,
                "description": description,
                "priority": priority,
                "status": status
            }
            if due_date:
                data["due_date"] = due_date
            if goal_id:
                data["goal_id"] = goal_id
            
            resp = await self._client.post("/goals", json=data)
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
        except Exception as e:
            return SkillResult.fail(f"Failed to create goal: {e}")
    
    async def update_goal(
        self,
        goal_id: str,
        status: Optional[str] = None,
        progress: Optional[int] = None,
        priority: Optional[int] = None
    ) -> SkillResult:
        """Update a goal."""
        try:
            data = {}
            if status is not None:
                data["status"] = status
            if progress is not None:
                data["progress"] = progress
            if priority is not None:
                data["priority"] = priority
            
            resp = await self._client.patch(f"/goals/{goal_id}", json=data)
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
        except Exception as e:
            return SkillResult.fail(f"Failed to update goal: {e}")
    
    async def delete_goal(self, goal_id: str) -> SkillResult:
        """Delete a goal."""
        try:
            resp = await self._client.delete(f"/goals/{goal_id}")
            resp.raise_for_status()
            return SkillResult.ok({"deleted": True})
        except Exception as e:
            return SkillResult.fail(f"Failed to delete goal: {e}")
    
    # ========================================
    # Hourly Goals
    # ========================================
    async def get_hourly_goals(self, status: Optional[str] = None) -> SkillResult:
        """Get hourly goals."""
        try:
            url = "/hourly-goals"
            if status:
                url += f"?status={status}"
            resp = await self._client.get(url)
            resp.raise_for_status()
            data = resp.json()
            return SkillResult.ok(data.get("goals", data))
        except Exception as e:
            return SkillResult.fail(f"Failed to get hourly goals: {e}")
    
    async def create_hourly_goal(
        self,
        hour_slot: int,
        goal_type: str,
        description: str,
        status: str = "pending"
    ) -> SkillResult:
        """Create an hourly goal."""
        try:
            resp = await self._client.post("/hourly-goals", json={
                "hour_slot": hour_slot,
                "goal_type": goal_type,
                "description": description,
                "status": status
            })
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
        except Exception as e:
            return SkillResult.fail(f"Failed to create hourly goal: {e}")
    
    async def update_hourly_goal(
        self,
        goal_id: int,
        status: str
    ) -> SkillResult:
        """Update an hourly goal status."""
        try:
            resp = await self._client.patch(f"/hourly-goals/{goal_id}", json={
                "status": status
            })
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
        except Exception as e:
            return SkillResult.fail(f"Failed to update hourly goal: {e}")
    
    # ========================================
    # Knowledge Graph
    # ========================================
    async def get_knowledge_graph(self) -> SkillResult:
        """Get full knowledge graph."""
        try:
            resp = await self._client.get("/knowledge-graph")
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
        except Exception as e:
            return SkillResult.fail(f"Failed to get knowledge graph: {e}")
    
    async def get_entities(
        self, 
        limit: int = 100, 
        entity_type: Optional[str] = None
    ) -> SkillResult:
        """Get knowledge entities."""
        try:
            url = f"/knowledge-graph/entities?limit={limit}"
            if entity_type:
                url += f"&type={entity_type}"
            resp = await self._client.get(url)
            resp.raise_for_status()
            data = resp.json()
            return SkillResult.ok(data.get("entities", data))
        except Exception as e:
            return SkillResult.fail(f"Failed to get entities: {e}")
    
    async def create_entity(
        self,
        name: str,
        entity_type: str,
        properties: Optional[Dict] = None
    ) -> SkillResult:
        """Create a knowledge entity."""
        try:
            resp = await self._client.post("/knowledge-graph/entities", json={
                "name": name,
                "type": entity_type,
                "properties": properties or {}
            })
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
        except Exception as e:
            return SkillResult.fail(f"Failed to create entity: {e}")
    
    async def create_relation(
        self,
        from_entity: str,
        to_entity: str,
        relation_type: str,
        properties: Optional[Dict] = None
    ) -> SkillResult:
        """Create a knowledge relation."""
        try:
            resp = await self._client.post("/knowledge-graph/relations", json={
                "from_entity": from_entity,
                "to_entity": to_entity,
                "relation_type": relation_type,
                "properties": properties or {}
            })
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
        except Exception as e:
            return SkillResult.fail(f"Failed to create relation: {e}")
    
    # ========================================
    # Social Posts
    # ========================================
    async def get_social_posts(
        self, 
        limit: int = 25, 
        page: int = 1,
        platform: Optional[str] = None
    ) -> SkillResult:
        """Get social posts (paginated)."""
        try:
            url = f"/social?limit={limit}&page={page}"
            if platform:
                url += f"&platform={platform}"
            resp = await self._client.get(url)
            resp.raise_for_status()
            data = resp.json()
            return SkillResult.ok(data.get("posts", data))
        except Exception as e:
            return SkillResult.fail(f"Failed to get social posts: {e}")
    
    async def create_social_post(
        self,
        content: str,
        platform: str = "unknown",
        visibility: str = "public",
        post_id: Optional[str] = None,
        reply_to: Optional[str] = None,
        url: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> SkillResult:
        """Create a social post."""
        try:
            data = {
                "content": content,
                "platform": platform,
                "visibility": visibility
            }
            if post_id:
                data["post_id"] = post_id
            if reply_to:
                data["reply_to"] = reply_to
            if url:
                data["url"] = url
            if metadata:
                data["metadata"] = metadata
            
            resp = await self._client.post("/social", json=data)
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
        except Exception as e:
            return SkillResult.fail(f"Failed to create social post: {e}")
    
    # ========================================
    # Heartbeat
    # ========================================
    async def get_heartbeats(self, limit: int = 50) -> SkillResult:
        """Get heartbeat logs."""
        try:
            resp = await self._client.get(f"/heartbeat?limit={limit}")
            resp.raise_for_status()
            data = resp.json()
            return SkillResult.ok(data.get("heartbeats", data))
        except Exception as e:
            return SkillResult.fail(f"Failed to get heartbeats: {e}")
    
    async def get_latest_heartbeat(self) -> SkillResult:
        """Get latest heartbeat."""
        try:
            resp = await self._client.get("/heartbeat/latest")
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
        except Exception as e:
            return SkillResult.fail(f"Failed to get latest heartbeat: {e}")
    
    async def create_heartbeat(
        self,
        beat_number: int = 0,
        status: str = "healthy",
        details: Optional[Dict] = None
    ) -> SkillResult:
        """Log a heartbeat."""
        try:
            resp = await self._client.post("/heartbeat", json={
                "beat_number": beat_number,
                "status": status,
                "details": details or {}
            })
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
        except Exception as e:
            return SkillResult.fail(f"Failed to create heartbeat: {e}")
    
    # ========================================
    # Performance
    # ========================================
    async def get_performance_logs(self, limit: int = 50) -> SkillResult:
        """Get performance logs."""
        try:
            resp = await self._client.get(f"/performance?limit={limit}")
            resp.raise_for_status()
            data = resp.json()
            return SkillResult.ok(data.get("logs", data))
        except Exception as e:
            return SkillResult.fail(f"Failed to get performance logs: {e}")
    
    async def create_performance_log(
        self,
        review_period: str,
        successes: Optional[str] = None,
        failures: Optional[str] = None,
        improvements: Optional[str] = None
    ) -> SkillResult:
        """Create a performance log."""
        try:
            resp = await self._client.post("/performance", json={
                "review_period": review_period,
                "successes": successes,
                "failures": failures,
                "improvements": improvements
            })
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
        except Exception as e:
            return SkillResult.fail(f"Failed to create performance log: {e}")
    
    # ========================================
    # Tasks
    # ========================================
    async def get_tasks(self, status: Optional[str] = None) -> SkillResult:
        """Get pending complex tasks."""
        try:
            url = "/tasks"
            if status:
                url += f"?status={status}"
            resp = await self._client.get(url)
            resp.raise_for_status()
            data = resp.json()
            return SkillResult.ok(data.get("tasks", data))
        except Exception as e:
            return SkillResult.fail(f"Failed to get tasks: {e}")
    
    async def create_task(
        self,
        task_type: str,
        description: str,
        agent_type: str,
        priority: str = "medium",
        task_id: Optional[str] = None
    ) -> SkillResult:
        """Create a pending complex task."""
        try:
            data = {
                "task_type": task_type,
                "description": description,
                "agent_type": agent_type,
                "priority": priority
            }
            if task_id:
                data["task_id"] = task_id
            
            resp = await self._client.post("/tasks", json=data)
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
        except Exception as e:
            return SkillResult.fail(f"Failed to create task: {e}")
    
    async def update_task(
        self,
        task_id: str,
        status: str,
        result: Optional[str] = None
    ) -> SkillResult:
        """Update a task status."""
        try:
            resp = await self._client.patch(f"/tasks/{task_id}", json={
                "status": status,
                "result": result
            })
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
        except Exception as e:
            return SkillResult.fail(f"Failed to update task: {e}")
    
    # ========================================
    # Schedule
    # ========================================
    async def get_schedule(self) -> SkillResult:
        """Get schedule tick status."""
        try:
            resp = await self._client.get("/schedule")
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
        except Exception as e:
            return SkillResult.fail(f"Failed to get schedule: {e}")
    
    async def trigger_schedule_tick(self) -> SkillResult:
        """Trigger a manual schedule tick."""
        try:
            resp = await self._client.post("/schedule/tick")
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
        except Exception as e:
            return SkillResult.fail(f"Failed to trigger tick: {e}")
    
    async def get_jobs(self, live: bool = False) -> SkillResult:
        """Get scheduled jobs."""
        try:
            url = "/jobs/live" if live else "/jobs"
            resp = await self._client.get(url)
            resp.raise_for_status()
            data = resp.json()
            return SkillResult.ok(data.get("jobs", data))
        except Exception as e:
            return SkillResult.fail(f"Failed to get jobs: {e}")
    
    async def sync_jobs(self) -> SkillResult:
        """Sync jobs from OpenClaw."""
        try:
            resp = await self._client.post("/jobs/sync")
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
        except Exception as e:
            return SkillResult.fail(f"Failed to sync jobs: {e}")
    
    # ========================================
    # Agent Sessions
    # ========================================
    async def get_sessions(
        self,
        limit: int = 25,
        page: int = 1,
        status: Optional[str] = None,
    ) -> SkillResult:
        """Get agent sessions (paginated)."""
        try:
            url = f"/sessions?limit={limit}&page={page}"
            if status:
                url += f"&status={status}"
            resp = await self._client.get(url)
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
        except Exception as e:
            return SkillResult.fail(f"Failed to get sessions: {e}")

    async def create_session(
        self,
        agent_id: str,
        session_type: str = "interactive",
        metadata: Optional[Dict] = None,
    ) -> SkillResult:
        """Start a new agent session."""
        try:
            resp = await self._client.post("/sessions", json={
                "agent_id": agent_id,
                "session_type": session_type,
                "metadata": metadata or {},
            })
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
        except Exception as e:
            return SkillResult.fail(f"Failed to create session: {e}")

    async def update_session(
        self,
        session_id: str,
        status: Optional[str] = None,
        messages_count: Optional[int] = None,
        tokens_used: Optional[int] = None,
        cost_usd: Optional[float] = None,
    ) -> SkillResult:
        """Update agent session."""
        try:
            data = {}
            if status is not None:
                data["status"] = status
            if messages_count is not None:
                data["messages_count"] = messages_count
            if tokens_used is not None:
                data["tokens_used"] = tokens_used
            if cost_usd is not None:
                data["cost_usd"] = cost_usd
            resp = await self._client.patch(f"/sessions/{session_id}", json=data)
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
        except Exception as e:
            return SkillResult.fail(f"Failed to update session: {e}")

    async def get_session_stats(self) -> SkillResult:
        """Get session statistics."""
        try:
            resp = await self._client.get("/sessions/stats")
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
        except Exception as e:
            return SkillResult.fail(f"Failed to get session stats: {e}")

    # ========================================
    # Model Usage
    # ========================================
    async def get_model_usage(self, limit: int = 50, page: int = 1) -> SkillResult:
        """Get model usage records (paginated)."""
        try:
            resp = await self._client.get(f"/model-usage?limit={limit}&page={page}")
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
        except Exception as e:
            return SkillResult.fail(f"Failed to get model usage: {e}")

    async def create_model_usage(
        self,
        model: str,
        provider: Optional[str] = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost_usd: float = 0.0,
        latency_ms: Optional[int] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> SkillResult:
        """Log model usage."""
        try:
            data: Dict[str, Any] = {
                "model": model,
                "provider": provider,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_usd": cost_usd,
                "success": success,
            }
            if latency_ms is not None:
                data["latency_ms"] = latency_ms
            if error_message:
                data["error_message"] = error_message
            if session_id:
                data["session_id"] = session_id
            resp = await self._client.post("/model-usage", json=data)
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
        except Exception as e:
            return SkillResult.fail(f"Failed to log model usage: {e}")

    async def get_model_usage_stats(self, hours: int = 24) -> SkillResult:
        """Get model usage statistics (merged with LiteLLM data)."""
        try:
            resp = await self._client.get(f"/model-usage/stats?hours={hours}")
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
        except Exception as e:
            return SkillResult.fail(f"Failed to get model usage stats: {e}")

    # ========================================
    # LiteLLM
    # ========================================
    async def get_litellm_models(self) -> SkillResult:
        """Get available LiteLLM models."""
        try:
            resp = await self._client.get("/litellm/models")
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
        except Exception as e:
            return SkillResult.fail(f"Failed to get LiteLLM models: {e}")

    async def get_litellm_health(self) -> SkillResult:
        """Get LiteLLM health status."""
        try:
            resp = await self._client.get("/litellm/health")
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
        except Exception as e:
            return SkillResult.fail(f"Failed to get LiteLLM health: {e}")

    async def get_litellm_spend(self, limit: int = 100) -> SkillResult:
        """Get LiteLLM spend logs."""
        try:
            resp = await self._client.get(f"/litellm/spend?limit={limit}")
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
        except Exception as e:
            return SkillResult.fail(f"Failed to get LiteLLM spend: {e}")

    # ========================================
    # Provider Balances
    # ========================================
    async def get_provider_balances(self) -> SkillResult:
        """Get provider balance info (Kimi, OpenRouter, local)."""
        try:
            resp = await self._client.get("/providers/balances")
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
        except Exception as e:
            return SkillResult.fail(f"Failed to get provider balances: {e}")

    # ========================================
    # Working Memory
    # ========================================
    async def remember(self, key: str, value: Any, category: str = "general",
                       importance: float = 0.5, ttl_hours: Optional[int] = None,
                       source: Optional[str] = None) -> SkillResult:
        """Store a working memory item."""
        try:
            resp = await self._client.post("/working-memory", json={
                "key": key, "value": value, "category": category,
                "importance": importance, "ttl_hours": ttl_hours, "source": source,
            })
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
        except Exception as e:
            return SkillResult.fail(f"Failed to store working memory: {e}")

    async def recall(self, key: Optional[str] = None,
                     category: Optional[str] = None,
                     limit: int = 25, page: int = 1) -> SkillResult:
        """Retrieve working memory items (paginated)."""
        try:
            params: Dict[str, Any] = {"limit": limit, "page": page}
            if key:
                params["key"] = key
            if category:
                params["category"] = category
            resp = await self._client.get("/working-memory", params=params)
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
        except Exception as e:
            return SkillResult.fail(f"Failed to recall working memory: {e}")

    async def get_working_memory_context(self, limit: int = 20,
                                          category: Optional[str] = None) -> SkillResult:
        """Get weighted-ranked context for LLM injection."""
        try:
            params: Dict[str, Any] = {"limit": limit}
            if category:
                params["category"] = category
            resp = await self._client.get("/working-memory/context", params=params)
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
        except Exception as e:
            return SkillResult.fail(f"Failed to get working memory context: {e}")

    async def working_memory_checkpoint(self) -> SkillResult:
        """Snapshot current working memory."""
        try:
            resp = await self._client.post("/working-memory/checkpoint", json={})
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
        except Exception as e:
            return SkillResult.fail(f"Failed to checkpoint working memory: {e}")

    async def restore_working_memory_checkpoint(self) -> SkillResult:
        """Restore from latest working memory checkpoint."""
        try:
            resp = await self._client.get("/working-memory/checkpoint")
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
        except Exception as e:
            return SkillResult.fail(f"Failed to restore checkpoint: {e}")

    async def forget_working_memory(self, item_id: str) -> SkillResult:
        """Delete a working memory item."""
        try:
            resp = await self._client.delete(f"/working-memory/{item_id}")
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
        except Exception as e:
            return SkillResult.fail(f"Failed to forget working memory item: {e}")

    async def update_working_memory(self, item_id: str, **kwargs) -> SkillResult:
        """Update a working memory item."""
        try:
            resp = await self._client.patch(f"/working-memory/{item_id}", json=kwargs)
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
        except Exception as e:
            return SkillResult.fail(f"Failed to update working memory item: {e}")

    # ========================================
    # Generic / Raw
    # ========================================
    async def get(self, path: str, params: Optional[Dict] = None) -> SkillResult:
        """Generic GET request."""
        try:
            resp = await self._client.get(path, params=params)
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
        except Exception as e:
            return SkillResult.fail(f"GET {path} failed: {e}")
    
    async def post(self, path: str, data: Optional[Dict] = None) -> SkillResult:
        """Generic POST request."""
        try:
            resp = await self._client.post(path, json=data)
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
        except Exception as e:
            return SkillResult.fail(f"POST {path} failed: {e}")
    
    async def patch(self, path: str, data: Optional[Dict] = None) -> SkillResult:
        """Generic PATCH request."""
        try:
            resp = await self._client.patch(path, json=data)
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
        except Exception as e:
            return SkillResult.fail(f"PATCH {path} failed: {e}")
    
    async def delete(self, path: str) -> SkillResult:
        """Generic DELETE request."""
        try:
            resp = await self._client.delete(path)
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
        except Exception as e:
            return SkillResult.fail(f"DELETE {path} failed: {e}")

    # ── Performance logging (S-21) ──────────────────────────────────

    async def log_agent_performance(self, data: dict) -> SkillResult:
        """POST agent performance record to aria-api."""
        return await self.post("/performance", data=data)

    async def get_agent_performance(
        self, agent_id: Optional[str] = None, limit: int = 100
    ) -> list:
        """GET agent performance records, optionally filtered by agent."""
        params: Dict[str, Any] = {"limit": limit}
        if agent_id:
            params["agent_id"] = agent_id
        result = await self.get("/performance", params=params)
        if result.success:
            return result.data.get("records", []) if isinstance(result.data, dict) else []
        return []

    async def get_all_pages(self, method_name: str, **kwargs) -> SkillResult:
        """Fetch all pages of a paginated endpoint."""
        all_items: list = []
        page = 1
        while True:
            result = await getattr(self, method_name)(page=page, **kwargs)
            if not result.success:
                return result
            data = result.data
            if isinstance(data, dict):
                all_items.extend(data.get("items", []))
                if page >= data.get("pages", 1):
                    break
            else:
                all_items.extend(data if isinstance(data, list) else [])
                break
            page += 1
        return SkillResult.ok({"items": all_items, "total": len(all_items)})


# Singleton instance for convenience
_client: Optional[AriaAPIClient] = None


async def get_api_client() -> AriaAPIClient:
    """Get or create the API client singleton."""
    global _client
    if _client is None:
        config = SkillConfig(name="api_client", config={})
        _client = AriaAPIClient(config)
        await _client.initialize()
    return _client
