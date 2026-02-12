"""Tests for skill auto-routing diagnostics and auto-exec helpers."""

from pathlib import Path

import pytest

from aria_mind.skills import _kernel_router as kernel_router
from aria_mind.skills.run_skill import _parse_args_payload


pytestmark = pytest.mark.unit


class TestParseArgsPayload:
    def test_parse_valid_json(self):
        args, warning = _parse_args_payload('{"k": 1}')
        assert args == {"k": 1}
        assert warning is None

    def test_parse_invalid_falls_back_to_raw_input(self):
        args, warning = _parse_args_payload("not-json")
        assert args == {"raw_input": "not-json"}
        assert warning is not None


class TestAutoRouteDiagnostics:
    @pytest.mark.asyncio
    async def test_fallback_diagnostics_present(self, monkeypatch):
        async def _fake_api(_task: str, _limit: int):
            return [], "no_api_candidates", [{"type": "api_attempt", "accepted": False}]

        monkeypatch.setattr(kernel_router, "_api_route_candidates", _fake_api)
        monkeypatch.setattr(
            kernel_router,
            "_local_manifest_route",
            lambda _task, _limit, _root_fn: [
                {
                    "skill_name": "market_data",
                    "name": "aria-market-data",
                    "canonical_name": "aria-market-data",
                }
            ],
        )

        result = await kernel_router.auto_route_task_to_skills(
            task="market sentiment",
            limit=3,
            registry={"market_data": None},
            validate_skill_coherence_fn=lambda _name: {"coherent": True},
            workspace_root_fn=lambda: Path("."),
            include_info=False,
        )

        assert result["route_source"] == "local:manifest_overlap"
        assert result["count"] == 1
        assert any(d.get("type") == "fallback" for d in result["route_diagnostics"])

    @pytest.mark.asyncio
    async def test_api_route_keeps_attempt_diagnostics(self, monkeypatch):
        async def _fake_api(_task: str, _limit: int):
            return [
                {
                    "skill_name": "llm",
                    "name": "aria-llm",
                    "canonical_name": "aria-llm",
                }
            ], "/knowledge-graph/skill-for-task", [
                {
                    "type": "api_attempt",
                    "endpoint": "/knowledge-graph/skill-for-task",
                    "accepted": True,
                    "candidate_count": 1,
                }
            ]

        monkeypatch.setattr(kernel_router, "_api_route_candidates", _fake_api)

        result = await kernel_router.auto_route_task_to_skills(
            task="summarize this text",
            limit=1,
            registry={"llm": None},
            validate_skill_coherence_fn=lambda _name: {"coherent": True},
            workspace_root_fn=lambda: Path("."),
            include_info=False,
        )

        assert result["route_source"] == "api:/knowledge-graph/skill-for-task"
        assert result["count"] == 1
        assert result["route_diagnostics"][0]["accepted"] is True
