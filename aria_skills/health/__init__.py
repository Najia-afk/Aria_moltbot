# aria_skills/health/__init__.py
"""
System health monitoring skill.

Checks Aria's internal systems and reports health status.
Includes self-diagnostic & auto-recovery (TICKET-36).
"""
import asyncio
import os
import sys
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus, logged_method
from aria_skills.latency import log_latency
from aria_skills.registry import SkillRegistry


# ─────────────────────────────────────────────────────────────────────────────
# S-45 Phase 4 — Health Degradation Levels
# ─────────────────────────────────────────────────────────────────────────────

class HealthDegradationLevel(str, Enum):
    """System-wide health degradation tiers used to suspend non-critical crons."""
    HEALTHY  = "healthy"   # All subsystems nominal
    DEGRADED = "degraded"  # 1–2 subsystems failing — core ops continue
    CRITICAL = "critical"  # 3+ subsystems failing — emergency mode
    RECOVERY = "recovery"  # Active recovery cycle running

# Cron jobs suspended at each degradation level (higher levels inherit lower)
_SUSPENDED_JOBS_BY_LEVEL: dict[str, list[str]] = {
    HealthDegradationLevel.DEGRADED: ["moltbook_check", "social_post"],
    HealthDegradationLevel.CRITICAL: [
        "moltbook_check", "social_post",
        "research_cycle", "brainstorm",
        "goal_check",     "agent_audit",
    ],
    # RECOVERY: only health_check and heartbeat continue
}

# TICKET-36: Self-diagnostic & auto-recovery exports
from aria_skills.health.diagnostics import HealthSignal, HealthLedger, Severity
from aria_skills.health.playbooks import (
    Playbook,
    RESTART_SERVICE,
    CLEAR_CACHE,
    REDUCE_LOAD,
    MODEL_FALLBACK,
    DATABASE_RECOVERY,
    ALL_PLAYBOOKS,
)
from aria_skills.health.recovery import RecoveryExecutor, RecoveryAction
from aria_skills.health.patterns import FailurePatternStore, FailureRecord

__all__ = [
    # Existing
    "HealthMonitorSkill",
    # S-45: Degradation levels
    "HealthDegradationLevel",
    # TICKET-36: Diagnostics
    "HealthSignal",
    "HealthLedger",
    "Severity",
    # TICKET-36: Playbooks
    "Playbook",
    "RESTART_SERVICE",
    "CLEAR_CACHE",
    "REDUCE_LOAD",
    "MODEL_FALLBACK",
    "DATABASE_RECOVERY",
    "ALL_PLAYBOOKS",
    # TICKET-36: Recovery
    "RecoveryExecutor",
    "RecoveryAction",
    # TICKET-36: Patterns
    "FailurePatternStore",
    "FailureRecord",
]


