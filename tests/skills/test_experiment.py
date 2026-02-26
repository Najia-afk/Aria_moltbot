"""
Tests for the experiment skill (Layer 3 — domain).

Covers:
- Experiment creation and tracking
- Hypothesis management
- Metric logging
- Experiment completion
- Cross-experiment comparison
- Model registration
"""
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock

from aria_skills.base import SkillConfig, SkillResult, SkillStatus
from aria_skills.experiment import ExperimentSkill


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_skill() -> ExperimentSkill:
    return ExperimentSkill(SkillConfig(name="experiment"))


# ---------------------------------------------------------------------------
# Tests — Lifecycle
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_initialize():
    skill = _make_skill()
    with patch("aria_skills.experiment.EXPERIMENTS_DIR") as mock_dir:
        mock_dir.mkdir = MagicMock()
        mock_file = MagicMock()
        mock_file.exists.return_value = False
        mock_dir.__truediv__ = MagicMock(return_value=mock_file)
        ok = await skill.initialize()
    assert ok is True
    assert await skill.health_check() == SkillStatus.AVAILABLE


# ---------------------------------------------------------------------------
# Tests — Experiment Creation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_experiment():
    skill = _make_skill()
    await skill.initialize()
    with patch.object(skill, "_persist"):
        result = await skill.create_experiment(
            name="test-exp", description="A test", hypothesis="It works", tags=["ml"]
        )
    assert result.success
    exp = result.data["experiment"]
    assert exp["name"] == "test-exp"
    assert exp["hypothesis"] == "It works"
    assert exp["status"] == "running"
    assert "ml" in exp["tags"]


@pytest.mark.asyncio
async def test_create_experiment_default_name():
    skill = _make_skill()
    await skill.initialize()
    with patch.object(skill, "_persist"):
        result = await skill.create_experiment()
    assert result.success
    assert result.data["experiment"]["name"] == "unnamed"


# ---------------------------------------------------------------------------
# Tests — Metric Logging
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_log_metrics():
    skill = _make_skill()
    await skill.initialize()
    with patch.object(skill, "_persist"):
        exp_res = await skill.create_experiment(name="metrics-test")
        exp_id = exp_res.data["experiment"]["id"]
        result = await skill.log_metrics(
            experiment_id=exp_id, metrics={"accuracy": 0.95, "loss": 0.12}, step=1
        )
    assert result.success
    assert "accuracy" in result.data["metrics_logged"]
    assert "loss" in result.data["metrics_logged"]


@pytest.mark.asyncio
async def test_log_metrics_missing_experiment():
    skill = _make_skill()
    await skill.initialize()
    result = await skill.log_metrics(experiment_id="nope", metrics={"acc": 1.0})
    assert not result.success


@pytest.mark.asyncio
async def test_log_metrics_empty():
    skill = _make_skill()
    await skill.initialize()
    with patch.object(skill, "_persist"):
        exp_res = await skill.create_experiment(name="empty-metrics")
        exp_id = exp_res.data["experiment"]["id"]
        result = await skill.log_metrics(experiment_id=exp_id, metrics={})
    assert not result.success


# ---------------------------------------------------------------------------
# Tests — Experiment Completion
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_complete_experiment():
    skill = _make_skill()
    await skill.initialize()
    with patch.object(skill, "_persist"):
        exp_res = await skill.create_experiment(name="complete-test")
        exp_id = exp_res.data["experiment"]["id"]
        result = await skill.complete_experiment(
            experiment_id=exp_id, conclusion="Hypothesis confirmed"
        )
    assert result.success
    assert result.data["experiment"]["status"] == "completed"
    assert result.data["experiment"]["conclusion"] == "Hypothesis confirmed"


@pytest.mark.asyncio
async def test_complete_experiment_not_found():
    skill = _make_skill()
    await skill.initialize()
    result = await skill.complete_experiment(experiment_id="missing")
    assert not result.success


# ---------------------------------------------------------------------------
# Tests — Comparison
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_compare_experiments():
    skill = _make_skill()
    await skill.initialize()
    with patch.object(skill, "_persist"):
        r1 = await skill.create_experiment(name="exp-a")
        r2 = await skill.create_experiment(name="exp-b")
        id_a = r1.data["experiment"]["id"]
        id_b = r2.data["experiment"]["id"]
        await skill.log_metrics(experiment_id=id_a, metrics={"acc": 0.9})
        await skill.log_metrics(experiment_id=id_b, metrics={"acc": 0.95})

        result = await skill.compare_experiments(
            experiment_ids=[id_a, id_b], metric="acc"
        )
    assert result.success
    assert result.data["best"] == id_b
    assert len(result.data["comparisons"]) == 2


@pytest.mark.asyncio
async def test_compare_no_ids():
    skill = _make_skill()
    await skill.initialize()
    result = await skill.compare_experiments(experiment_ids=[], metric="acc")
    assert not result.success


# ---------------------------------------------------------------------------
# Tests — Model Registration
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_register_model():
    skill = _make_skill()
    await skill.initialize()
    result = await skill.register_model(
        name="my-model", experiment_id="exp1", version="2.0.0"
    )
    assert result.success
    assert result.data["model"]["name"] == "my-model"
    assert result.data["model"]["stage"] == "staging"


@pytest.mark.asyncio
async def test_register_model_no_name():
    skill = _make_skill()
    await skill.initialize()
    result = await skill.register_model(name="")
    assert not result.success
