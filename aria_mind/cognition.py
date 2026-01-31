# aria_mind/cognition.py
"""
Cognition - Thinking, reasoning, and decision-making.

The cognitive engine that processes inputs and generates responses.
"""
import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from aria_mind.soul import Soul
    from aria_mind.memory import MemoryManager
    from aria_skills import SkillRegistry
    from aria_agents import AgentCoordinator


class Cognition:
    """
    Aria's cognitive system.
    
    Responsibilities:
    - Process user inputs
    - Apply soul constraints
    - Coordinate with agents
    - Generate responses
    """
    
    def __init__(
        self,
        soul: "Soul",
        memory: "MemoryManager",
        skill_registry: Optional["SkillRegistry"] = None,
        agent_coordinator: Optional["AgentCoordinator"] = None,
    ):
        self.soul = soul
        self.memory = memory
        self._skills = skill_registry
        self._agents = agent_coordinator
        self.logger = logging.getLogger("aria.cognition")
    
    def set_skill_registry(self, registry: "SkillRegistry"):
        """Inject skill registry."""
        self._skills = registry
    
    def set_agent_coordinator(self, coordinator: "AgentCoordinator"):
        """Inject agent coordinator."""
        self._agents = coordinator
    
    async def process(
        self,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Process a prompt and generate a response.
        
        Args:
            prompt: User input or thought
            context: Additional context
            
        Returns:
            Response string
        """
        context = context or {}
        
        # Step 1: Check boundaries
        allowed, reason = self.soul.check_request(prompt)
        if not allowed:
            self.logger.warning(f"Request blocked: {reason}")
            return f"I can't do that. {reason}"
        
        # Step 2: Add to short-term memory
        self.memory.remember_short(prompt, "user_input")
        
        # Step 3: Build context with recent memory
        recent = self.memory.recall_short(limit=5)
        context["recent_memory"] = recent
        context["system_prompt"] = self.soul.get_system_prompt()
        
        # Step 4: Process through agents if available
        if self._agents:
            try:
                response = await self._agents.process(prompt, **context)
                result = response.content
            except Exception as e:
                self.logger.error(f"Agent processing failed: {e}")
                result = await self._fallback_process(prompt, context)
        else:
            result = await self._fallback_process(prompt, context)
        
        # Step 5: Log thought
        await self.memory.log_thought(f"Responded to: {prompt[:50]}...")
        
        return result
    
    async def _fallback_process(
        self,
        prompt: str,
        context: Dict[str, Any],
    ) -> str:
        """
        Fallback processing without agents.
        
        Respects SOUL.md model hierarchy:
        1. ollama (qwen3-vl:8b) - Local, free, private, vision (DEFAULT per SOUL.md)
        2. gemini - Cloud fallback for quick tasks
        3. moonshot - Cloud fallback for creative/long tasks
        """
        if self._skills:
            # SOUL.md says: local first (qwen/ollama), then cloud fallback
            llm = (
                self._skills.get("ollama") or  # Local first (Aria's preference)
                self._skills.get("gemini") or  # Cloud fallback
                self._skills.get("moonshot")   # Alternative cloud
            )
            if llm and llm.is_available:
                result = await llm.generate(
                    prompt=prompt,
                    system_prompt=context.get("system_prompt"),
                )
                if result.success:
                    return result.data.get("text", "")
        
        # Last resort - acknowledge but can't process
        return (
            f"I hear you, but I don't have an LLM available right now. "
            f"You said: {prompt[:100]}..."
        )
    
    async def reflect(self) -> str:
        """
        Internal reflection process.
        
        Called periodically to process recent experiences.
        """
        recent = self.memory.recall_short(limit=20)
        
        if not recent:
            return "Nothing to reflect on yet."
        
        # Summarize recent activity
        summary_parts = []
        for entry in recent:
            category = entry.get("category", "unknown")
            content = entry.get("content", "")[:50]
            summary_parts.append(f"- [{category}] {content}...")
        
        summary = "\n".join(summary_parts)
        
        reflection = f"""Reflecting on recent activity...

{summary}

Key observations:
- {len(recent)} events in short-term memory
- Soul constraints active: {len(self.soul.boundaries.will_not)} boundaries

I remain {self.soul.identity.vibe}. ⚡️
"""
        
        await self.memory.log_thought(reflection, "reflection")
        return reflection
    
    async def plan(self, goal: str) -> List[str]:
        """
        Create a plan to achieve a goal.
        
        Args:
            goal: The goal to plan for
            
        Returns:
            List of steps
        """
        # Check if goal is allowed
        allowed, reason = self.soul.check_request(goal)
        if not allowed:
            return [f"Cannot plan for this goal: {reason}"]
        
        # Simple planning with available skills
        steps = [
            f"1. Analyze goal: {goal[:50]}...",
            "2. Check available skills",
        ]
        
        if self._skills:
            available = self._skills.list()
            steps.append(f"3. Available tools: {', '.join(available)}")
        else:
            steps.append("3. No skills available")
        
        steps.extend([
            "4. Execute plan with boundary checks",
            "5. Reflect on outcome",
        ])
        
        return steps
    
    def get_status(self) -> Dict[str, Any]:
        """Get cognition status."""
        return {
            "soul_loaded": self.soul._loaded if hasattr(self.soul, '_loaded') else False,
            "memory_connected": self.memory._connected,
            "has_skills": self._skills is not None,
            "has_agents": self._agents is not None,
            "skill_count": len(self._skills.list()) if self._skills else 0,
        }
    
    def __repr__(self):
        return f"<Cognition: soul={self.soul.name}, skills={self._skills is not None}>"
