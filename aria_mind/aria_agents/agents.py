"""Concrete agent implementations that integrate with OpenClaw.

These agents subclass BaseAgent and use sessions_spawn for actual execution.
"""
import json
import re
from typing import Any

from .base import AgentConfig, AgentResult, BaseAgent


class OpenClawAgent(BaseAgent):
    """Base agent that delegates to OpenClaw sub-agents via sessions_spawn.
    
    This bridges the Aria agent system with OpenClaw's native session spawning.
    """
    
    def __init__(self, config: AgentConfig, agent_id_override: str | None = None):
        """Initialize with optional agent ID override for OpenClaw mapping."""
        super().__init__(config)
        self.oc_agent_id = agent_id_override or config.id
    
    def execute(self, task: dict) -> AgentResult:
        """Execute task by spawning an OpenClaw sub-agent session.
        
        Args:
            task: Dict with type, params, context
            
        Returns:
            AgentResult from the spawned session
        """
        task_type = task.get("type", "unknown")
        params = task.get("params", {})
        context = task.get("context", "")
        
        # Build task prompt for the sub-agent
        prompt = self._build_prompt(task_type, params, context)
        
        try:
            # Import here to avoid circular deps at module load
            result = self._spawn_session(prompt, task.get("timeout"))
            return AgentResult(
                success=True,
                data=result,
                agent_id=self.id
            )
        except Exception as e:
            return AgentResult(
                success=False,
                error=f"Spawn failed: {e}",
                agent_id=self.id
            )
    
    def _build_prompt(self, task_type: str, params: dict, context: str) -> str:
        """Build the prompt for the sub-agent."""
        safe_task_type = self._sanitize_prompt_fragment(task_type, max_len=160)
        safe_context = self._sanitize_prompt_fragment(context, max_len=2400)
        prompt_parts = [
            f"You are the {self.focus} agent.",
            f"Task type: {safe_task_type}",
            f"Your capabilities: {', '.join(self.capabilities)}",
        ]
        if safe_context:
            prompt_parts.append(f"Context: {safe_context}")
        if params:
            try:
                params_text = json.dumps(params, indent=2, default=str)
            except Exception:
                params_text = str(params)
            prompt_parts.append(
                f"Parameters: {self._sanitize_prompt_fragment(params_text, max_len=2400)}"
            )
        return "\n".join(prompt_parts)

    def _sanitize_prompt_fragment(self, value: Any, max_len: int = 2000) -> str:
        text = str(value or "")
        text = re.sub(r"[\u200b-\u200f\u202a-\u202e\u2060-\u206f\ufeff]", "", text)
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:max_len]
    
    def _spawn_session(self, prompt: str, timeout: int | None = None) -> dict:
        """Spawn OpenClaw session. Override in tests or use mock.
        
        In production, this calls sessions_spawn. For now, returns mock.
        """
        # TODO: Integrate with actual sessions_spawn when available
        # from openclaw import sessions_spawn
        # return sessions_spawn(task=prompt, agent_id=self.oc_agent_id, timeout=timeout)
        return {
            "status": "mock_spawn",
            "agent": self.oc_agent_id,
            "prompt_preview": prompt[:100] + "..." if len(prompt) > 100 else prompt
        }


class DevOpsAgent(OpenClawAgent):
    """DevSecOps agent for security, code, and infrastructure tasks."""
    
    DEFAULT_CAPABILITIES = [
        "code_review", "security_scan", "testing", "deployment",
        "ci_cd", "infrastructure", "vulnerability_assessment"
    ]
    
    def __init__(self, config: AgentConfig | None = None):
        if config is None:
            config = AgentConfig(
                id="devops",
                focus="devsecops",
                model="qwen3-coder-free",
                fallback="gpt-oss-free",
                skills=["pytest_runner", "database", "health", "llm"],
                capabilities=self.DEFAULT_CAPABILITIES,
                timeout=600,
                parent="aria"
            )
        super().__init__(config, agent_id_override="devops")


class AnalystAgent(OpenClawAgent):
    """Data + Trader agent for analysis and market tasks."""
    
    DEFAULT_CAPABILITIES = [
        "data_analysis", "market_analysis", "experiment_tracking",
        "metrics", "portfolio_analysis", "trading_strategy"
    ]
    
    def __init__(self, config: AgentConfig | None = None):
        if config is None:
            config = AgentConfig(
                id="analyst",
                focus="data",
                model="deepseek-free",
                fallback="chimera-free",
                skills=["database", "knowledge_graph", "performance", "llm"],
                capabilities=self.DEFAULT_CAPABILITIES,
                timeout=600,
                parent="aria"
            )
        super().__init__(config, agent_id_override="analyst")


class CreatorAgent(OpenClawAgent):
    """Creative + Social + Journalist agent for content and community."""
    
    DEFAULT_CAPABILITIES = [
        "content_generation", "community_engagement", "fact_checking",
        "storytelling", "social_post", "research", "moltbook"
    ]
    
    def __init__(self, config: AgentConfig | None = None):
        if config is None:
            config = AgentConfig(
                id="creator",
                focus="social",
                model="trinity-free",
                fallback="qwen3-next-free",
                skills=["moltbook", "social", "knowledge_graph", "llm"],
                capabilities=self.DEFAULT_CAPABILITIES,
                timeout=300,
                parent="aria",
                rate_limit={"posts_per_hour": 2, "comments_per_day": 50}
            )
        super().__init__(config, agent_id_override="creator")


class MemoryAgent(OpenClawAgent):
    """Memory agent for storage and retrieval tasks."""
    
    DEFAULT_CAPABILITIES = [
        "memory_store", "memory_search", "context_retrieval",
        "knowledge_graph_query"
    ]
    
    def __init__(self, config: AgentConfig | None = None):
        if config is None:
            config = AgentConfig(
                id="memory",
                focus="memory",
                model="qwen3-mlx",
                fallback="qwen3-next-free",
                skills=["database", "knowledge_graph"],
                capabilities=self.DEFAULT_CAPABILITIES,
                timeout=120,
                parent="aria"
            )
        super().__init__(config, agent_id_override="memory")


class AriaTalkAgent(OpenClawAgent):
    """Conversational agent for direct user interaction."""
    
    DEFAULT_CAPABILITIES = [
        "conversation", "question_answering", "explanation",
        "social_interaction"
    ]
    
    def __init__(self, config: AgentConfig | None = None):
        if config is None:
            config = AgentConfig(
                id="aria_talk",
                focus="conversational",
                model="qwen3-mlx",
                fallback="trinity-free",
                skills=["database", "llm", "moltbook", "social"],
                capabilities=self.DEFAULT_CAPABILITIES,
                timeout=300,
                parent="aria",
                rate_limit={"messages_per_minute": 10}
            )
        super().__init__(config, agent_id_override="aria_talk")


def create_all_agents() -> list[BaseAgent]:
    """Factory function to create all default agents.
    
    Returns:
        List of fully configured agent instances
    """
    return [
        DevOpsAgent(),
        AnalystAgent(),
        CreatorAgent(),
        MemoryAgent(),
        AriaTalkAgent(),
    ]
