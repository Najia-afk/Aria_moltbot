# aria_skills/pipeline_executor.py
"""
Cognitive Pipeline Engine — executes multi-step skill workflows.

Responsibilities:
- Topological sort of steps by depends_on (cycle detection)
- Sequential execution with shared context dict
- Template resolution: {{context.step_name.field}} in params
- Failure handling: stop / skip / retry:N / fallback:skill.method
- Per-step timeout via asyncio.wait_for
- Structured logging of every step
"""
import asyncio
import copy
import logging
import re
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from aria_skills.pipeline import Pipeline, PipelineResult, PipelineStep, StepStatus

logger = logging.getLogger("aria.pipeline.executor")

# Regex for template placeholders: {{context.step_name.field}}
_TEMPLATE_RE = re.compile(r"\{\{context\.(\w+)\.(\w+)\}\}")


# ── Topological Sort ────────────────────────────────────────────────────

def topological_sort(steps: List[PipelineStep]) -> List[PipelineStep]:
    """
    Return steps in dependency-respecting order (Kahn's algorithm).

    Raises:
        ValueError: If a cycle is detected in the dependency graph.
    """
    name_to_step: Dict[str, PipelineStep] = {s.name: s for s in steps}
    in_degree: Dict[str, int] = {s.name: 0 for s in steps}
    adjacency: Dict[str, List[str]] = {s.name: [] for s in steps}

    for step in steps:
        for dep in step.depends_on:
            if dep not in name_to_step:
                raise ValueError(
                    f"Step '{step.name}' depends on unknown step '{dep}'"
                )
            adjacency[dep].append(step.name)
            in_degree[step.name] += 1

    queue: deque[str] = deque(
        name for name, deg in in_degree.items() if deg == 0
    )
    sorted_names: List[str] = []

    while queue:
        current = queue.popleft()
        sorted_names.append(current)
        for neighbour in adjacency[current]:
            in_degree[neighbour] -= 1
            if in_degree[neighbour] == 0:
                queue.append(neighbour)

    if len(sorted_names) != len(steps):
        raise ValueError("Cycle detected in pipeline step dependencies")

    return [name_to_step[n] for n in sorted_names]


# ── Template Resolution ─────────────────────────────────────────────────

def resolve_templates(params: dict, context: dict) -> dict:
    """
    Deep-copy *params* and replace ``{{context.<step>.<field>}}``
    placeholders with values from the shared *context* dict.
    """
    resolved = copy.deepcopy(params)

    def _resolve_value(value: Any) -> Any:
        if isinstance(value, str):
            def _replacer(match: re.Match) -> str:
                step_name = match.group(1)
                field_name = match.group(2)
                step_ctx = context.get(step_name, {})
                if isinstance(step_ctx, dict):
                    return str(step_ctx.get(field_name, match.group(0)))
                return match.group(0)
            return _TEMPLATE_RE.sub(_replacer, value)
        if isinstance(value, dict):
            return {k: _resolve_value(v) for k, v in value.items()}
        if isinstance(value, list):
            return [_resolve_value(v) for v in value]
        return value

    return _resolve_value(resolved)


# ── Failure-strategy helpers ────────────────────────────────────────────

def _parse_on_failure(on_failure: str):
    """Return (strategy, arg) tuple from the on_failure string."""
    if on_failure == "stop":
        return ("stop", None)
    if on_failure == "skip":
        return ("skip", None)
    if on_failure.startswith("retry:"):
        try:
            retries = int(on_failure.split(":", 1)[1])
        except (ValueError, IndexError):
            retries = 1
        return ("retry", retries)
    if on_failure.startswith("fallback:"):
        target = on_failure.split(":", 1)[1]  # "skill.method"
        return ("fallback", target)
    return ("stop", None)


# ── Executor ────────────────────────────────────────────────────────────

