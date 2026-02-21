# S10-01: Unit Tests for LLMGateway
**Epic:** E8 — Quality & Testing | **Priority:** P0 | **Points:** 3 | **Phase:** 10

## Problem
`aria_engine/llm_gateway.py` is the most critical component — every LLM call flows through it. It has zero unit tests. Without tests, we cannot verify model routing, fallback chains, circuit breaker behavior, thinking token extraction, or tool calling. This blocks production deployment.

## Root Cause
The LLM gateway was built in Sprint 1 with verification commands but no automated test suite. Test infrastructure (conftest, fixtures, mock patterns) was deferred to Sprint 10.

## Fix
### `tests/unit/test_llm_gateway.py`
```python
"""
Unit tests for aria_engine.llm_gateway.LLMGateway.

Tests:
- Successful completion (non-streaming)
- Streaming responses
- Error handling and circuit breaker
- Model resolution via models.yaml
- Thinking token extraction
- Tool calling
- Timeout handling
- Fallback chains
"""
import asyncio
import time
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aria_engine.config import EngineConfig
from aria_engine.exceptions import LLMError
from aria_engine.llm_gateway import LLMGateway, LLMResponse, StreamChunk


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def config() -> EngineConfig:
    """Create test engine config."""
    return EngineConfig(
        litellm_base_url="http://localhost:4000",
        litellm_master_key="sk-test-key",
        default_model="step-35-flash-free",
        default_temperature=0.7,
        default_max_tokens=4096,
        models_yaml_path="aria_models/models.yaml",
    )


@pytest.fixture
def gateway(config: EngineConfig) -> LLMGateway:
    """Create LLMGateway instance."""
    return LLMGateway(config)


@pytest.fixture
def mock_completion_response() -> MagicMock:
    """Create a mock litellm completion response."""
    response = MagicMock()
    choice = MagicMock()
    choice.message.content = "Hello, I'm Aria!"
    choice.message.reasoning_content = None
    choice.message.tool_calls = None
    choice.finish_reason = "stop"
    response.choices = [choice]
    usage = MagicMock()
    usage.prompt_tokens = 50
    usage.completion_tokens = 25
    response.usage = usage
    response._hidden_params = {"response_cost": 0.001}
    return response


@pytest.fixture
def mock_thinking_response() -> MagicMock:
    """Create a mock response with thinking tokens."""
    response = MagicMock()
    choice = MagicMock()
    choice.message.content = "The answer is 42."
    choice.message.reasoning_content = "Let me think step by step...\n1. Consider the question\n2. Apply logic\n3. Conclude"
    choice.message.tool_calls = None
    choice.finish_reason = "stop"
    response.choices = [choice]
    usage = MagicMock()
    usage.prompt_tokens = 100
    usage.completion_tokens = 80
    response.usage = usage
    response._hidden_params = {"response_cost": 0.005}
    return response


@pytest.fixture
def mock_tool_call_response() -> MagicMock:
    """Create a mock response with tool calls."""
    response = MagicMock()
    choice = MagicMock()
    choice.message.content = None
    choice.message.reasoning_content = None
    tc = MagicMock()
    tc.id = "call_abc123"
    tc.function.name = "search_knowledge"
    tc.function.arguments = '{"query": "Python 3.13 features"}'
    choice.message.tool_calls = [tc]
    choice.finish_reason = "tool_calls"
    response.choices = [choice]
    usage = MagicMock()
    usage.prompt_tokens = 75
    usage.completion_tokens = 30
    response.usage = usage
    response._hidden_params = {"response_cost": 0.002}
    return response


# ============================================================================
# Completion Tests
# ============================================================================

class TestLLMGatewayComplete:
    """Tests for LLMGateway.complete()."""

    @pytest.mark.asyncio
    async def test_successful_completion(
        self, gateway: LLMGateway, mock_completion_response: MagicMock
    ):
        """Test basic successful LLM completion."""
        with patch("aria_engine.llm_gateway.acompletion", new_callable=AsyncMock) as mock_ac:
            mock_ac.return_value = mock_completion_response

            result = await gateway.complete(
                messages=[{"role": "user", "content": "Hello"}],
                model="step-35-flash-free",
            )

            assert isinstance(result, LLMResponse)
            assert result.content == "Hello, I'm Aria!"
            assert result.thinking is None
            assert result.tool_calls is None
            assert result.input_tokens == 50
            assert result.output_tokens == 25
            assert result.cost_usd == 0.001
            assert result.finish_reason == "stop"
            assert result.latency_ms > 0

    @pytest.mark.asyncio
    async def test_completion_with_thinking(
        self, gateway: LLMGateway, mock_thinking_response: MagicMock
    ):
        """Test completion that includes thinking/reasoning tokens."""
        with patch("aria_engine.llm_gateway.acompletion", new_callable=AsyncMock) as mock_ac:
            mock_ac.return_value = mock_thinking_response

            result = await gateway.complete(
                messages=[{"role": "user", "content": "What is the meaning of life?"}],
                enable_thinking=True,
            )

            assert result.content == "The answer is 42."
            assert result.thinking is not None
            assert "step by step" in result.thinking
            assert result.input_tokens == 100
            assert result.output_tokens == 80

    @pytest.mark.asyncio
    async def test_completion_with_tool_calls(
        self, gateway: LLMGateway, mock_tool_call_response: MagicMock
    ):
        """Test completion that returns tool calls."""
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "search_knowledge",
                    "description": "Search the knowledge base",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"}
                        },
                        "required": ["query"],
                    },
                },
            }
        ]

        with patch("aria_engine.llm_gateway.acompletion", new_callable=AsyncMock) as mock_ac:
            mock_ac.return_value = mock_tool_call_response

            result = await gateway.complete(
                messages=[{"role": "user", "content": "Search for Python 3.13 features"}],
                tools=tools,
            )

            assert result.content is None or result.content == ""
            assert result.tool_calls is not None
            assert len(result.tool_calls) == 1
            assert result.tool_calls[0]["id"] == "call_abc123"
            assert result.tool_calls[0]["function"]["name"] == "search_knowledge"
            assert result.finish_reason == "tool_calls"

    @pytest.mark.asyncio
    async def test_completion_passes_temperature(self, gateway: LLMGateway):
        """Test that temperature is passed through to litellm."""
        with patch("aria_engine.llm_gateway.acompletion", new_callable=AsyncMock) as mock_ac:
            mock_response = MagicMock()
            choice = MagicMock()
            choice.message.content = "test"
            choice.message.reasoning_content = None
            choice.message.tool_calls = None
            choice.finish_reason = "stop"
            mock_response.choices = [choice]
            mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=5)
            mock_response._hidden_params = {"response_cost": 0.0}
            mock_ac.return_value = mock_response

            await gateway.complete(
                messages=[{"role": "user", "content": "test"}],
                temperature=0.1,
                max_tokens=100,
            )

            call_kwargs = mock_ac.call_args[1]
            assert call_kwargs["temperature"] == 0.1
            assert call_kwargs["max_tokens"] == 100


# ============================================================================
# Circuit Breaker Tests
# ============================================================================

class TestCircuitBreaker:
    """Tests for circuit breaker behavior."""

    @pytest.mark.asyncio
    async def test_circuit_opens_after_threshold(self, gateway: LLMGateway):
        """Circuit breaker opens after 5 consecutive failures."""
        with patch("aria_engine.llm_gateway.acompletion", new_callable=AsyncMock) as mock_ac:
            mock_ac.side_effect = Exception("Connection refused")

            # Fail 5 times to trip the breaker
            for i in range(5):
                with pytest.raises(LLMError):
                    await gateway.complete(
                        messages=[{"role": "user", "content": "test"}],
                    )

            # 6th call should fail immediately with circuit breaker error
            with pytest.raises(LLMError, match="Circuit breaker open"):
                await gateway.complete(
                    messages=[{"role": "user", "content": "test"}],
                )

    @pytest.mark.asyncio
    async def test_circuit_resets_after_timeout(self, gateway: LLMGateway):
        """Circuit breaker resets after reset period."""
        gateway._circuit_reset_after = 0.1  # 100ms for testing

        with patch("aria_engine.llm_gateway.acompletion", new_callable=AsyncMock) as mock_ac:
            mock_ac.side_effect = Exception("Connection refused")

            # Trip the breaker
            for _ in range(5):
                with pytest.raises(LLMError):
                    await gateway.complete(
                        messages=[{"role": "user", "content": "test"}],
                    )

            # Wait for reset
            await asyncio.sleep(0.2)

            # Now prepare a successful response
            mock_response = MagicMock()
            choice = MagicMock()
            choice.message.content = "recovered"
            choice.message.reasoning_content = None
            choice.message.tool_calls = None
            choice.finish_reason = "stop"
            mock_response.choices = [choice]
            mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=5)
            mock_response._hidden_params = {"response_cost": 0.0}
            mock_ac.side_effect = None
            mock_ac.return_value = mock_response

            result = await gateway.complete(
                messages=[{"role": "user", "content": "test"}],
            )
            assert result.content == "recovered"

    @pytest.mark.asyncio
    async def test_circuit_resets_on_success(self, gateway: LLMGateway):
        """Successful call resets failure counter."""
        mock_response = MagicMock()
        choice = MagicMock()
        choice.message.content = "ok"
        choice.message.reasoning_content = None
        choice.message.tool_calls = None
        choice.finish_reason = "stop"
        mock_response.choices = [choice]
        mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=5)
        mock_response._hidden_params = {"response_cost": 0.0}

        with patch("aria_engine.llm_gateway.acompletion", new_callable=AsyncMock) as mock_ac:
            # Fail 3 times
            mock_ac.side_effect = Exception("Error")
            for _ in range(3):
                with pytest.raises(LLMError):
                    await gateway.complete(messages=[{"role": "user", "content": "test"}])

            assert gateway._circuit_failures == 3

            # Succeed once
            mock_ac.side_effect = None
            mock_ac.return_value = mock_response
            await gateway.complete(messages=[{"role": "user", "content": "test"}])

            assert gateway._circuit_failures == 0


# ============================================================================
# Streaming Tests
# ============================================================================

class TestLLMGatewayStream:
    """Tests for LLMGateway.stream()."""

    @pytest.mark.asyncio
    async def test_streaming_response(self, gateway: LLMGateway):
        """Test streaming returns chunks with content."""
        # Mock async iterator for streaming
        chunks_data = [
            {"content": "Hello", "reasoning_content": None, "finish_reason": None},
            {"content": ", ", "reasoning_content": None, "finish_reason": None},
            {"content": "world!", "reasoning_content": None, "finish_reason": "stop"},
        ]

        async def mock_stream(*args, **kwargs):
            for chunk_data in chunks_data:
                chunk = MagicMock()
                delta = MagicMock()
                delta.content = chunk_data["content"]
                delta.reasoning_content = chunk_data["reasoning_content"]
                chunk.choices = [MagicMock(delta=delta, finish_reason=chunk_data["finish_reason"])]
                yield chunk

        with patch("aria_engine.llm_gateway.acompletion", new_callable=AsyncMock) as mock_ac:
            mock_ac.return_value = mock_stream()

            collected: list[str] = []
            async for chunk in gateway.stream(
                messages=[{"role": "user", "content": "Hi"}],
            ):
                assert isinstance(chunk, StreamChunk)
                collected.append(chunk.content)

            assert "".join(collected) == "Hello, world!"

    @pytest.mark.asyncio
    async def test_streaming_with_thinking(self, gateway: LLMGateway):
        """Test streaming includes thinking tokens."""
        chunks_data = [
            {"content": "", "reasoning_content": "Let me think...", "finish_reason": None},
            {"content": "", "reasoning_content": " step by step", "finish_reason": None},
            {"content": "The answer.", "reasoning_content": "", "finish_reason": "stop"},
        ]

        async def mock_stream(*args, **kwargs):
            for chunk_data in chunks_data:
                chunk = MagicMock()
                delta = MagicMock()
                delta.content = chunk_data["content"]
                delta.reasoning_content = chunk_data["reasoning_content"]
                chunk.choices = [MagicMock(delta=delta, finish_reason=chunk_data["finish_reason"])]
                yield chunk

        with patch("aria_engine.llm_gateway.acompletion", new_callable=AsyncMock) as mock_ac:
            mock_ac.return_value = mock_stream()

            thinking_parts: list[str] = []
            content_parts: list[str] = []
            async for chunk in gateway.stream(
                messages=[{"role": "user", "content": "Think"}],
                enable_thinking=True,
            ):
                if chunk.thinking:
                    thinking_parts.append(chunk.thinking)
                if chunk.content:
                    content_parts.append(chunk.content)

            assert "".join(thinking_parts) == "Let me think... step by step"
            assert "".join(content_parts) == "The answer."


# ============================================================================
# Model Resolution Tests
# ============================================================================

class TestModelResolution:
    """Tests for model resolution via models.yaml."""

    def test_resolve_known_model(self, gateway: LLMGateway):
        """Test resolution of a known model alias."""
        with patch.object(gateway, "_load_models") as mock_load:
            mock_load.return_value = {
                "models": {
                    "step-35-flash-free": {
                        "litellm_model": "openrouter/step-35-flash-free",
                    }
                }
            }
            result = gateway._resolve_model("step-35-flash-free")
            assert result == "openrouter/step-35-flash-free"

    def test_resolve_unknown_model_returns_as_is(self, gateway: LLMGateway):
        """Unknown model names pass through unchanged."""
        with patch.object(gateway, "_load_models") as mock_load:
            mock_load.return_value = {"models": {}}
            result = gateway._resolve_model("unknown-model-xyz")
            assert result == "unknown-model-xyz"

    def test_get_stats(self, gateway: LLMGateway):
        """Test gateway stats reporting."""
        stats = gateway.get_stats()
        assert "circuit_failures" in stats
        assert "circuit_open" in stats
        assert stats["circuit_failures"] == 0
        assert stats["circuit_open"] is False


# ============================================================================
# Error Handling Tests
# ============================================================================

class TestErrorHandling:
    """Tests for error handling behavior."""

    @pytest.mark.asyncio
    async def test_llm_error_wraps_exception(self, gateway: LLMGateway):
        """LLM errors are wrapped in LLMError."""
        with patch("aria_engine.llm_gateway.acompletion", new_callable=AsyncMock) as mock_ac:
            mock_ac.side_effect = ConnectionError("Network down")

            with pytest.raises(LLMError, match="LLM completion failed"):
                await gateway.complete(
                    messages=[{"role": "user", "content": "test"}],
                )

    @pytest.mark.asyncio
    async def test_stream_error_wraps_exception(self, gateway: LLMGateway):
        """Streaming errors are wrapped in LLMError."""
        with patch("aria_engine.llm_gateway.acompletion", new_callable=AsyncMock) as mock_ac:
            mock_ac.side_effect = ConnectionError("Network down")

            with pytest.raises(LLMError, match="LLM streaming failed"):
                async for _ in gateway.stream(
                    messages=[{"role": "user", "content": "test"}],
                ):
                    pass

    @pytest.mark.asyncio
    async def test_empty_messages_still_calls_llm(self, gateway: LLMGateway):
        """Empty message list is passed to LLM (let litellm validate)."""
        mock_response = MagicMock()
        choice = MagicMock()
        choice.message.content = ""
        choice.message.reasoning_content = None
        choice.message.tool_calls = None
        choice.finish_reason = "stop"
        mock_response.choices = [choice]
        mock_response.usage = MagicMock(prompt_tokens=0, completion_tokens=0)
        mock_response._hidden_params = {"response_cost": 0.0}

        with patch("aria_engine.llm_gateway.acompletion", new_callable=AsyncMock) as mock_ac:
            mock_ac.return_value = mock_response
            result = await gateway.complete(messages=[])
            assert result.content == ""
```

