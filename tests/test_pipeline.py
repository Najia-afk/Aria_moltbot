# tests/test_pipeline.py
"""
Tests for the Cognitive Pipeline Engine.

Covers data models, topological sort, template resolution,
executor behaviour (success, failure, retry, timeout, fallback),
the PipelineSkill wrapper, and YAML pipeline loading.
"""
import asyncio
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

pytestmark = pytest.mark.unit

from aria_skills.base import SkillConfig, SkillResult, SkillStatus
from aria_skills.pipeline import Pipeline, PipelineResult, PipelineStep, StepStatus
from aria_skills.pipeline_executor import (
    PipelineExecutor,
    resolve_templates,
    topological_sort,
)


# ============================================================================
# 1. Data-model tests
# ============================================================================


class TestStepStatusEnum:
    """test_step_status_enum — verify all enum members."""

    def test_all_members(self):
        assert StepStatus.PENDING.value == "pending"
        assert StepStatus.RUNNING.value == "running"
        assert StepStatus.SUCCESS.value == "success"
        assert StepStatus.FAILED.value == "failed"
        assert StepStatus.SKIPPED.value == "skipped"

    def test_member_count(self):
        assert len(StepStatus) == 5


class TestPipelineStepDefaults:
    """test_pipeline_step_defaults — verify default field values."""

    def test_defaults(self):
        step = PipelineStep(name="s1", skill="health", method="check")
        assert step.params == {}
        assert step.depends_on == []
        assert step.condition is None
        assert step.on_failure == "stop"
        assert step.timeout_seconds == 120
        assert step.status == StepStatus.PENDING
        assert step.result is None
        assert step.error is None
        assert step.duration_ms == 0


class TestPipelineCreation:
    """test_pipeline_creation — Pipeline dataclass smoke test."""

    def test_empty_pipeline(self):
        p = Pipeline(name="empty")
        assert p.name == "empty"
        assert p.steps == []
        assert p.context == {}
        assert p.status == StepStatus.PENDING
        assert p.created_at == ""
        assert p.completed_at == ""
        assert p.total_duration_ms == 0

    def test_pipeline_with_steps(self):
        steps = [
            PipelineStep(name="a", skill="s", method="m"),
            PipelineStep(name="b", skill="s", method="m", depends_on=["a"]),
        ]
        p = Pipeline(name="two_step", steps=steps, context={"key": "val"})
        assert len(p.steps) == 2
        assert p.context["key"] == "val"


# ============================================================================
# 2. Topological sort tests
# ============================================================================


class TestTopologicalSortLinear:
    """test_topological_sort_linear — A → B → C is preserved."""

    def test_linear_chain(self):
        steps = [
            PipelineStep(name="a", skill="s", method="m"),
            PipelineStep(name="b", skill="s", method="m", depends_on=["a"]),
            PipelineStep(name="c", skill="s", method="m", depends_on=["b"]),
        ]
        ordered = topological_sort(steps)
        names = [s.name for s in ordered]
        assert names.index("a") < names.index("b") < names.index("c")


class TestTopologicalSortParallel:
    """test_topological_sort_parallel — independent steps keep valid order."""

    def test_diamond(self):
        steps = [
            PipelineStep(name="start", skill="s", method="m"),
            PipelineStep(name="left", skill="s", method="m", depends_on=["start"]),
            PipelineStep(name="right", skill="s", method="m", depends_on=["start"]),
            PipelineStep(name="end", skill="s", method="m", depends_on=["left", "right"]),
        ]
        ordered = topological_sort(steps)
        names = [s.name for s in ordered]
        assert names.index("start") < names.index("left")
        assert names.index("start") < names.index("right")
        assert names.index("left") < names.index("end")
        assert names.index("right") < names.index("end")


class TestTopologicalSortCycleDetection:
    """test_topological_sort_cycle_detection — raise ValueError on cycle."""

    def test_direct_cycle(self):
        steps = [
            PipelineStep(name="a", skill="s", method="m", depends_on=["b"]),
            PipelineStep(name="b", skill="s", method="m", depends_on=["a"]),
        ]
        with pytest.raises(ValueError, match="[Cc]ycle"):
            topological_sort(steps)

    def test_self_cycle(self):
        steps = [
            PipelineStep(name="a", skill="s", method="m", depends_on=["a"]),
        ]
        with pytest.raises(ValueError, match="[Cc]ycle"):
            topological_sort(steps)

    def test_unknown_dependency(self):
        steps = [
            PipelineStep(name="a", skill="s", method="m", depends_on=["ghost"]),
        ]
        with pytest.raises(ValueError, match="unknown step"):
            topological_sort(steps)


