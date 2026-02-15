"""
Skill Health Dashboard - Lightweight metrics aggregation for skill performance.
Stored in working memory for fast access and periodic persistence.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import json

@dataclass
class SkillMetric:
    """Single skill execution metric."""
    skill_name: str
    execution_time_ms: float
    success: bool
    error_type: Optional[str] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill_name": self.skill_name,
            "execution_time_ms": self.execution_time_ms,
            "success": self.success,
            "error_type": self.error_type,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None
        }

@dataclass  
class SkillHealthSnapshot:
    """Aggregated health metrics for a single skill."""
    skill_name: str
    total_calls: int
    success_count: int
    error_count: int
    avg_execution_time_ms: float
    max_execution_time_ms: float
    min_execution_time_ms: float
    error_rate: float
    last_updated: datetime
    recent_errors: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill_name": self.skill_name,
            "total_calls": self.total_calls,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "avg_execution_time_ms": round(self.avg_execution_time_ms, 2),
            "max_execution_time_ms": round(self.max_execution_time_ms, 2),
            "min_execution_time_ms": round(self.min_execution_time_ms, 2),
            "error_rate": round(self.error_rate, 4),
            "last_updated": self.last_updated.isoformat(),
            "recent_errors": self.recent_errors[:5]  # Keep last 5
        }

class SkillHealthDashboard:
    """
    Lightweight skill performance monitoring.
    Aggregates metrics in working memory, persists periodically.
    """
    
    def __init__(self, max_history: int = 1000):
        self.metrics: List[SkillMetric] = []
        self.max_history = max_history
        self._snapshots: Dict[str, SkillHealthSnapshot] = {}
    
    def record_execution(self, skill_name: str, execution_time_ms: float, 
                        success: bool, error_type: Optional[str] = None) -> None:
        """Record a skill execution metric."""
        metric = SkillMetric(
            skill_name=skill_name,
            execution_time_ms=execution_time_ms,
            success=success,
            error_type=error_type
        )
        self.metrics.append(metric)
        
        # Trim old metrics
        if len(self.metrics) > self.max_history:
            self.metrics = self.metrics[-self.max_history:]
        
        # Update snapshot for this skill
        self._update_snapshot(skill_name)
    
    def _update_snapshot(self, skill_name: str) -> None:
        """Recalculate aggregated metrics for a skill."""
        skill_metrics = [m for m in self.metrics if m.skill_name == skill_name]
        
        if not skill_metrics:
            return
        
        total = len(skill_metrics)
        successes = sum(1 for m in skill_metrics if m.success)
        errors = total - successes
        exec_times = [m.execution_time_ms for m in skill_metrics]
        
        recent_errors = [
            m.error_type for m in skill_metrics 
            if not m.success and m.error_type
        ][-5:]
        
        self._snapshots[skill_name] = SkillHealthSnapshot(
            skill_name=skill_name,
            total_calls=total,
            success_count=successes,
            error_count=errors,
            avg_execution_time_ms=sum(exec_times) / len(exec_times),
            max_execution_time_ms=max(exec_times),
            min_execution_time_ms=min(exec_times),
            error_rate=errors / total if total > 0 else 0.0,
            last_updated=datetime.utcnow(),
            recent_errors=recent_errors
        )
    
    def get_snapshot(self, skill_name: str) -> Optional[SkillHealthSnapshot]:
        """Get health snapshot for a specific skill."""
        return self._snapshots.get(skill_name)
    
    def get_all_snapshots(self) -> Dict[str, SkillHealthSnapshot]:
        """Get health snapshots for all skills."""
        return self._snapshots.copy()
    
    def get_unhealthy_skills(self, error_threshold: float = 0.1) -> List[SkillHealthSnapshot]:
        """Get skills with error rate above threshold."""
        return [
            snap for snap in self._snapshots.values()
            if snap.error_rate >= error_threshold
        ]
    
    def get_slow_skills(self, time_threshold_ms: float = 5000) -> List[SkillHealthSnapshot]:
        """Get skills with avg execution time above threshold."""
        return [
            snap for snap in self._snapshots.values()
            if snap.avg_execution_time_ms >= time_threshold_ms
        ]
    
    def to_dict(self) -> Dict[str, Any]:
        """Export dashboard state for working memory storage."""
        return {
            "snapshots": {
                name: snap.to_dict() 
                for name, snap in self._snapshots.items()
            },
            "total_metrics_tracked": len(self.metrics),
            "skills_monitored": len(self._snapshots),
            "unhealthy_count": len(self.get_unhealthy_skills()),
            "slow_count": len(self.get_slow_skills()),
            "generated_at": datetime.utcnow().isoformat()
        }
    
    def summary(self) -> str:
        """Human-readable summary of skill health."""
        lines = [
            f"📊 Skill Health Dashboard",
            f"   Skills monitored: {len(self._snapshots)}",
            f"   Total executions tracked: {len(self.metrics)}",
            f"   Unhealthy skills (error rate ≥10%): {len(self.get_unhealthy_skills())}",
            f"   Slow skills (avg ≥5s): {len(self.get_slow_skills())}",
            ""
        ]
        
        for name, snap in sorted(self._snapshots.items()):
            status = "🟢" if snap.error_rate < 0.1 else "🔴"
            lines.append(
                f"   {status} {name}: {snap.error_rate*100:.1f}% errors, "
                f"{snap.avg_execution_time_ms:.0f}ms avg"
            )
        
        return "\n".join(lines)


# Singleton instance for global access
_dashboard_instance: Optional[SkillHealthDashboard] = None

def get_dashboard() -> SkillHealthDashboard:
    """Get or create the global dashboard instance."""
    global _dashboard_instance
    if _dashboard_instance is None:
        _dashboard_instance = SkillHealthDashboard()
    return _dashboard_instance

def record_skill_execution(skill_name: str, execution_time_ms: float,
                          success: bool, error_type: Optional[str] = None) -> None:
    """Convenience function to record execution via global dashboard."""
    get_dashboard().record_execution(skill_name, execution_time_ms, success, error_type)

def get_skill_health(skill_name: str) -> Optional[SkillHealthSnapshot]:
    """Get health snapshot for a skill."""
    return get_dashboard().get_snapshot(skill_name)

def get_dashboard_summary() -> str:
    """Get human-readable dashboard summary."""
    return get_dashboard().summary()