### `tests/conftest.py` (additions)
```python
"""Shared test fixtures for aria_engine tests."""
import pytest

from aria_engine.config import EngineConfig


@pytest.fixture
def engine_config() -> EngineConfig:
    """Standard test engine config — no external services."""
    return EngineConfig(
        litellm_base_url="http://localhost:4000",
        litellm_master_key="sk-test-key",
        default_model="step-35-flash-free",
        default_temperature=0.7,
        default_max_tokens=4096,
        models_yaml_path="aria_models/models.yaml",
        database_url="postgresql+asyncpg://test:test@localhost:5432/aria_test",
    )
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | Tests validate gateway layer in isolation |
| 2 | .env for secrets (zero in code) | ✅ | Test config uses dummy keys |
| 3 | models.yaml single source of truth | ✅ | Model resolution tests verify models.yaml integration |
| 4 | Docker-first testing | ✅ | Tests run in Docker CI with `pytest tests/unit/` |
| 5 | aria_memories only writable path | ❌ | Tests only — no file writes |
| 6 | No soul modification | ❌ | No soul access |

## Dependencies
- S1-02 must complete first (LLMGateway implementation exists)
- S1-01 must complete first (EngineConfig, LLMError exist)

## Verification
```bash
# 1. Run unit tests:
pytest tests/unit/test_llm_gateway.py -v
# EXPECTED: All tests pass

