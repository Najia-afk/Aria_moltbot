# aria_mind/cognition.py
"""
Cognition - Thinking, reasoning, and decision-making.

The cognitive engine that processes inputs and generates responses.
Includes integrated security checks against prompt injection.
"""
import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from aria_mind.soul import Soul
    from aria_mind.memory import MemoryManager
    from aria_skills import SkillRegistry
    from aria_agents import AgentCoordinator

# Import security module (try container path first, then local)
try:
    from security import (
        AriaSecurityGateway,
        OutputFilter,
        ThreatLevel,
        get_security_gateway,
    )
    HAS_SECURITY = True
except ImportError:
    try:
        from aria_mind.security import (
            AriaSecurityGateway,
            OutputFilter,
            ThreatLevel,
            get_security_gateway,
        )
        HAS_SECURITY = True
    except ImportError:
        HAS_SECURITY = False


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
        
        # Initialize security gateway
        self._security: Optional["AriaSecurityGateway"] = None
        if HAS_SECURITY:
            try:
                self._security = get_security_gateway()
                # Attach to soul boundaries for unified protection
                if hasattr(self.soul, 'boundaries'):
                    self.soul.boundaries.set_security_gateway(self._security)
                self.logger.info("🛡️ Security gateway initialized for cognition")
            except Exception as e:
                self.logger.warning(f"Failed to initialize security gateway: {e}")
    
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
        user_id: Optional[str] = None,
    ) -> str:
        """
        Process a prompt and generate a response.
        
        Args:
            prompt: User input or thought
            context: Additional context
            user_id: Optional user identifier for rate limiting
            
        Returns:
            Response string
        """
        context = context or {}
        
        # Step 0: Security check (if available)
        if self._security:
            security_result = self._security.check_input(
                prompt,
                source="cognition",
                user_id=user_id,
                check_rate_limit=bool(user_id),
            )
            if not security_result.allowed:
                self.logger.warning(f"🛡️ Request blocked by security: {security_result.threat_level.value}")
                # Log security event
                await self.memory.log_thought(
                    f"Blocked request (threat: {security_result.threat_level.value}): {prompt[:100]}...",
                    category="security",
                )
                return f"I can't process that request. {security_result.rejection_message}"
            
            # Use sanitized input if available
            if security_result.sanitized_input:
                prompt = security_result.sanitized_input
        
        # Step 1: Check boundaries (legacy - also checked by security gateway)
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
        
        # Step 5: Filter output for sensitive data (if security available)
        if self._security and HAS_SECURITY:
            result = OutputFilter.filter_output(result)
        
        # Step 6: Log thought
        await self.memory.log_thought(f"Responded to: {prompt[:50]}...")
        
        return result
    
    async def _fallback_process(
        self,
        prompt: str,
        context: Dict[str, Any],
    ) -> str:
        """
        Fallback processing without agents.
        
        Respects models.yaml priority: local → free → paid.
        Uses litellm router which handles model selection internally.
        """
        if self._skills:
            # Use LiteLLM router (handles model priority per models.yaml)
            llm = self._skills.get("litellm") or self._skills.get("llm")
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
