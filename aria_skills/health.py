# aria_skills/health.py
"""
Health monitoring skill.

Tracks system health, skill status, and generates heartbeats.
"""
import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus
from aria_skills.registry import SkillRegistry


@SkillRegistry.register
class HealthMonitorSkill(BaseSkill):
    """
    System health monitoring.
    
    Config:
        check_interval: Seconds between health checks (default: 300)
        alert_threshold: Consecutive failures before alert (default: 3)
    """
    
    def __init__(self, config: SkillConfig):
        super().__init__(config)
        self._check_interval = config.config.get("check_interval", 300)
        self._alert_threshold = config.config.get("alert_threshold", 3)
        self._registry: Optional["SkillRegistry"] = None
        self._failure_counts: Dict[str, int] = {}
        self._last_check: Optional[datetime] = None
        self._last_results: Dict[str, SkillStatus] = {}
        self._running = False
    
    @property
    def name(self) -> str:
        return "health_monitor"
    
    def set_registry(self, registry: "SkillRegistry") -> None:
        """Inject the skill registry to monitor."""
        self._registry = registry
    
    async def initialize(self) -> bool:
        """Initialize health monitor."""
        self._status = SkillStatus.AVAILABLE
        return True
    
    async def health_check(self) -> SkillStatus:
        """Self health check."""
        return SkillStatus.AVAILABLE
    
    async def check_all_skills(self) -> SkillResult:
        """
        Run health checks on all registered skills.
        
        Returns:
            SkillResult with health status of all skills
        """
        if not self._registry:
            return SkillResult.fail("No registry connected")
        
        results = {}
        alerts = []
        
        for skill_name in self._registry.list():
            try:
                skill = self._registry.get(skill_name)
                if skill:
                    status = await skill.health_check()
                    results[skill_name] = status.value
                    
                    # Track failures
                    if status not in (SkillStatus.AVAILABLE,):
                        self._failure_counts[skill_name] = (
                            self._failure_counts.get(skill_name, 0) + 1
                        )
                        
                        if self._failure_counts[skill_name] >= self._alert_threshold:
                            alerts.append(f"{skill_name}: {status.value} ({self._failure_counts[skill_name]} consecutive)")
                    else:
                        self._failure_counts[skill_name] = 0
                        
            except Exception as e:
                results[skill_name] = f"error: {e}"
                self._failure_counts[skill_name] = self._failure_counts.get(skill_name, 0) + 1
        
        self._last_check = datetime.utcnow()
        self._last_results = {k: SkillStatus(v) if v in [s.value for s in SkillStatus] else SkillStatus.ERROR 
                             for k, v in results.items()}
        
        self._log_usage("check_all_skills", True)
        
        return SkillResult.ok({
            "timestamp": self._last_check.isoformat(),
            "skills": results,
            "alerts": alerts,
            "all_healthy": len(alerts) == 0,
        })
    
    async def get_status_summary(self) -> SkillResult:
        """
        Get a human-readable health summary.
        
        Returns:
            SkillResult with summary text
        """
        if not self._last_results:
            # Run check first
            await self.check_all_skills()
        
        healthy = sum(1 for s in self._last_results.values() if s == SkillStatus.AVAILABLE)
        total = len(self._last_results)
        
        lines = [
            f"# Health Report - {self._last_check.strftime('%Y-%m-%d %H:%M UTC') if self._last_check else 'Never'}",
            f"",
            f"**Overall**: {healthy}/{total} skills healthy",
            f"",
            "| Skill | Status |",
            "|-------|--------|",
        ]
        
        for skill, status in sorted(self._last_results.items()):
            emoji = "✅" if status == SkillStatus.AVAILABLE else "❌"
            lines.append(f"| {skill} | {emoji} {status.value} |")
        
        # Add alerts if any
        if any(c >= self._alert_threshold for c in self._failure_counts.values()):
            lines.extend([
                "",
                "## ⚠️ Alerts",
            ])
            for skill, count in self._failure_counts.items():
                if count >= self._alert_threshold:
                    lines.append(f"- **{skill}**: {count} consecutive failures")
        
        return SkillResult.ok("\n".join(lines))
    
    async def start_monitoring(self) -> None:
        """Start background health monitoring loop."""
        if self._running:
            return
        
        self._running = True
        self.logger.info(f"Starting health monitor (interval: {self._check_interval}s)")
        
        while self._running:
            try:
                await self.check_all_skills()
            except Exception as e:
                self.logger.error(f"Health check cycle failed: {e}")
            
            await asyncio.sleep(self._check_interval)
    
    async def stop_monitoring(self) -> None:
        """Stop background monitoring."""
        self._running = False
        self.logger.info("Health monitor stopped")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get monitoring metrics."""
        base_metrics = super().get_metrics()
        base_metrics.update({
            "last_check": self._last_check.isoformat() if self._last_check else None,
            "failure_counts": self._failure_counts.copy(),
            "skills_monitored": len(self._last_results),
        })
        return base_metrics
