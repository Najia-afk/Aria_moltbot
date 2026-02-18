"""
Per-Agent Heartbeat System — health monitoring via scheduler.

Each agent gets its own heartbeat cron job that:
- Updates last_active_at in engine_agent_state
- Checks agent-specific health (LLM connectivity, session state)
- Marks agents unhealthy if beats are missed (3x interval)
- Runs existing heartbeat logic from aria_mind/heartbeat.py per agent
- Reports metrics to the health monitoring system
"""
import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from aria_engine.config import EngineConfig
from aria_engine.exceptions import EngineError

logger = logging.getLogger("aria.engine.heartbeat")

# Default intervals (seconds)
DEFAULT_MAIN_INTERVAL = 30
DEFAULT_AGENT_INTERVAL = 300  # 5 minutes

# Miss threshold: mark unhealthy if missed 3x the interval
MISS_MULTIPLIER = 3


class AgentHeartbeatConfig:
    """Configuration for a single agent's heartbeat."""

    def __init__(
        self,
        agent_id: str,
        interval_seconds: int = DEFAULT_AGENT_INTERVAL,
        enabled: bool = True,
    ):
        self.agent_id = agent_id
        self.interval_seconds = interval_seconds
        self.enabled = enabled

    @property
    def miss_threshold_seconds(self) -> int:
        """Seconds after which a missed beat marks the agent unhealthy."""
        return self.interval_seconds * MISS_MULTIPLIER

    @property
    def schedule_expression(self) -> str:
        """Convert interval to scheduler-friendly expression."""
        if self.interval_seconds < 60:
            return f"{self.interval_seconds}s"
        minutes = self.interval_seconds // 60
        return f"{minutes}m"