# ============================================================================
# 3. Template resolution
# ============================================================================


class TestTemplateResolution:
    """test_template_resolution — {{context.step.field}} interpolation."""

    def test_simple_replacement(self):
        params = {"query": "{{context.research.summary}}"}
        ctx = {"research": {"summary": "AI is cool"}}
        resolved = resolve_templates(params, ctx)
        assert resolved["query"] == "AI is cool"

    def test_nested_dict(self):
        params = {"outer": {"inner": "{{context.a.val}}"}}
        ctx = {"a": {"val": "42"}}
        resolved = resolve_templates(params, ctx)
        assert resolved["outer"]["inner"] == "42"

    def test_list_replacement(self):
        params = {"items": ["{{context.s.x}}", "literal"]}
        ctx = {"s": {"x": "replaced"}}
        resolved = resolve_templates(params, ctx)
        assert resolved["items"] == ["replaced", "literal"]

    def test_missing_keeps_placeholder(self):
        params = {"key": "{{context.missing.field}}"}
        resolved = resolve_templates(params, {})
        assert resolved["key"] == "{{context.missing.field}}"

    def test_no_mutation_of_original(self):
        params = {"key": "{{context.a.b}}"}
        original = {"key": "{{context.a.b}}"}
        resolve_templates(params, {"a": {"b": "new"}})
        assert params == original


# ============================================================================
# 4. Executor tests (mock skills)
# ============================================================================


def _make_registry(*skills):
    """Build a mock registry with the given (name, skill) pairs."""
    reg = MagicMock()
    mapping = {name: skill for name, skill in skills}
    reg.get = MagicMock(side_effect=lambda n: mapping.get(n))
    return reg


def _make_skill(**methods):
    """Return a mock skill whose async methods are pre-configured."""
    skill = MagicMock()
    for method_name, return_value in methods.items():
        mock_method = AsyncMock(return_value=return_value)
        setattr(skill, method_name, mock_method)
    return skill


@pytest.mark.asyncio
class TestExecuteSimplePipeline:
    """test_execute_simple_pipeline — happy path with mocked skills."""

    async def test_two_step_success(self):
        skill = _make_skill(
            step_one=SkillResult.ok({"val": 1}),
            step_two=SkillResult.ok({"val": 2}),
        )
        reg = _make_registry(("my_skill", skill))
        executor = PipelineExecutor(reg)

        pipeline = Pipeline(
            name="simple",
            steps=[
                PipelineStep(name="s1", skill="my_skill", method="step_one"),
                PipelineStep(name="s2", skill="my_skill", method="step_two", depends_on=["s1"]),
            ],
        )

        result = await executor.execute(pipeline)
        assert result.status == StepStatus.SUCCESS
        assert result.step_results["s1"] == {"val": 1}
        assert result.step_results["s2"] == {"val": 2}
        assert result.errors == []
        assert result.total_duration_ms >= 0


@pytest.mark.asyncio
class TestExecuteWithFailureStop:
    """test_execute_with_failure_stop — pipeline halts on stop strategy."""

    async def test_stop_on_error(self):
        fail_skill = _make_skill(
            boom=SkillResult.fail("kaboom"),
            after=SkillResult.ok("should not run"),
        )
        reg = _make_registry(("sk", fail_skill))
        executor = PipelineExecutor(reg)

        pipeline = Pipeline(
            name="fail_stop",
            steps=[
                PipelineStep(name="s1", skill="sk", method="boom", on_failure="stop"),
                PipelineStep(name="s2", skill="sk", method="after", depends_on=["s1"]),
            ],
        )

        result = await executor.execute(pipeline)
        assert result.status == StepStatus.FAILED
        assert len(result.errors) >= 1
        assert "s2" not in result.step_results or result.step_results.get("s2") is None