class PipelineExecutor:
    """
    Execute a :class:`Pipeline` against a skill registry.

    Parameters:
        registry: An object with a ``.get(name)`` method that returns
                  skill instances (typically :class:`SkillRegistry`).
    """

    def __init__(self, registry):
        self.registry = registry

    # ── public API ──────────────────────────────────────────────────────

    async def execute(self, pipeline: Pipeline) -> PipelineResult:
        """Run every step of *pipeline* and return a PipelineResult."""
        pipeline.status = StepStatus.RUNNING
        pipeline.created_at = datetime.now(timezone.utc).isoformat()
        errors: List[str] = []
        step_results: Dict[str, Any] = {}
        total_start = time.monotonic()

        try:
            ordered = topological_sort(pipeline.steps)
        except ValueError as exc:
            pipeline.status = StepStatus.FAILED
            return PipelineResult(
                pipeline_name=pipeline.name,
                status=StepStatus.FAILED,
                errors=[str(exc)],
            )

        for step in ordered:
            # ── Condition check ──────────────────────────────────────
            if step.condition and not self._evaluate_condition(
                step.condition, pipeline.context
            ):
                step.status = StepStatus.SKIPPED
                logger.info(
                    "Step '%s' skipped (condition false)", step.name
                )
                continue

            # ── Execute step ─────────────────────────────────────────
            success = await self._execute_step(step, pipeline.context)
            step_results[step.name] = step.result

            if success:
                pipeline.context[step.name] = step.result
            else:
                errors.append(f"{step.name}: {step.error}")
                strategy, arg = _parse_on_failure(step.on_failure)

                if strategy == "stop":
                    logger.error(
                        "Pipeline '%s' stopped at step '%s': %s",
                        pipeline.name, step.name, step.error,
                    )
                    break
                elif strategy == "skip":
                    logger.warning(
                        "Step '%s' failed but skipped: %s",
                        step.name, step.error,
                    )
                    continue
                # retry and fallback are handled inside _execute_step

        total_ms = int((time.monotonic() - total_start) * 1000)
        pipeline.total_duration_ms = total_ms
        pipeline.completed_at = datetime.now(timezone.utc).isoformat()

        # Compute step counts
        completed = sum(1 for s in ordered if s.status == StepStatus.SUCCESS)
        failed = sum(1 for s in ordered if s.status == StepStatus.FAILED)
        skipped = sum(1 for s in ordered if s.status == StepStatus.SKIPPED)

        if errors and any(
            s.status == StepStatus.FAILED
            and _parse_on_failure(s.on_failure)[0] == "stop"
            for s in ordered
        ):
            pipeline.status = StepStatus.FAILED
        else:
            pipeline.status = StepStatus.SUCCESS

        return PipelineResult(
            pipeline_name=pipeline.name,
            status=pipeline.status,
            steps_completed=completed,
            steps_failed=failed,
            steps_skipped=skipped,
            step_results=step_results,
            total_duration_ms=total_ms,
            errors=errors,
            context=dict(pipeline.context),
        )

    # ── internals ───────────────────────────────────────────────────────

    async def _execute_step(
        self, step: PipelineStep, context: dict
    ) -> bool:
        """
        Execute a single step, handling retry / fallback / timeout.

        Returns True on success, False on failure.
        """
        strategy, arg = _parse_on_failure(step.on_failure)
        max_attempts = arg if strategy == "retry" else 1

        for attempt in range(max_attempts):
            step.status = StepStatus.RUNNING
            start = time.monotonic()
            try:
                result = await asyncio.wait_for(
                    self._invoke_skill(step, context),
                    timeout=step.timeout_seconds,
                )
                step.duration_ms = int((time.monotonic() - start) * 1000)
                step.result = result
                step.status = StepStatus.SUCCESS
                logger.info(
                    "Step '%s' succeeded (%d ms)",
                    step.name, step.duration_ms,
                )
                return True

            except asyncio.TimeoutError:
                step.duration_ms = int((time.monotonic() - start) * 1000)
                step.error = f"Timeout after {step.timeout_seconds}s"
                step.status = StepStatus.FAILED
                logger.warning(
                    "Step '%s' timed out after %ds",
                    step.name, step.timeout_seconds,
                )

            except Exception as exc:  # noqa: BLE001
                step.duration_ms = int((time.monotonic() - start) * 1000)
                step.error = str(exc)
                step.status = StepStatus.FAILED
                logger.warning(
                    "Step '%s' attempt %d/%d failed: %s",
                    step.name, attempt + 1, max_attempts, exc,
                )

            # Retry back-off
            if attempt < max_attempts - 1:
                await asyncio.sleep(0.5 * (attempt + 1))

        # ── Fallback ────────────────────────────────────────────────
        if strategy == "fallback" and arg:
            return await self._execute_fallback(step, arg, context)

        return False

    async def _invoke_skill(
        self, step: PipelineStep, context: dict
    ) -> Any:
        """Resolve templates, look up skill, and call the method."""
        params = resolve_templates(step.params, context)
        skill = self.registry.get(step.skill)
        if skill is None:
            raise RuntimeError(f"Skill '{step.skill}' not found in registry")

        method = getattr(skill, step.method, None)
        if method is None:
            raise RuntimeError(
                f"Method '{step.method}' not found on skill '{step.skill}'"
            )

        result = await method(**params)

        # Unwrap SkillResult if the method returns one
        if hasattr(result, "success"):
            if not result.success:
                raise RuntimeError(result.error or "Skill returned failure")
            return result.data
        return result

    async def _execute_fallback(
        self, step: PipelineStep, target: str, context: dict
    ) -> bool:
        """Run a fallback skill.method when the primary step fails."""
        try:
            skill_name, method_name = target.split(".", 1)
        except ValueError:
            step.error += f"; invalid fallback target '{target}'"
            return False

        skill = self.registry.get(skill_name)
        if skill is None:
            step.error += f"; fallback skill '{skill_name}' not found"
            return False

        method = getattr(skill, method_name, None)
        if method is None:
            step.error += (
                f"; fallback method '{method_name}' not on '{skill_name}'"
            )
            return False

        start = time.monotonic()
        try:
            params = resolve_templates(step.params, context)
            result = await method(**params)
            step.duration_ms += int((time.monotonic() - start) * 1000)

            if hasattr(result, "success"):
                if not result.success:
                    raise RuntimeError(result.error or "Fallback returned failure")
                step.result = result.data
            else:
                step.result = result

            step.status = StepStatus.SUCCESS
            logger.info(
                "Step '%s' recovered via fallback %s", step.name, target
            )
            return True

        except Exception as exc:  # noqa: BLE001
            step.duration_ms += int((time.monotonic() - start) * 1000)
            step.error += f"; fallback '{target}' also failed: {exc}"
            step.status = StepStatus.FAILED
            return False

    @staticmethod
    def _evaluate_condition(condition: str, context: dict) -> bool:
        """
        Safely evaluate a simple condition expression against context.

        Only supports:
            context.<step>.<field> == <value>
            context.<step>.<field> != <value>
            context.<step>   (truthy check)
        """
        condition = condition.strip()

        # Truthy check: "context.step_name"
        m = re.match(r"^context\.(\w+)$", condition)
        if m:
            return bool(context.get(m.group(1)))

        # Equality / inequality
        m = re.match(
            r"^context\.(\w+)\.(\w+)\s*(==|!=)\s*['\"]?(.+?)['\"]?$",
            condition,
        )
        if m:
            step_name, field, op, value = m.groups()
            step_ctx = context.get(step_name, {})
            actual = step_ctx.get(field) if isinstance(step_ctx, dict) else None
            if op == "==":
                return str(actual) == value
            return str(actual) != value

        logger.warning("Unsupported condition expression: %s", condition)
        return True  # default-allow