@SkillRegistry.register
class HealthMonitorSkill(BaseSkill):
    """
    System health monitoring.
    
    Provides comprehensive health checks for Aria's subsystems.
    """
    
    def __init__(self, config: SkillConfig):
        super().__init__(config)
        self._last_check: datetime | None = None
        self._check_results: dict[str, Any] = {}
    
    @property
    def name(self) -> str:
        return "health"
    
    async def initialize(self) -> bool:
        """Initialize health monitor."""
        self._status = SkillStatus.AVAILABLE
        self.logger.info("Health monitor initialized")
        return True
    
    async def health_check(self, **kwargs) -> SkillStatus:
        """Check own health (meta!)."""
        return self._status
    
    @log_latency
    @logged_method()
    async def check_system(self, **kwargs) -> SkillResult:
        """
        Run comprehensive system health check.
        
        Returns:
            SkillResult with health status for all subsystems
        """
        checks = {
            "python": await self._check_python(),
            "memory": await self._check_memory(),
            "disk": await self._check_disk(),
            "network": await self._check_network(),
            "environment": await self._check_environment(),
        }
        
        self._last_check = datetime.now(timezone.utc)
        self._check_results = checks
        
        # Determine overall health
        statuses = [c.get("status", "unknown") for c in checks.values()]
        if all(s == "healthy" for s in statuses):
            overall = "healthy"
        elif any(s == "critical" for s in statuses):
            overall = "critical"
        elif any(s == "warning" for s in statuses):
            overall = "warning"
        else:
            overall = "unknown"
        
        return SkillResult.ok({
            "overall_status": overall,
            "timestamp": self._last_check.isoformat(),
            "checks": checks,
        })
    
    async def _check_python(self) -> dict[str, Any]:
        """Check Python runtime."""
        return {
            "status": "healthy",
            "version": sys.version,
            "executable": sys.executable,
            "platform": sys.platform,
        }
    
    async def _check_memory(self) -> dict[str, Any]:
        """Check memory usage."""
        try:
            import psutil
            mem = psutil.virtual_memory()
            
            status = "healthy"
            if mem.percent > 90:
                status = "critical"
            elif mem.percent > 75:
                status = "warning"
            
            return {
                "status": status,
                "total_gb": round(mem.total / (1024**3), 2),
                "available_gb": round(mem.available / (1024**3), 2),
                "percent_used": mem.percent,
            }
        except ImportError:
            return {"status": "unknown", "message": "psutil not installed"}
    
    async def _check_disk(self) -> dict[str, Any]:
        """Check disk space."""
        try:
            import psutil
            disk = psutil.disk_usage("/")
            
            status = "healthy"
            if disk.percent > 95:
                status = "critical"
            elif disk.percent > 80:
                status = "warning"
            
            return {
                "status": status,
                "total_gb": round(disk.total / (1024**3), 2),
                "free_gb": round(disk.free / (1024**3), 2),
                "percent_used": disk.percent,
            }
        except ImportError:
            return {"status": "unknown", "message": "psutil not installed"}
    
    async def _check_network(self) -> dict[str, Any]:
        """Check network connectivity."""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get("https://httpbin.org/ip", timeout=5) as resp:
                    if resp.status == 200:
                        return {"status": "healthy", "external_ip": (await resp.json()).get("origin")}
            return {"status": "warning", "message": "Network check failed"}
        except ImportError:
            return {"status": "unknown", "message": "aiohttp not installed"}
        except Exception as e:
            return {"status": "warning", "message": str(e)}
    
    async def _check_environment(self) -> dict[str, Any]:
        """Check environment variables."""
        required_vars = ["HOME", "PATH"]
        missing = [v for v in required_vars if not os.environ.get(v)]
        
        return {
            "status": "healthy" if not missing else "warning",
            "missing_vars": missing,
            "aria_vars": {
                k: "set" for k, v in os.environ.items() 
                if k.startswith("ARIA_")
            },
        }
    
    async def get_last_check(self) -> SkillResult:
        """Get results of last health check."""
        if not self._last_check:
            return SkillResult.fail("No health check has been run yet")
        
        return SkillResult.ok({
            "timestamp": self._last_check.isoformat(),
            "checks": self._check_results,
        })

    # ─────────────────────────────────────────────────────────────────────────
    # S-45 Phase 4 — Degradation level detection & enforcement
    # ─────────────────────────────────────────────────────────────────────────

    async def check_degradation_level(self) -> SkillResult:
        """
        Evaluate current degradation level based on last health check results.

        Returns SkillResult.ok({"level": ..., "failing_subsystems": [...], ...}).
        Triggers check_system() if no prior check has run.
        """
        if not self._check_results:
            await self.check_system()

        failing = [
            name for name, info in self._check_results.items()
            if info.get("status") not in ("healthy", "unknown")
        ]
        n = len(failing)

        if n == 0:
            level = HealthDegradationLevel.HEALTHY
        elif n <= 2:
            level = HealthDegradationLevel.DEGRADED
        else:
            level = HealthDegradationLevel.CRITICAL

        return SkillResult.ok({
            "level": level.value,
            "failing_count": n,
            "failing_subsystems": failing,
            "suspended_jobs": _SUSPENDED_JOBS_BY_LEVEL.get(level, []),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    async def apply_degradation_mode(
        self, level: HealthDegradationLevel | str
    ) -> SkillResult:
        """
        Report which cron jobs should be suspended at the given degradation level.

        Does NOT directly modify the scheduler — returns a structured plan that
        the cron orchestrator or work_cycle can act on.

        Args:
            level: HealthDegradationLevel enum value or its string representation.

        Returns:
            SkillResult.ok({
                "level": ...,
                "suspend": [...],   # job names to pause
                "continue": [...],  # job names that must keep running
                "action": "..."     # human-readable summary
            })
        """
        if isinstance(level, str):
            try:
                level = HealthDegradationLevel(level)
            except ValueError:
                return SkillResult.fail(f"Unknown degradation level: '{level}'")

        suspend = _SUSPENDED_JOBS_BY_LEVEL.get(level, [])
        always_running = ["health_check", "heartbeat", "work_cycle"]
        cont = [j for j in always_running if j not in suspend]

        action_map = {
            HealthDegradationLevel.HEALTHY:  "All systems nominal — no suspensions.",
            HealthDegradationLevel.DEGRADED: (
                "Non-critical crons suspended. Core ops (work_cycle, heartbeat) continue."
            ),
            HealthDegradationLevel.CRITICAL: (
                "Emergency mode. Most crons suspended. Only health_check and heartbeat running. "
                "Alert Najia via fallback channel."
            ),
            HealthDegradationLevel.RECOVERY: (
                "Recovery cycle active. All crons paused except health_check."
            ),
        }

        self.logger.warning(
            "Degradation mode applied: level=%s, suspended=%s", level.value, suspend
        )

        return SkillResult.ok({
            "level": level.value,
            "suspend": suspend,
            "continue": cont,
            "action": action_map.get(level, "Unknown degradation level"),
        })

    async def check_all_subsystems(self) -> list[dict[str, Any]]:
        """Return a flat list of subsystem health dicts (for degradation counting)."""
        await self.check_system()
        return [
            {"name": k, **v}
            for k, v in self._check_results.items()
        ]
