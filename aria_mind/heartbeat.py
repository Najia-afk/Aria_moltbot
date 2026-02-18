# aria_mind/heartbeat.py
"""
Heartbeat - Lifecycle, health monitoring, and autonomous action.

More than just a health check — this is Aria's pulse of autonomous behavior.
Every beat is an opportunity to:
- Monitor health and self-heal failing subsystems
- Work on active goals
- Trigger memory consolidation
- Reflect on recent experiences
- Grow confidence through consistent operation
"""
import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from aria_mind import AriaMind


class Heartbeat:
    """
    Aria's heartbeat — keeps her alive, healthy, AND productive.
    
    Responsibilities:
    - Periodic health checks with self-healing
    - Goal progress on every beat
    - Memory consolidation triggers
    - Periodic reflection scheduling
    - Subsystem reconnection on failure
    """
    
    def __init__(self, mind: "AriaMind"):
        self._mind = mind
        self._running = False
        self._task: asyncio.Task | None = None
        self._last_beat: datetime | None = None
        self._beat_count = 0
        self._interval = int(os.environ.get("HEARTBEAT_INTERVAL_SECONDS", "3600"))
        self._health_status: dict[str, Any] = {}
        self.logger = logging.getLogger("aria.heartbeat")
        
        # Self-healing state
        self._consecutive_failures = 0
        self._max_consecutive_failures = 5
        self._subsystem_health: dict[str, bool] = {
            "soul": False,
            "memory": False,
            "cognition": False,
        }
        
        # Autonomous action scheduling (1 beat = 1 hour)
        self._beats_since_reflection = 0
        self._beats_since_consolidation = 0
        self._beats_since_goal_check = 0
        self._reflection_interval = 6      # every 6 beats = 6hr (matches six_hour_review cron)
        self._consolidation_interval = 24  # every 24 beats = 24hr (daily)
        self._goal_check_interval = 1      # every beat = 1hr (matches hourly_goal_check cron)
    
    @property
    def is_healthy(self) -> bool:
        """Check if heartbeat is functioning."""
        if not self._running:
            return False
        
        if self._last_beat is None:
            return False
        
        # Unhealthy if no beat in 2x interval
        elapsed = (datetime.now(timezone.utc) - self._last_beat).total_seconds()
        return elapsed < (self._interval * 2)
    
    async def start(self):
        """Start the heartbeat loop."""
        if self._running:
            return
        
        self._running = True
        self.logger.info("💓 Heartbeat started — Aria is alive")
        
        # Start background task with reference
        self._task = asyncio.create_task(self._beat_loop())
    
    async def stop(self):
        """Stop the heartbeat."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self.logger.info("💔 Heartbeat stopped")
    
    async def _beat_loop(self):
        """Main heartbeat loop with error recovery."""
        while self._running:
            try:
                await self._beat()
                self._consecutive_failures = 0
            except Exception as e:
                self._consecutive_failures += 1
                self.logger.error(
                    f"Beat failed ({self._consecutive_failures}/"
                    f"{self._max_consecutive_failures}): {e}"
                )
                
                # Self-healing: if too many failures, try to recover
                if self._consecutive_failures >= self._max_consecutive_failures:
                    self.logger.warning("⚠️ Too many consecutive failures — attempting self-heal")
                    await self._self_heal()
                    self._consecutive_failures = 0
            
            await asyncio.sleep(self._interval)
    
    async def _beat(self):
        """
        Single heartbeat cycle — monitor + act.
        
        Every beat Aria:
        1. Checks all subsystem health
        2. Attempts self-healing for failed subsystems
        3. Works on goals (every 5 beats)
        4. Triggers reflection (every 30 beats)
        5. Triggers memory consolidation (every 60 beats)
        """
        from aria_mind.logging_config import correlation_id_var, new_correlation_id
        correlation_id_var.set(new_correlation_id())

        self._last_beat = datetime.now(timezone.utc)
        self._beat_count += 1
        
        # 1. Collect health status
        self._subsystem_health = {
            "soul": self._mind.soul is not None and getattr(self._mind.soul, '_loaded', False),
            "memory": self._mind.memory is not None and self._mind.memory._connected,
            "cognition": self._mind.cognition is not None,
        }
        
        self._health_status = {
            "timestamp": self._last_beat.isoformat(),
            "beat_number": self._beat_count,
            "subsystems": dict(self._subsystem_health),
            "all_healthy": all(self._subsystem_health.values()),
        }
        
        # Log to DB via api_client (replaces startup.py raw SQL)
        try:
            from aria_skills.api_client import get_api_client
            api = await get_api_client()
            if api:
                await api.create_activity(
                    action="heartbeat",
                    skill="system",
                    details=self._health_status,
                    success=True,
                )
        except Exception as e:
            self.logger.debug(f"Heartbeat DB log failed: {e}")

        # 2. Self-heal any failed subsystems
        for subsystem, healthy in self._subsystem_health.items():
            if not healthy:
                self.logger.warning(f"⚠️ Subsystem '{subsystem}' unhealthy — attempting recovery")
                await self._heal_subsystem(subsystem)
        
        # 3. Goal work (every 5 beats = 5 min work cycle per GOALS.md)
        self._beats_since_goal_check += 1
        if self._beats_since_goal_check >= self._goal_check_interval:
            self._beats_since_goal_check = 0
            await self._check_goals()
        
        # 4. Periodic reflection (every 30 beats = 30 min)
        self._beats_since_reflection += 1
        if self._beats_since_reflection >= self._reflection_interval:
            self._beats_since_reflection = 0
            await self._trigger_reflection()
        
        # 5. Memory consolidation (every 60 beats = 1 hr)
        self._beats_since_consolidation += 1
        if self._beats_since_consolidation >= self._consolidation_interval:
            self._beats_since_consolidation = 0
            await self._trigger_consolidation()
        
        self.logger.debug(f"💓 Beat #{self._beat_count} — all systems nominal")
    
    async def _heal_subsystem(self, subsystem: str) -> bool:
        """Attempt to reconnect/reload a failed subsystem."""
        try:
            if subsystem == "memory" and self._mind.memory:
                success = await self._mind.memory.connect()
                if success:
                    self.logger.info(f"✅ Memory reconnected")
                return success
                
            elif subsystem == "soul" and self._mind.soul:
                if not getattr(self._mind.soul, '_loaded', False):
                    await self._mind.soul.load()
                    self.logger.info(f"✅ Soul reloaded")
                    return True
                
            elif subsystem == "cognition":
                if self._mind.cognition is None and self._mind.soul and self._mind.memory:
                    from aria_mind.cognition import Cognition
                    self._mind.cognition = Cognition(
                        soul=self._mind.soul,
                        memory=self._mind.memory,
                    )
                    self.logger.info(f"✅ Cognition reconstructed")
                    return True
                    
        except Exception as e:
            self.logger.error(f"Failed to heal {subsystem}: {e}")
        
        return False
    
    async def _self_heal(self) -> None:
        """Emergency self-healing — try to recover all subsystems."""
        self.logger.warning("🔧 Running emergency self-heal cycle...")
        for subsystem in ["memory", "soul", "cognition"]:
            if not self._subsystem_health.get(subsystem, False):
                await self._heal_subsystem(subsystem)
    
    async def _check_goals(self) -> None:
        """Check active goals and work on the top priority."""
        if not self._mind.cognition or not self._mind.cognition._skills:
            return
        
        try:
            goals_skill = self._mind.cognition._skills.get("goals")
            if goals_skill and goals_skill.is_available:
                actions = await goals_skill.get_next_actions(limit=1)
                if actions.success and actions.data:
                    next_action = actions.data
                    if isinstance(next_action, list) and next_action:
                        self.logger.info(f"🎯 Goal work: {str(next_action[0])[:80]}")
        except Exception as e:
            self.logger.debug(f"Goal check skipped: {e}")
    
    async def _trigger_reflection(self) -> None:
        """Trigger a reflection cycle through cognition."""
        if not self._mind.cognition:
            return
        
        try:
            reflection = await self._mind.cognition.reflect()
            self.logger.info(f"🪞 Reflection complete ({len(reflection)} chars)")
        except Exception as e:
            self.logger.debug(f"Reflection skipped: {e}")
    
    async def _trigger_consolidation(self) -> None:
        """Trigger memory consolidation."""
        if not self._mind.memory:
            return
        
        try:
            # Get LLM skill for intelligent consolidation
            llm_skill = None
            if self._mind.cognition and self._mind.cognition._skills:
                llm_skill = (
                    self._mind.cognition._skills.get("litellm")
                    or self._mind.cognition._skills.get("llm")
                )
            
            result = await self._mind.memory.consolidate(llm_skill=llm_skill)
            if result.get("consolidated"):
                self.logger.info(
                    f"🧠 Memory consolidated: {result['entries_processed']} entries, "
                    f"{len(result.get('lessons', []))} lessons learned"
                )
        except Exception as e:
            self.logger.debug(f"Consolidation skipped: {e}")
    
    def get_status(self) -> dict[str, Any]:
        """Get current health status with detailed telemetry."""
        return {
            "running": self._running,
            "healthy": self.is_healthy,
            "last_beat": self._last_beat.isoformat() if self._last_beat else None,
            "beat_count": self._beat_count,
            "consecutive_failures": self._consecutive_failures,
            "subsystems": self._subsystem_health,
            "autonomous_actions": {
                "next_goal_check_in": self._goal_check_interval - self._beats_since_goal_check,
                "next_reflection_in": self._reflection_interval - self._beats_since_reflection,
                "next_consolidation_in": self._consolidation_interval - self._beats_since_consolidation,
            },
            "details": self._health_status,
        }
    
    def __repr__(self):
        status = "healthy" if self.is_healthy else "unhealthy"
        return f"<Heartbeat: {status}, beats={self._beat_count}, failures={self._consecutive_failures}>"