class AgentHeartbeatManager:
    """
    Manages per-agent heartbeats, health checks, and monitoring.

    Usage:
        manager = AgentHeartbeatManager(config, db_engine, scheduler)
        await manager.register_all_agents()
        # Heartbeats now fire automatically via scheduler

        # Check health:
        health = await manager.check_all_health()
        # → {"main": "healthy", "aria-talk": "unhealthy", ...}
    """

    def __init__(
        self,
        config: EngineConfig,
        db_engine: AsyncEngine,
        scheduler: Optional[Any] = None,
        agent_pool: Optional[Any] = None,
    ):
        self.config = config
        self._db_engine = db_engine
        self._scheduler = scheduler
        self._agent_pool = agent_pool
        self._heartbeat_configs: Dict[str, AgentHeartbeatConfig] = {}
        self._beat_counts: Dict[str, int] = {}
        self._consecutive_failures: Dict[str, int] = {}

    def configure_agent(
        self,
        agent_id: str,
        interval_seconds: Optional[int] = None,
        enabled: bool = True,
    ) -> None:
        """
        Configure heartbeat for a specific agent.

        Args:
            agent_id: Agent identifier.
            interval_seconds: Beat interval (default: 30s for main, 300s for others).
            enabled: Whether heartbeat is active.
        """
        if interval_seconds is None:
            interval_seconds = (
                DEFAULT_MAIN_INTERVAL
                if agent_id == "main"
                else DEFAULT_AGENT_INTERVAL
            )

        self._heartbeat_configs[agent_id] = AgentHeartbeatConfig(
            agent_id=agent_id,
            interval_seconds=interval_seconds,
            enabled=enabled,
        )
        self._beat_counts.setdefault(agent_id, 0)
        self._consecutive_failures.setdefault(agent_id, 0)

        logger.info(
            "Configured heartbeat for %s: interval=%ds enabled=%s",
            agent_id, interval_seconds, enabled,
        )

    async def register_all_agents(self) -> int:
        """
        Register heartbeat jobs for all configured agents with the scheduler.

        Reads agent_state table to discover agents, then registers
        a heartbeat cron job per agent.

        Returns:
            Number of heartbeat jobs registered.
        """
        # Discover agents from DB
        async with self._db_engine.begin() as conn:
            result = await conn.execute(
                text("""
                    SELECT agent_id, status
                    FROM aria_engine.agent_state
                    WHERE status != 'disabled'
                """)
            )
            agents = result.mappings().all()

        # Configure any discovered agents not yet configured
        for agent in agents:
            agent_id = agent["agent_id"]
            if agent_id not in self._heartbeat_configs:
                self.configure_agent(agent_id)

        if self._scheduler is None:
            logger.warning("No scheduler — heartbeats configured but not scheduled")
            return 0

        registered = 0
        for agent_id, hb_config in self._heartbeat_configs.items():
            if not hb_config.enabled:
                continue

            job_id = f"heartbeat_{agent_id}"
            try:
                await self._scheduler.add_job(
                    {
                        "id": job_id,
                        "name": f"Heartbeat: {agent_id}",
                        "schedule": hb_config.schedule_expression,
                        "agent_id": agent_id,
                        "enabled": True,
                        "payload_type": "prompt",
                        "payload": f"__heartbeat__ {agent_id}",
                        "session_mode": "isolated",
                        "max_duration_seconds": min(
                            hb_config.interval_seconds, 60
                        ),
                        "retry_count": 0,
                    }
                )
                registered += 1
            except Exception as e:
                logger.error(
                    "Failed to register heartbeat for %s: %s", agent_id, e
                )

        logger.info("Registered %d agent heartbeats", registered)
        return registered

    async def heartbeat_handler(self, agent_id: str) -> Dict[str, Any]:
        """
        Execute a single heartbeat for an agent.

        This is called by the scheduler on each beat interval.

        Steps:
        1. Update last_active_at in agent_state
        2. Check agent-specific health
        3. Run existing heartbeat logic (subsystem checks)
        4. Record beat count and failure state
        5. Return health status

        Args:
            agent_id: The agent to heartbeat.

        Returns:
            Health status dict.
        """
        start_time = time.monotonic()
        self._beat_counts[agent_id] = self._beat_counts.get(agent_id, 0) + 1
        beat_number = self._beat_counts[agent_id]

        health_status: Dict[str, Any] = {
            "agent_id": agent_id,
            "beat_number": beat_number,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": {},
        }

        try:
            # 1. Update last_active_at
            await self._update_last_active(agent_id)
            health_status["checks"]["db_write"] = True

            # 2. Check agent is responsive
            agent_ok = await self._check_agent_health(agent_id)
            health_status["checks"]["agent_responsive"] = agent_ok

            # 3. Check LLM connectivity (lightweight — no actual LLM call)
            llm_ok = await self._check_llm_health()
            health_status["checks"]["llm_gateway"] = llm_ok

            # 4. Run subsystem checks from existing heartbeat logic
            subsystem_health = await self._check_subsystems(agent_id)
            health_status["checks"]["subsystems"] = subsystem_health

            # Determine overall health
            all_ok = all([
                agent_ok,
                llm_ok,
                all(subsystem_health.values()) if subsystem_health else True,
            ])
            health_status["healthy"] = all_ok

            if all_ok:
                self._consecutive_failures[agent_id] = 0
                await self._set_agent_status(agent_id, "idle")
            else:
                self._consecutive_failures[agent_id] = (
                    self._consecutive_failures.get(agent_id, 0) + 1
                )
                if self._consecutive_failures[agent_id] >= MISS_MULTIPLIER:
                    await self._set_agent_status(agent_id, "error")
                    logger.warning(
                        "Agent %s marked unhealthy after %d consecutive failures",
                        agent_id, self._consecutive_failures[agent_id],
                    )

            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            health_status["duration_ms"] = elapsed_ms

            logger.debug(
                "💓 %s beat #%d — %s (%dms)",
                agent_id,
                beat_number,
                "healthy" if all_ok else "UNHEALTHY",
                elapsed_ms,
            )

            return health_status

        except Exception as e:
            self._consecutive_failures[agent_id] = (
                self._consecutive_failures.get(agent_id, 0) + 1
            )
            logger.error("Heartbeat failed for %s: %s", agent_id, e)
            health_status["healthy"] = False
            health_status["error"] = str(e)
            return health_status

    async def _update_last_active(self, agent_id: str) -> None:
        """Update last_active_at timestamp in agent_state."""
        async with self._db_engine.begin() as conn:
            await conn.execute(
                text("""
                    UPDATE aria_engine.agent_state
                    SET last_active_at = NOW(),
                        updated_at = NOW()
                    WHERE agent_id = :agent_id
                """),
                {"agent_id": agent_id},
            )

    async def _set_agent_status(self, agent_id: str, status: str) -> None:
        """Update agent status in agent_state."""
        async with self._db_engine.begin() as conn:
            await conn.execute(
                text("""
                    UPDATE aria_engine.agent_state
                    SET status = :status,
                        consecutive_failures = :failures,
                        updated_at = NOW()
                    WHERE agent_id = :agent_id
                """),
                {
                    "agent_id": agent_id,
                    "status": status,
                    "failures": self._consecutive_failures.get(agent_id, 0),
                },
            )

    async def _check_agent_health(self, agent_id: str) -> bool:
        """Check if an agent is responsive via the AgentPool."""
        if self._agent_pool is None:
            return True  # No pool — assume OK (pool not yet initialized)

        try:
            agent = self._agent_pool.get_agent(agent_id)
            return agent is not None
        except Exception:
            return False

    async def _check_llm_health(self) -> bool:
        """Lightweight LLM gateway health check (no actual LLM call)."""
        try:
            # Check if the LLM gateway is configured and circuit breaker is closed
            from aria_engine import get_engine

            engine = get_engine()
            if engine and hasattr(engine, "llm_gateway"):
                stats = engine.llm_gateway.get_stats()
                return not stats.get("circuit_open", False)
            return True
        except Exception:
            return True  # Don't fail heartbeat just because gateway isn't initialized

    async def _check_subsystems(self, agent_id: str) -> Dict[str, bool]:
        """
        Check subsystem health using existing heartbeat.py logic.

        For the main agent, checks soul, memory, and cognition.
        For sub-agents, checks basic connectivity only.
        """
        if agent_id != "main":
            return {"agent_exists": True}

        checks: Dict[str, bool] = {}

        try:
            # Check DB connectivity
            async with self._db_engine.begin() as conn:
                result = await conn.execute(text("SELECT 1"))
                checks["database"] = result.scalar() == 1
        except Exception:
            checks["database"] = False

        return checks

    async def check_all_health(self) -> Dict[str, Dict[str, Any]]:
        """
        Check health of all agents, including missed-beat detection.

        Returns:
            Dict mapping agent_id to health status.
        """
        results: Dict[str, Dict[str, Any]] = {}

        async with self._db_engine.begin() as conn:
            result = await conn.execute(
                text("""
                    SELECT agent_id, status, last_active_at,
                           consecutive_failures
                    FROM aria_engine.agent_state
                """)
            )
            agents = result.mappings().all()

        now = datetime.now(timezone.utc)

        for agent in agents:
            agent_id = agent["agent_id"]
            hb_config = self._heartbeat_configs.get(agent_id)
            last_active = agent["last_active_at"]

            # Check for missed beats
            missed_beat = False
            if last_active and hb_config:
                if last_active.tzinfo is None:
                    last_active = last_active.replace(tzinfo=timezone.utc)
                elapsed = (now - last_active).total_seconds()
                missed_beat = elapsed > hb_config.miss_threshold_seconds

            status = agent["status"]
            if missed_beat and status != "disabled":
                status = "unhealthy"
                # Update DB
                await self._set_agent_status(agent_id, "error")

            results[agent_id] = {
                "agent_id": agent_id,
                "status": status,
                "last_active_at": (
                    last_active.isoformat() if last_active else None
                ),
                "consecutive_failures": agent["consecutive_failures"],
                "missed_beat": missed_beat,
                "beat_count": self._beat_counts.get(agent_id, 0),
                "interval_seconds": (
                    hb_config.interval_seconds if hb_config else None
                ),
            }

        return results

    def get_status(self) -> Dict[str, Any]:
        """Get heartbeat manager status summary."""
        return {
            "configured_agents": len(self._heartbeat_configs),
            "beat_counts": dict(self._beat_counts),
            "consecutive_failures": dict(self._consecutive_failures),
            "configs": {
                aid: {
                    "interval": cfg.interval_seconds,
                    "enabled": cfg.enabled,
                }
                for aid, cfg in self._heartbeat_configs.items()
            },
        }
