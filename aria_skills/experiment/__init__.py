# aria_skills/experiment.py
"""
🧪 Experiment Tracking Skill - ML/Research Focus

Provides experiment tracking and management for Aria's Research persona.
Handles experiment lifecycle, metrics, and comparisons.
"""
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus
from aria_skills.registry import SkillRegistry


@dataclass
class Metric:
    """A tracked metric."""
    name: str
    value: float
    step: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Experiment:
    """An experiment run."""
    id: str
    name: str
    hypothesis: str
    parameters: dict
    metrics: list[Metric] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    status: str = "running"  # running, completed, failed
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ended_at: Optional[datetime] = None
    tags: list[str] = field(default_factory=list)


@SkillRegistry.register
class ExperimentSkill(BaseSkill):
    """
    Experiment tracking and management.
    
    Capabilities:
    - Experiment lifecycle management
    - Metric logging and comparison
    - Parameter tracking
    - Artifact management
    """
    
    @property
    def name(self) -> str:
        return "experiment"
    
    async def initialize(self) -> bool:
        """Initialize experiment skill."""
        # TODO: TICKET-12 - stub requires API endpoint for experiment persistence.
        # Currently in-memory only. Needs POST/GET /api/experiments endpoints.
        self.logger.warning("experiment skill is in-memory only — API endpoint not yet available")
        self._experiments: dict[str, Experiment] = {}
        self._status = SkillStatus.AVAILABLE
        self.logger.info("🧪 Experiment skill initialized")
        return True
    
    async def health_check(self) -> SkillStatus:
        """Check experiment skill availability."""
        return self._status
    
    async def start_experiment(
        self,
        name: str,
        hypothesis: str,
        parameters: dict,
        tags: Optional[list[str]] = None
    ) -> SkillResult:
        """
        Start a new experiment.
        
        Args:
            name: Experiment name
            hypothesis: What you're testing
            parameters: Experiment parameters/config
            tags: Optional tags for categorization
            
        Returns:
            SkillResult with experiment ID
        """
        try:
            # Generate unique ID from name and timestamp
            exp_hash = hashlib.md5(f"{name}{datetime.now(timezone.utc).isoformat()}".encode()).hexdigest()[:8]
            exp_id = f"exp_{exp_hash}"
            
            experiment = Experiment(
                id=exp_id,
                name=name,
                hypothesis=hypothesis,
                parameters=parameters,
                tags=tags or []
            )
            
            self._experiments[exp_id] = experiment
            
            return SkillResult.ok({
                "experiment_id": exp_id,
                "name": name,
                "hypothesis": hypothesis,
                "parameters": parameters,
                "status": experiment.status,
                "started_at": experiment.started_at.isoformat()
            })
            
        except Exception as e:
            return SkillResult.fail(f"Experiment start failed: {str(e)}")
    
    async def log_metric(
        self,
        experiment_id: str,
        name: str,
        value: float,
        step: Optional[int] = None
    ) -> SkillResult:
        """
        Log a metric to an experiment.
        
        Args:
            experiment_id: Target experiment
            name: Metric name
            value: Metric value
            step: Optional step/epoch number
            
        Returns:
            SkillResult confirming metric logged
        """
        try:
            if experiment_id not in self._experiments:
                return SkillResult.fail(f"Experiment not found: {experiment_id}")
            
            exp = self._experiments[experiment_id]
            
            if exp.status != "running":
                return SkillResult.fail(f"Experiment is {exp.status}, cannot log metrics")
            
            # Auto-increment step if not provided
            if step is None:
                existing_steps = [m.step for m in exp.metrics if m.name == name]
                step = max(existing_steps, default=-1) + 1
            
            metric = Metric(name=name, value=value, step=step)
            exp.metrics.append(metric)
            
            return SkillResult.ok({
                "experiment_id": experiment_id,
                "metric": name,
                "value": value,
                "step": step,
                "total_metrics": len(exp.metrics)
            })
            
        except Exception as e:
            return SkillResult.fail(f"Metric logging failed: {str(e)}")
    
    async def log_metrics(
        self,
        experiment_id: str,
        metrics: dict[str, float],
        step: Optional[int] = None
    ) -> SkillResult:
        """
        Log multiple metrics at once.
        
        Args:
            experiment_id: Target experiment
            metrics: Dict of metric_name: value
            step: Optional step/epoch number
            
        Returns:
            SkillResult confirming metrics logged
        """
        try:
            results = []
            for name, value in metrics.items():
                result = await self.log_metric(experiment_id, name, value, step)
                if not result.success:
                    return result
                results.append({"name": name, "value": value})
            
            return SkillResult.ok({
                "experiment_id": experiment_id,
                "metrics_logged": results,
                "count": len(results)
            })
            
        except Exception as e:
            return SkillResult.fail(f"Batch metric logging failed: {str(e)}")
    
    async def add_artifact(
        self,
        experiment_id: str,
        artifact_path: str
    ) -> SkillResult:
        """
        Register an artifact with an experiment.
        
        Args:
            experiment_id: Target experiment
            artifact_path: Path or identifier of artifact
            
        Returns:
            SkillResult confirming artifact added
        """
        try:
            if experiment_id not in self._experiments:
                return SkillResult.fail(f"Experiment not found: {experiment_id}")
            
            exp = self._experiments[experiment_id]
            exp.artifacts.append(artifact_path)
            
            return SkillResult.ok({
                "experiment_id": experiment_id,
                "artifact": artifact_path,
                "total_artifacts": len(exp.artifacts)
            })
            
        except Exception as e:
            return SkillResult.fail(f"Artifact registration failed: {str(e)}")
    
    async def end_experiment(
        self,
        experiment_id: str,
        status: str = "completed",
        summary: Optional[str] = None
    ) -> SkillResult:
        """
        End an experiment.
        
        Args:
            experiment_id: Target experiment
            status: Final status (completed, failed)
            summary: Optional summary of findings
            
        Returns:
            SkillResult with experiment summary
        """
        try:
            if experiment_id not in self._experiments:
                return SkillResult.fail(f"Experiment not found: {experiment_id}")
            
            exp = self._experiments[experiment_id]
            exp.status = status
            exp.ended_at = datetime.now(timezone.utc)
            
            # Calculate metric summaries
            metric_names = set(m.name for m in exp.metrics)
            metric_summaries = {}
            
            for name in metric_names:
                values = [m.value for m in exp.metrics if m.name == name]
                metric_summaries[name] = {
                    "count": len(values),
                    "min": min(values),
                    "max": max(values),
                    "last": values[-1] if values else None
                }
            
            duration = (exp.ended_at - exp.started_at).total_seconds()
            
            return SkillResult.ok({
                "experiment_id": experiment_id,
                "name": exp.name,
                "status": status,
                "hypothesis": exp.hypothesis,
                "parameters": exp.parameters,
                "metric_summaries": metric_summaries,
                "total_metrics": len(exp.metrics),
                "artifacts": exp.artifacts,
                "duration_seconds": duration,
                "summary": summary,
                "started_at": exp.started_at.isoformat(),
                "ended_at": exp.ended_at.isoformat()
            })
            
        except Exception as e:
            return SkillResult.fail(f"Experiment end failed: {str(e)}")
    
    async def get_experiment(self, experiment_id: str) -> SkillResult:
        """
        Get experiment details.
        
        Args:
            experiment_id: Target experiment
            
        Returns:
            SkillResult with experiment details
        """
        try:
            if experiment_id not in self._experiments:
                return SkillResult.fail(f"Experiment not found: {experiment_id}")
            
            exp = self._experiments[experiment_id]
            
            return SkillResult.ok({
                "experiment_id": exp.id,
                "name": exp.name,
                "hypothesis": exp.hypothesis,
                "parameters": exp.parameters,
                "status": exp.status,
                "metrics_count": len(exp.metrics),
                "artifacts": exp.artifacts,
                "tags": exp.tags,
                "started_at": exp.started_at.isoformat(),
                "ended_at": exp.ended_at.isoformat() if exp.ended_at else None
            })
            
        except Exception as e:
            return SkillResult.fail(f"Get experiment failed: {str(e)}")
    
    async def compare_experiments(
        self,
        experiment_ids: list[str],
        metric_name: Optional[str] = None
    ) -> SkillResult:
        """
        Compare multiple experiments.
        
        Args:
            experiment_ids: List of experiments to compare
            metric_name: Specific metric to compare (or all)
            
        Returns:
            SkillResult with comparison
        """
        try:
            comparisons = []
            
            for exp_id in experiment_ids:
                if exp_id not in self._experiments:
                    continue
                
                exp = self._experiments[exp_id]
                
                metrics = {}
                if metric_name:
                    values = [m.value for m in exp.metrics if m.name == metric_name]
                    if values:
                        metrics[metric_name] = {
                            "last": values[-1],
                            "best": max(values)
                        }
                else:
                    for name in set(m.name for m in exp.metrics):
                        values = [m.value for m in exp.metrics if m.name == name]
                        metrics[name] = {
                            "last": values[-1] if values else None,
                            "best": max(values) if values else None
                        }
                
                comparisons.append({
                    "experiment_id": exp_id,
                    "name": exp.name,
                    "status": exp.status,
                    "parameters": exp.parameters,
                    "metrics": metrics
                })
            
            # Find best if comparing specific metric
            best = None
            if metric_name and comparisons:
                valid = [c for c in comparisons if metric_name in c["metrics"]]
                if valid:
                    best = max(valid, key=lambda x: x["metrics"][metric_name]["best"])
            
            return SkillResult.ok({
                "compared": len(comparisons),
                "metric_focused": metric_name,
                "experiments": comparisons,
                "best_performer": best["experiment_id"] if best else None
            })
            
        except Exception as e:
            return SkillResult.fail(f"Comparison failed: {str(e)}")
    
    async def list_experiments(
        self,
        status: Optional[str] = None,
        tag: Optional[str] = None
    ) -> SkillResult:
        """
        List all experiments.
        
        Args:
            status: Filter by status
            tag: Filter by tag
            
        Returns:
            SkillResult with experiment list
        """
        try:
            experiments = []
            
            for exp in self._experiments.values():
                # Apply filters
                if status and exp.status != status:
                    continue
                if tag and tag not in exp.tags:
                    continue
                
                experiments.append({
                    "experiment_id": exp.id,
                    "name": exp.name,
                    "status": exp.status,
                    "metrics_count": len(exp.metrics),
                    "started_at": exp.started_at.isoformat()
                })
            
            # Sort by start time
            experiments.sort(key=lambda x: x["started_at"], reverse=True)
            
            return SkillResult.ok({
                "total": len(experiments),
                "filters": {"status": status, "tag": tag},
                "experiments": experiments
            })
            
        except Exception as e:
            return SkillResult.fail(f"List experiments failed: {str(e)}")


# Skill instance factory
def create_skill(config: SkillConfig) -> ExperimentSkill:
    """Create an experiment skill instance."""
    return ExperimentSkill(config)
