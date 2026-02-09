# aria_skills/pipeline.py
"""
Data models for the Cognitive Pipeline Engine.

Pipelines let Aria compose multi-step skill workflows with
dependency tracking, failure handling, and shared context.
"""
from dataclasses import dataclass, field
from typing import Any, Optional
from enum import Enum


class StepStatus(Enum):
    """Execution status for a pipeline step."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PipelineStep:
    """
    A single step in a pipeline.

    Attributes:
        name: Unique step identifier within the pipeline.
        skill: Name of the skill to invoke.
        method: Method on the skill to call.
        params: Keyword arguments forwarded to the method.
        depends_on: Names of steps that must complete first.
        condition: Optional expression evaluated against context.
        on_failure: Failure strategy — "stop" | "skip" | "retry:N" | "fallback:skill.method".
        timeout_seconds: Max wall-clock seconds before the step is killed.
        status: Current execution status.
        result: Return value from the skill method (set after execution).
        error: Error message if the step failed.
        duration_ms: Elapsed wall-clock milliseconds.
    """
    name: str
    skill: str
    method: str
    params: dict = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)
    condition: Optional[str] = None
    on_failure: str = "stop"  # "stop" | "skip" | "retry:N" | "fallback:skill.method"
    timeout_seconds: int = 120
    status: StepStatus = StepStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    duration_ms: int = 0


@dataclass
class Pipeline:
    """
    A named, ordered collection of PipelineSteps with shared context.

    Attributes:
        name: Human-readable pipeline name.
        steps: Ordered list of steps.
        context: Shared data dict passed between steps.
        status: Aggregate pipeline status.
        created_at: ISO-8601 creation timestamp.
        completed_at: ISO-8601 completion timestamp.
        total_duration_ms: Total wall-clock milliseconds.
    """
    name: str
    steps: list[PipelineStep] = field(default_factory=list)
    context: dict = field(default_factory=dict)
    status: StepStatus = StepStatus.PENDING
    created_at: str = ""
    completed_at: str = ""
    total_duration_ms: int = 0


@dataclass
class PipelineResult:
    """
    Final result returned after a pipeline completes.

    Attributes:
        pipeline_name: Name of the pipeline that ran.
        status: Final aggregate status.
        steps_completed: Count of steps that finished successfully.
        steps_failed: Count of steps that failed.
        steps_skipped: Count of steps that were skipped.
        total_duration_ms: Total wall-clock milliseconds.
        step_results: Mapping of step name → result data.
        errors: List of error messages collected across steps.
        context: Snapshot of the shared pipeline context at completion.
    """
    pipeline_name: str
    status: StepStatus = StepStatus.PENDING
    steps_completed: int = 0
    steps_failed: int = 0
    steps_skipped: int = 0
    total_duration_ms: int = 0
    step_results: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    context: dict = field(default_factory=dict)
