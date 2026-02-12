"""Experiment skill — lightweight in-memory ML experiment tracking."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus
from aria_skills.registry import SkillRegistry


@SkillRegistry.register
class ExperimentSkill(BaseSkill):
    def __init__(self, config: SkillConfig):
        super().__init__(config)
        self._experiments: dict[str, dict] = {}
        self._models: dict[str, list[dict]] = {}

    @property
    def name(self) -> str:
        return "experiment"

    async def initialize(self) -> bool:
        self._status = SkillStatus.AVAILABLE
        return True

    async def health_check(self) -> SkillStatus:
        return self._status

    async def create_experiment(self, name: str, parameters: dict, tags: list[str] | None = None) -> SkillResult:
        experiment_id = f"exp-{uuid.uuid4().hex[:10]}"
        obj = {
            "experiment_id": experiment_id,
            "name": name,
            "parameters": parameters,
            "tags": tags or [],
            "status": "running",
            "metrics": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._experiments[experiment_id] = obj
        return SkillResult.ok(obj)

    async def log_metrics(self, experiment_id: str, metrics: dict, step: int | None = None) -> SkillResult:
        exp = self._experiments.get(experiment_id)
        if not exp:
            return SkillResult.fail(f"Experiment not found: {experiment_id}")
        point = {"step": step, "metrics": metrics, "at": datetime.now(timezone.utc).isoformat()}
        exp["metrics"].append(point)
        return SkillResult.ok({"experiment_id": experiment_id, "logged": point})

    async def complete_experiment(self, experiment_id: str, status: str = "completed") -> SkillResult:
        exp = self._experiments.get(experiment_id)
        if not exp:
            return SkillResult.fail(f"Experiment not found: {experiment_id}")
        exp["status"] = status
        exp["completed_at"] = datetime.now(timezone.utc).isoformat()
        return SkillResult.ok(exp)

    async def compare_experiments(self, experiment_ids: list[str], metrics: list[str] | None = None) -> SkillResult:
        rows = []
        for eid in experiment_ids:
            exp = self._experiments.get(eid)
            if not exp:
                continue
            latest = exp.get("metrics", [])[-1]["metrics"] if exp.get("metrics") else {}
            if metrics:
                latest = {k: latest.get(k) for k in metrics}
            rows.append({"experiment_id": eid, "name": exp.get("name"), "status": exp.get("status"), "latest_metrics": latest})
        return SkillResult.ok({"comparisons": rows})

    async def register_model(self, name: str, experiment_id: str, metrics: dict, path: str | None = None) -> SkillResult:
        version = len(self._models.get(name, [])) + 1
        model = {
            "name": name,
            "version": version,
            "experiment_id": experiment_id,
            "metrics": metrics,
            "path": path,
            "stage": "development",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._models.setdefault(name, []).append(model)
        return SkillResult.ok(model)

    async def promote_model(self, name: str, version: int, stage: str) -> SkillResult:
        entries = self._models.get(name, [])
        for model in entries:
            if model.get("version") == version:
                model["stage"] = stage
                model["promoted_at"] = datetime.now(timezone.utc).isoformat()
                return SkillResult.ok(model)
        return SkillResult.fail(f"Model not found: {name} v{version}")
