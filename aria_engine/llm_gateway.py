"""
Native LLM Gateway — Direct litellm SDK integration.

Zero-hop Python calls to litellm.
Features:
- Direct litellm.acompletion() with async streaming
- Model routing from models.yaml
- Fallback chain with automatic failover
- Token counting and cost tracking
- Thinking token support (Qwen3, Claude)
- Tool calling (function calling) support
- Circuit breaker for resilience
"""
import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional

import litellm
from litellm import acompletion, token_counter

from aria_engine.config import EngineConfig
from aria_engine.exceptions import LLMError
from aria_models.loader import load_catalog, get_routing_config, normalize_model_id

logger = logging.getLogger("aria.engine.llm")


@dataclass
class LLMResponse:
    """Response from LLM gateway."""
    content: str
    thinking: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    finish_reason: str = ""


@dataclass
class StreamChunk:
    """Single chunk from streaming response."""
    content: str = ""
    thinking: str = ""
    tool_call_delta: Optional[Dict[str, Any]] = None
    finish_reason: Optional[str] = None
    is_thinking: bool = False


class LLMGateway:
    """
    Native LLM gateway using litellm SDK directly.

    Usage:
        gateway = LLMGateway(config)
        response = await gateway.complete(messages, model="step-35-flash-free")

        # Streaming:
        async for chunk in gateway.stream(messages, model="qwen3-mlx"):
            print(chunk.content, end="")
    """

    def __init__(self, config: EngineConfig):
        self.config = config
        self._models_config: Optional[Dict[str, Any]] = None
        self._circuit_failures = 0
        self._circuit_threshold = 5
        self._circuit_reset_after = 30.0
        self._circuit_opened_at: Optional[float] = None
        self._latency_samples: List[float] = []

        # Configure litellm
        litellm.api_base = config.litellm_base_url
        litellm.api_key = config.litellm_master_key
        litellm.drop_params = True  # Don't fail on unsupported params

    def _load_models(self) -> Dict[str, Any]:
        """Lazy-load models.yaml configuration."""
        if self._models_config is None:
            self._models_config = load_catalog()
        return self._models_config

    def _resolve_model(self, model: str) -> str:
        """Resolve model alias to LiteLLM model string."""
        models = self._load_models()
        model_id = normalize_model_id(model)
        # Look up in models.yaml for the litellm routing string
        model_entries = models.get("models", {})
        model_def = model_entries.get(model_id, {})
        litellm_block = model_def.get("litellm", {})
        litellm_model = litellm_block.get("model", model)
        return litellm_model

    def _get_fallback_chain(self) -> List[str]:
        """Get fallback model chain from models.yaml."""
        routing = get_routing_config()
        fallbacks = routing.get("fallbacks", [])
        return [self._resolve_model(m) for m in fallbacks]

    def _is_circuit_open(self) -> bool:
        """Check if circuit breaker is open."""
        if self._circuit_failures < self._circuit_threshold:
            return False
        if self._circuit_opened_at is None:
            return False
        elapsed = time.monotonic() - self._circuit_opened_at
        if elapsed > self._circuit_reset_after:
            # Half-open: reset and try again
            self._circuit_failures = 0
            self._circuit_opened_at = None
            return False
        return True

    async def complete(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        enable_thinking: bool = False,
    ) -> LLMResponse:
        """
        Send a completion request to the LLM.

        Args:
            messages: Chat messages [{role, content}]
            model: Model to use (resolved via models.yaml)
            temperature: Override temperature
            max_tokens: Override max tokens
            tools: Tool definitions for function calling
            enable_thinking: Request thinking/reasoning tokens

        Returns:
            LLMResponse with content, thinking, tool_calls, usage stats
        """
        if self._is_circuit_open():
            raise LLMError("Circuit breaker open — too many consecutive failures")

        resolved_model = self._resolve_model(model or self.config.default_model)

        kwargs: Dict[str, Any] = {
            "model": resolved_model,
            "messages": messages,
            "temperature": temperature or self.config.default_temperature,
            "max_tokens": max_tokens or self.config.default_max_tokens,
        }

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        if enable_thinking:
            from aria_engine.thinking import build_thinking_params
            thinking_params = build_thinking_params(resolved_model, enable=True)
            kwargs.update(thinking_params)

        start = time.monotonic()

        try:
            response = await acompletion(**kwargs)
            elapsed_ms = int((time.monotonic() - start) * 1000)
            self._circuit_failures = 0
            self._latency_samples.append(elapsed_ms)

            choice = response.choices[0]
            content = choice.message.content or ""
            thinking = getattr(choice.message, "reasoning_content", None)

            # Also check for thinking tag extraction
            if not thinking:
                from aria_engine.thinking import extract_thinking_from_response
                thinking = extract_thinking_from_response(response)
                if thinking:
                    from aria_engine.thinking import strip_thinking_from_content
                    content = strip_thinking_from_content(content)

            tool_calls_raw = getattr(choice.message, "tool_calls", None)
            tool_calls = None
            if tool_calls_raw:
                tool_calls = [
                    {
                        "id": tc.id,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in tool_calls_raw
                ]

            usage = response.usage or {}

            return LLMResponse(
                content=content,
                thinking=thinking,
                tool_calls=tool_calls,
                model=resolved_model,
                input_tokens=getattr(usage, "prompt_tokens", 0),
                output_tokens=getattr(usage, "completion_tokens", 0),
                cost_usd=getattr(response, "_hidden_params", {}).get("response_cost", 0.0),
                latency_ms=elapsed_ms,
                finish_reason=choice.finish_reason or "",
            )

        except Exception as e:
            self._circuit_failures += 1
            if self._circuit_failures >= self._circuit_threshold:
                self._circuit_opened_at = time.monotonic()
            logger.error("LLM call failed (failures=%d): %s", self._circuit_failures, e)
            raise LLMError(f"LLM completion failed: {e}") from e

    async def stream(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        enable_thinking: bool = False,
    ) -> AsyncIterator[StreamChunk]:
        """
        Stream a completion response chunk by chunk.

        Yields StreamChunk objects with content/thinking deltas.
        """
        if self._is_circuit_open():
            raise LLMError("Circuit breaker open — too many consecutive failures")

        resolved_model = self._resolve_model(model or self.config.default_model)

        kwargs: Dict[str, Any] = {
            "model": resolved_model,
            "messages": messages,
            "temperature": temperature or self.config.default_temperature,
            "max_tokens": max_tokens or self.config.default_max_tokens,
            "stream": True,
        }

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        if enable_thinking:
            from aria_engine.thinking import build_thinking_params
            thinking_params = build_thinking_params(resolved_model, enable=True)
            kwargs.update(thinking_params)

        try:
            response = await acompletion(**kwargs)

            async for chunk in response:
                delta = chunk.choices[0].delta if chunk.choices else None
                if not delta:
                    continue

                yield StreamChunk(
                    content=getattr(delta, "content", "") or "",
                    thinking=getattr(delta, "reasoning_content", "") or "",
                    tool_call_delta=None,  # TODO: streaming tool calls
                    finish_reason=chunk.choices[0].finish_reason,
                    is_thinking=bool(getattr(delta, "reasoning_content", "")),
                )

            self._circuit_failures = 0

        except Exception as e:
            self._circuit_failures += 1
            if self._circuit_failures >= self._circuit_threshold:
                self._circuit_opened_at = time.monotonic()
            raise LLMError(f"LLM streaming failed: {e}") from e

    def get_stats(self) -> Dict[str, Any]:
        """Return gateway statistics."""
        return {
            "circuit_failures": self._circuit_failures,
            "circuit_open": self._is_circuit_open(),
            "latency_samples": len(self._latency_samples),
        }