# 2. Coverage check:
pytest tests/unit/test_llm_gateway.py --cov=aria_engine.llm_gateway --cov-report=term-missing
# EXPECTED: >90% coverage on llm_gateway.py

# 3. Quick sanity:
python -c "import tests.unit.test_llm_gateway; print('OK')"
# EXPECTED: OK
```

## Prompt for Agent
```
Write comprehensive unit tests for aria_engine.llm_gateway.LLMGateway.

FILES TO READ FIRST:
- aria_engine/llm_gateway.py (full file — the implementation under test)
- aria_engine/config.py (EngineConfig dataclass)
- aria_engine/exceptions.py (LLMError class)
- tests/conftest.py (existing fixtures)
- tests/test_sandbox_skill.py (example of mock patterns used in project)

STEPS:
1. Read all files above
2. Create tests/unit/test_llm_gateway.py with all test classes
3. Add engine_config fixture to tests/conftest.py
4. Run pytest and verify all tests pass
5. Check coverage is >90%

CONSTRAINTS:
- Mock litellm.acompletion — never call real LLM in unit tests
- Use pytest-asyncio for async tests (asyncio_mode=auto in pyproject.toml)
- Test BOTH success and failure paths
- Test circuit breaker with fast reset (0.1s)
- Use MagicMock for litellm response objects
```
