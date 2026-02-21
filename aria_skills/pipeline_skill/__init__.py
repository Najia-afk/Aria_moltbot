# aria_skills/pipeline_skill/__init__.py
"""
Pipeline Skill — exposes the Cognitive Pipeline Engine as a first-class skill.

Allows Aria to:
- Run named pipeline definitions (from YAML or ad-hoc)
- List available pipeline definitions
- Query the status of a running / completed pipeline
"""
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus, logged_method
from aria_skills.pipeline import Pipeline, PipelineResult, PipelineStep, StepStatus
from aria_skills.pipeline_executor import PipelineExecutor
from aria_skills.registry import SkillRegistry

logger = logging.getLogger("aria.skills.pipeline")

# Default directory for YAML pipeline definitions
_PIPELINES_DIR = Path(__file__).resolve().parent.parent / "pipelines"


def _load_pipeline_from_yaml(path: Path) -> Pipeline:
    """Parse a YAML file into a :class:`Pipeline`."""
    data = yaml.safe_load(path.read_text())
    steps: list[PipelineStep] = []
    for s in data.get("steps", []):
        steps.append(
            PipelineStep(
                name=s["name"],
                skill=s["skill"],
                method=s["method"],
                params=s.get("params", {}),
                depends_on=s.get("depends_on", []),
                condition=s.get("condition"),
                on_failure=s.get("on_failure", "stop"),
                timeout_seconds=s.get("timeout_seconds", 120),
            )
        )
    return Pipeline(name=data.get("name", path.stem), steps=steps)


@SkillRegistry.register
class PipelineSkill(BaseSkill):
    """
    Cognitive Pipeline Engine skill.

    Provides methods to run, list, and inspect multi-step skill pipelines.
    """

    def __init__(self, config: SkillConfig):
        super().__init__(config)
        self._pipelines_dir: Path = _PIPELINES_DIR
        self._history: dict[str, PipelineResult] = {}
        self._executor: PipelineExecutor | None = None
        self._registry: SkillRegistry | None = None

    @property
    def name(self) -> str:
        return "pipeline"

    async def initialize(self, registry: SkillRegistry | None = None) -> bool:
        """Initialize the pipeline skill and its executor.

        Args:
            registry: An existing SkillRegistry with live skills.  If *None*,
                      a new **empty** registry is created (with a warning).
        """
        if registry is not None:
            self._registry = registry
        else:
            logger.warning(
                "PipelineSkill.initialize() called without a registry — "
                "creating an empty SkillRegistry. Pipelines will not be able "
                "to invoke other skills."
            )
            self._registry = SkillRegistry()
        self._executor = PipelineExecutor(self._registry)
        self._status = SkillStatus.AVAILABLE
        self.logger.info("Pipeline skill initialized (pipelines_dir=%s)", self._pipelines_dir)
        return True

    async def health_check(self) -> SkillStatus:
        """Pipeline engine is healthy if the executor is set."""
        if self._executor is not None:
            self._status = SkillStatus.AVAILABLE
        else:
            self._status = SkillStatus.UNAVAILABLE
        return self._status

    # ── Public methods ──────────────────────────────────────────────────

    @logged_method()
    async def run_pipeline(
        self, name: str, context: dict | None = None
    ) -> SkillResult:
        """
        Execute a named pipeline.

        Looks for ``<name>.yaml`` inside the pipelines directory, builds
        a Pipeline object, and runs it through the executor.

        Args:
            name: Pipeline name (matches the YAML filename without extension).
            context: Optional initial context dict injected into the pipeline.

        Returns:
            SkillResult wrapping a PipelineResult on success.
        """
        if self._executor is None:
            return SkillResult.fail("Pipeline executor not initialised")

        yaml_path = self._pipelines_dir / f"{name}.yaml"
        if not yaml_path.exists():
            return SkillResult.fail(f"Pipeline definition not found: {name}")

        try:
            pipeline = _load_pipeline_from_yaml(yaml_path)
        except Exception as exc:
            return SkillResult.fail(f"Failed to parse pipeline YAML: {exc}")

        if context:
            pipeline.context.update(context)

        pipeline_id = str(uuid.uuid4())[:8]
        logger.info("Running pipeline '%s' (id=%s)", name, pipeline_id)

        result: PipelineResult = await self._executor.execute(pipeline)
        self._history[pipeline_id] = result

        if result.status == StepStatus.SUCCESS:
            return SkillResult.ok({
                "pipeline_id": pipeline_id,
                "status": result.status.value,
                "step_results": result.step_results,
                "total_duration_ms": result.total_duration_ms,
            })
        return SkillResult.fail(
            f"Pipeline '{name}' failed: {'; '.join(result.errors)}"
        )

    @logged_method()
    async def list_pipelines(self) -> SkillResult:
        """
        List available pipeline definitions from the pipelines directory.

        Returns:
            SkillResult with a list of pipeline names.
        """
        if not self._pipelines_dir.exists():
            return SkillResult.ok([])

        names = sorted(
            p.stem for p in self._pipelines_dir.glob("*.yaml")
        )
        return SkillResult.ok(names)

    @logged_method()
    async def get_pipeline_status(self, pipeline_id: str) -> SkillResult:
        """
        Retrieve the result of a previously-run pipeline.

        Args:
            pipeline_id: Short id returned by ``run_pipeline``.

        Returns:
            SkillResult wrapping the PipelineResult, or an error if not found.
        """
        result = self._history.get(pipeline_id)
        if result is None:
            return SkillResult.fail(f"Pipeline '{pipeline_id}' not found in history")

        return SkillResult.ok({
            "pipeline_name": result.pipeline_name,
            "status": result.status.value,
            "step_results": result.step_results,
            "total_duration_ms": result.total_duration_ms,
            "errors": result.errors,
        })