@pytest.mark.asyncio
class TestExecuteWithFailureSkip:
    """test_execute_with_failure_skip — pipeline continues past skipped step."""

    async def test_skip_continues(self):
        skill = _make_skill(
            good=SkillResult.ok("ok"),
        )
        fail_skill = _make_skill(
            bad=SkillResult.fail("oops"),
        )
        reg = _make_registry(("good_sk", skill), ("bad_sk", fail_skill))
        executor = PipelineExecutor(reg)

        pipeline = Pipeline(
            name="fail_skip",
            steps=[
                PipelineStep(name="s1", skill="bad_sk", method="bad", on_failure="skip"),
                PipelineStep(name="s2", skill="good_sk", method="good"),
            ],
        )

        result = await executor.execute(pipeline)
        # Pipeline should still succeed because the failure was skipped
        assert result.status == StepStatus.SUCCESS
        assert result.step_results["s2"] == "ok"
        assert len(result.errors) >= 1  # s1 error recorded


@pytest.mark.asyncio
class TestExecuteWithRetry:
    """test_execute_with_retry — retry:N retries the step N times."""

    async def test_retry_succeeds_on_second_attempt(self):
        call_count = 0

        async def flaky(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RuntimeError("transient")
            return SkillResult.ok("recovered")

        skill = MagicMock()
        skill.do_thing = flaky
        reg = _make_registry(("sk", skill))
        executor = PipelineExecutor(reg)

        pipeline = Pipeline(
            name="retry_test",
            steps=[
                PipelineStep(
                    name="s1", skill="sk", method="do_thing",
                    on_failure="retry:3", timeout_seconds=5,
                ),
            ],
        )

        result = await executor.execute(pipeline)
        assert result.status == StepStatus.SUCCESS
        assert call_count == 2


@pytest.mark.asyncio
class TestExecuteWithTimeout:
    """test_execute_with_timeout — step killed after timeout_seconds."""

    async def test_timeout_marks_failed(self):
        async def slow(**kwargs):
            await asyncio.sleep(10)
            return SkillResult.ok("never")

        skill = MagicMock()
        skill.slow_method = slow
        reg = _make_registry(("sk", skill))
        executor = PipelineExecutor(reg)

        pipeline = Pipeline(
            name="timeout_test",
            steps=[
                PipelineStep(
                    name="s1", skill="sk", method="slow_method",
                    timeout_seconds=1, on_failure="stop",
                ),
            ],
        )

        result = await executor.execute(pipeline)
        assert result.status == StepStatus.FAILED
        assert any("Timeout" in e for e in result.errors)


# ============================================================================
# 5. PipelineSkill tests
# ============================================================================


@pytest.mark.asyncio
class TestPipelineSkillList:
    """test_pipeline_skill_list — list_pipelines reads YAML directory."""

    async def test_list_returns_yaml_stems(self, tmp_path):
        # Write two dummy YAML files
        (tmp_path / "alpha.yaml").write_text("name: alpha\nsteps: []")
        (tmp_path / "beta.yaml").write_text("name: beta\nsteps: []")
        (tmp_path / "not_a_pipeline.txt").write_text("ignored")

        from aria_skills.pipeline_skill import PipelineSkill

        config = SkillConfig(name="pipeline")
        skill = PipelineSkill(config)
        skill._pipelines_dir = tmp_path
        await skill.initialize()

        result = await skill.list_pipelines()
        assert result.success
        assert sorted(result.data) == ["alpha", "beta"]


@pytest.mark.asyncio
class TestPipelineSkillRun:
    """test_pipeline_skill_run — run_pipeline delegates to executor."""

    async def test_run_delegates(self, tmp_path):
        yaml_content = (
            "name: demo\n"
            "steps:\n"
            "  - name: s1\n"
            "    skill: mock_sk\n"
            "    method: do\n"
        )
        (tmp_path / "demo.yaml").write_text(yaml_content)

        from aria_skills.pipeline_skill import PipelineSkill

        config = SkillConfig(name="pipeline")
        skill = PipelineSkill(config)
        skill._pipelines_dir = tmp_path

        # Mock executor
        mock_result = PipelineResult(
            pipeline_name="demo",
            status=StepStatus.SUCCESS,
            step_results={"s1": {"ok": True}},
            total_duration_ms=42,
            errors=[],
        )
        mock_executor = AsyncMock()
        mock_executor.execute = AsyncMock(return_value=mock_result)
        skill._executor = mock_executor
        skill._status = SkillStatus.AVAILABLE

        result = await skill.run_pipeline(name="demo")
        assert result.success
        assert result.data["status"] == "success"
        assert result.data["total_duration_ms"] == 42
        mock_executor.execute.assert_awaited_once()


# ============================================================================
# 6. YAML pipeline loading
# ============================================================================


class TestYamlPipelineLoading:
    """test_yaml_pipeline_loading — parse YAML into Pipeline objects."""

    def test_load_daily_research(self):
        yaml_path = Path(__file__).resolve().parent.parent / "aria_skills" / "pipelines" / "daily_research.yaml"
        if not yaml_path.exists():
            pytest.skip("daily_research.yaml not present")

        from aria_skills.pipeline_skill import _load_pipeline_from_yaml

        pipeline = _load_pipeline_from_yaml(yaml_path)
        assert pipeline.name == "daily_research"
        assert len(pipeline.steps) == 5
        step_names = [s.name for s in pipeline.steps]
        assert "check_goals" in step_names
        assert "post_summary" in step_names

    def test_load_health_and_report(self):
        yaml_path = Path(__file__).resolve().parent.parent / "aria_skills" / "pipelines" / "health_and_report.yaml"
        if not yaml_path.exists():
            pytest.skip("health_and_report.yaml not present")

        from aria_skills.pipeline_skill import _load_pipeline_from_yaml

        pipeline = _load_pipeline_from_yaml(yaml_path)
        assert pipeline.name == "health_and_report"
        assert len(pipeline.steps) == 4

    def test_load_social_engagement(self):
        yaml_path = Path(__file__).resolve().parent.parent / "aria_skills" / "pipelines" / "social_engagement.yaml"
        if not yaml_path.exists():
            pytest.skip("social_engagement.yaml not present")

        from aria_skills.pipeline_skill import _load_pipeline_from_yaml

        pipeline = _load_pipeline_from_yaml(yaml_path)
        assert pipeline.name == "social_engagement"
        assert len(pipeline.steps) == 4
        # Check fallback strategy is preserved
        draft = next(s for s in pipeline.steps if s.name == "draft_post")
        assert draft.on_failure.startswith("fallback:")


# ============================================================================
# 7. Additional edge-case tests
# ============================================================================


@pytest.mark.asyncio
class TestExecuteWithFallback:
    """Fallback strategy delegates to alternative skill.method."""

    async def test_fallback_recovers(self):
        primary = _make_skill(
            generate_post=SkillResult.fail("llm down"),
        )
        fallback = _make_skill(
            generate_simple_post=SkillResult.ok({"content": "simple post"}),
        )
        reg = _make_registry(("brainstorm", primary), ("brainstorm", fallback))
        # Override so the same name resolves to an object with *both* methods
        combined = MagicMock()
        combined.generate_post = AsyncMock(side_effect=RuntimeError("llm down"))
        combined.generate_simple_post = AsyncMock(
            return_value=SkillResult.ok({"content": "simple post"})
        )
        reg.get = MagicMock(return_value=combined)

        executor = PipelineExecutor(reg)
        pipeline = Pipeline(
            name="fb_test",
            steps=[
                PipelineStep(
                    name="draft",
                    skill="brainstorm",
                    method="generate_post",
                    on_failure="fallback:brainstorm.generate_simple_post",
                    timeout_seconds=5,
                ),
            ],
        )

        result = await executor.execute(pipeline)
        assert result.status == StepStatus.SUCCESS
        assert result.step_results["draft"] == {"content": "simple post"}


@pytest.mark.asyncio
class TestConditionEvaluation:
    """Steps with conditions are skipped when condition is false."""

    async def test_condition_skips_step(self):
        skill = _make_skill(guarded=SkillResult.ok("ran"))
        reg = _make_registry(("sk", skill))
        executor = PipelineExecutor(reg)

        pipeline = Pipeline(
            name="cond_test",
            steps=[
                PipelineStep(
                    name="s1", skill="sk", method="guarded",
                    condition="context.nonexistent",
                ),
            ],
        )

        result = await executor.execute(pipeline)
        assert result.status == StepStatus.SUCCESS
        # s1 should have been skipped (condition falsy)
        assert pipeline.steps[0].status == StepStatus.SKIPPED


# ============================================================================
# 8. Explicitly-named tests required by TICKET-34
# ============================================================================


class TestPipelineDatamodels:
    """test_pipeline_datamodels — Pipeline, PipelineStep, StepStatus importable."""

    def test_imports(self):
        from aria_skills.pipeline import Pipeline, PipelineStep, PipelineResult, StepStatus
        assert Pipeline is not None
        assert PipelineStep is not None
        assert PipelineResult is not None
        assert StepStatus is not None

    def test_step_status_values(self):
        assert StepStatus.PENDING.value == "pending"
        assert StepStatus.SUCCESS.value == "success"
        assert StepStatus.FAILED.value == "failed"


@pytest.mark.asyncio
class TestLinearPipelineSuccess:
    """test_linear_pipeline_success — 3 steps all succeed."""

    async def test_three_step_linear(self):
        skill = _make_skill(
            a=SkillResult.ok({"v": "a"}),
            b=SkillResult.ok({"v": "b"}),
            c=SkillResult.ok({"v": "c"}),
        )
        reg = _make_registry(("sk", skill))
        executor = PipelineExecutor(reg)

        pipeline = Pipeline(
            name="linear_3",
            steps=[
                PipelineStep(name="s1", skill="sk", method="a"),
                PipelineStep(name="s2", skill="sk", method="b", depends_on=["s1"]),
                PipelineStep(name="s3", skill="sk", method="c", depends_on=["s2"]),
            ],
        )

        result = await executor.execute(pipeline)
        assert result.status == StepStatus.SUCCESS
        assert result.steps_completed == 3
        assert result.steps_failed == 0
        assert result.steps_skipped == 0
        assert len(result.step_results) == 3


@pytest.mark.asyncio
class TestSharedContext:
    """test_shared_context — step B sees step A's result in context."""

    async def test_context_propagation(self):
        skill_a = _make_skill(do_a=SkillResult.ok({"key": "from_a"}))

        # Step B should receive resolved template from context
        async def do_b(**kwargs):
            return SkillResult.ok({"received": kwargs.get("input", "")})

        skill_b = MagicMock()
        skill_b.do_b = do_b
        reg = _make_registry(("sk_a", skill_a), ("sk_b", skill_b))
        executor = PipelineExecutor(reg)

        pipeline = Pipeline(
            name="ctx_test",
            steps=[
                PipelineStep(name="step_a", skill="sk_a", method="do_a"),
                PipelineStep(
                    name="step_b", skill="sk_b", method="do_b",
                    depends_on=["step_a"],
                    params={"input": "{{context.step_a.key}}"},
                ),
            ],
        )

        result = await executor.execute(pipeline)
        assert result.status == StepStatus.SUCCESS
        assert result.step_results["step_b"]["received"] == "from_a"
        assert "step_a" in result.context


@pytest.mark.asyncio
class TestConditionTrue:
    """test_condition_true — condition met, step runs."""

    async def test_condition_met_runs_step(self):
        skill = _make_skill(
            setup=SkillResult.ok({"ready": True}),
            guarded=SkillResult.ok("executed"),
        )
        reg = _make_registry(("sk", skill))
        executor = PipelineExecutor(reg)

        pipeline = Pipeline(
            name="cond_true",
            steps=[
                PipelineStep(name="setup", skill="sk", method="setup"),
                PipelineStep(
                    name="guarded", skill="sk", method="guarded",
                    depends_on=["setup"],
                    condition="context.setup",
                ),
            ],
        )

        result = await executor.execute(pipeline)
        assert result.status == StepStatus.SUCCESS
        assert pipeline.steps[1].status == StepStatus.SUCCESS
        assert result.step_results["guarded"] == "executed"


class TestPipelineSkillProperties:
    """test_pipeline_skill_properties — name, canonical_name correct."""

    def test_name(self):
        from aria_skills.pipeline_skill import PipelineSkill
        config = SkillConfig(name="pipeline")
        skill = PipelineSkill(config)
        assert skill.name == "pipeline"
        assert skill.canonical_name == "aria-pipeline"


class TestPipelineResultFields:
    """test_pipeline_result — PipelineResult fields correct."""

    def test_defaults(self):
        r = PipelineResult(pipeline_name="test")
        assert r.pipeline_name == "test"
        assert r.status == StepStatus.PENDING
        assert r.steps_completed == 0
        assert r.steps_failed == 0
        assert r.steps_skipped == 0
        assert r.total_duration_ms == 0
        assert r.step_results == {}
        assert r.errors == []
        assert r.context == {}

    def test_custom_values(self):
        r = PipelineResult(
            pipeline_name="custom",
            status=StepStatus.SUCCESS,
            steps_completed=3,
            steps_failed=1,
            steps_skipped=1,
            total_duration_ms=500,
            step_results={"s1": "ok"},
            errors=["err"],
            context={"k": "v"},
        )
        assert r.steps_completed == 3
        assert r.steps_failed == 1
        assert r.steps_skipped == 1
        assert r.context == {"k": "v"}
