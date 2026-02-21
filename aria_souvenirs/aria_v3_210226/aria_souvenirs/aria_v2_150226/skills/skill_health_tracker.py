"""
Skill Health Tracker - Lightweight monitoring for skill performance
Tracks: execution times, error rates, API token usage per skill
"""
import time
import json
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional
from pathlib import Path

@dataclass
class SkillExecution:
    skill_name: str
    function: str
    start_time: float
    end_time: Optional[float] = None
    tokens_used: int = 0
    error: Optional[str] = None
    
    @property
    def duration_ms(self) -> float:
        if self.end_time is None:
            return 0.0
        return (self.end_time - self.start_time) * 1000
    
    @property
    def success(self) -> bool:
        return self.error is None

@dataclass
class SkillMetrics:
    skill_name: str
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_duration_ms: float = 0.0
    total_tokens: int = 0
    last_executed: Optional[str] = None
    error_history: List[str] = field(default_factory=list)
    
    @property
    def avg_duration_ms(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.total_duration_ms / self.total_calls
    
    @property
    def error_rate(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.failed_calls / self.total_calls
    
    @property
    def health_score(self) -> float:
        """0-100 health score based on error rate and performance"""
        if self.total_calls == 0:
            return 100.0
        error_penalty = self.error_rate * 50  # Max 50 points lost from errors
        return max(0.0, 100.0 - error_penalty)

class SkillHealthTracker:
    """Track and aggregate skill health metrics"""
    
    def __init__(self, storage_path: Optional[Path] = None):
        self._executions: List[SkillExecution] = []
        self._metrics: Dict[str, SkillMetrics] = {}
        self._storage_path = storage_path or Path("/root/.openclaw/aria_memories/skills/metrics.json")
        self._load_metrics()
    
    def start_execution(self, skill_name: str, function: str) -> SkillExecution:
        """Start tracking a skill execution"""
        execution = SkillExecution(
            skill_name=skill_name,
            function=function,
            start_time=time.time()
        )
        self._executions.append(execution)
        return execution
    
    def end_execution(self, execution: SkillExecution, tokens: int = 0, error: Optional[str] = None):
        """Complete tracking for an execution"""
        execution.end_time = time.time()
        execution.tokens_used = tokens
        execution.error = error
        self._update_metrics(execution)
        self._save_metrics()
    
    def _update_metrics(self, execution: SkillExecution):
        """Update aggregated metrics from execution"""
        if execution.skill_name not in self._metrics:
            self._metrics[execution.skill_name] = SkillMetrics(skill_name=execution.skill_name)
        
        metrics = self._metrics[execution.skill_name]
        metrics.total_calls += 1
        metrics.total_duration_ms += execution.duration_ms
        metrics.total_tokens += execution.tokens_used
        metrics.last_executed = datetime.utcnow().isoformat()
        
        if execution.success:
            metrics.successful_calls += 1
        else:
            metrics.failed_calls += 1
            if execution.error and len(metrics.error_history) < 10:
                metrics.error_history.append(execution.error)
    
    def get_skill_health(self, skill_name: str) -> Optional[SkillMetrics]:
        """Get health metrics for a specific skill"""
        return self._metrics.get(skill_name)
    
    def get_all_health(self) -> Dict[str, dict]:
        """Get health metrics for all skills"""
        return {
            name: asdict(metrics) 
            for name, metrics in self._metrics.items()
        }
    
    def get_dashboard_summary(self) -> dict:
        """Get a summary view for dashboard display"""
        if not self._metrics:
            return {"status": "no_data", "skills": []}
        
        skills = []
        total_calls = 0
        total_errors = 0
        
        for name, metrics in self._metrics.items():
            total_calls += metrics.total_calls
            total_errors += metrics.failed_calls
            skills.append({
                "name": name,
                "health_score": round(metrics.health_score, 1),
                "error_rate": round(metrics.error_rate * 100, 2),
                "avg_duration_ms": round(metrics.avg_duration_ms, 2),
                "total_calls": metrics.total_calls,
                "status": "healthy" if metrics.error_rate < 0.1 else "degraded" if metrics.error_rate < 0.3 else "unhealthy"
            })
        
        # Sort by health score ascending (worst first)
        skills.sort(key=lambda s: s["health_score"])
        
        return {
            "status": "ok",
            "overall_health": round(sum(s["health_score"] for s in skills) / len(skills), 1) if skills else 100.0,
            "total_calls": total_calls,
            "total_errors": total_errors,
            "skills_count": len(skills),
            "skills": skills[:10]  # Top 10 for dashboard
        }
    
    def _save_metrics(self):
        """Persist metrics to storage"""
        try:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "updated_at": datetime.utcnow().isoformat(),
                "metrics": self.get_all_health()
            }
            with open(self._storage_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Failed to save metrics: {e}")
    
    def _load_metrics(self):
        """Load metrics from storage"""
        try:
            if self._storage_path.exists():
                with open(self._storage_path, 'r') as f:
                    data = json.load(f)
                for name, m in data.get("metrics", {}).items():
                    self._metrics[name] = SkillMetrics(**m)
        except Exception as e:
            print(f"Failed to load metrics: {e}")

# Global instance for use across skills
tracker = SkillHealthTracker()

if __name__ == "__main__":
    # Demo/test
    print(tracker.get_dashboard_summary())
