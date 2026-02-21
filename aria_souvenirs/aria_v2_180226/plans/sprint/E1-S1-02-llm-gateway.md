# S1-02: Implement LLM Gateway (Direct LiteLLM SDK)
**Epic:** E1 — Engine Core | **Priority:** P0 | **Points:** 5 | **Phase:** 1

## Problem
Currently, LLM calls flow through OpenClaw → LiteLLM (HTTP proxy at port 4000). This adds an unnecessary network hop and couples us to OpenClaw's session model. We need a direct Python gateway calling `litellm.acompletion()` natively.

Reference: `aria_mind/gateway.py` defines `GatewayInterface` ABC with `OpenClawGateway` (lines 1-100). The `OpenClawGateway.send_message()` raises `NotImplementedError`. The `NativeGateway` was planned for v1.3.

## Root Cause
The gateway interface exists (`aria_mind/gateway.py`) but only has a stub `OpenClawGateway`. No native implementation was built because OpenClaw handled all LLM routing. The coordinator in `aria_agents/coordinator.py` lines 56-144 (`LLMAgent.process()`) calls LLM through `litellm` skill's `.chat()` method — this works but adds layers of indirection.

## Fix
### `aria_engine/llm_gateway.py`
```python
"""
Native LLM Gateway — Direct litellm SDK integration.

Replaces OpenClaw's proxy layer with zero-hop Python calls.
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
from aria_models.loader import load_models_config, get_route_skill, normalize_model_id

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
        self._models_config = None
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
            self._models_config = load_models_config(self.config.models_yaml_path)
        return self._models_config
    
    def _resolve_model(self, model: str) -> str:
        """Resolve model alias to LiteLLM model string."""
        models = self._load_models()
        model_id = normalize_model_id(model)
        # Look up in models.yaml for the litellm routing string
        model_def = models.get("models", {}).get(model_id, {})
        litellm_model = model_def.get("litellm_model", model)
        return litellm_model
    
    def _get_fallback_chain(self) -> List[str]:
        """Get fallback model chain from models.yaml."""
        models = self._load_models()
        routing = models.get("routing", {})
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
            # Qwen3 thinking format
            kwargs["extra_body"] = {"enable_thinking": True}
        
        start = time.monotonic()
        
        try:
            response = await acompletion(**kwargs)
            elapsed_ms = int((time.monotonic() - start) * 1000)
            self._circuit_failures = 0
            
            choice = response.choices[0]
            content = choice.message.content or ""
            thinking = getattr(choice.message, "reasoning_content", None)
            
            tool_calls_raw = getattr(choice.message, "tool_calls", None)
            tool_calls = None
            if tool_calls_raw:
                tool_calls = [
                    {
                        "id": tc.id,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        }
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
            kwargs["extra_body"] = {"enable_thinking": True}
        
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
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | Gateway sits at infrastructure layer, called by engine |
| 2 | .env for secrets (zero in code) | ✅ | LITELLM_MASTER_KEY from env via config |
| 3 | models.yaml single source of truth | ✅ | Model resolution through aria_models.loader |
| 4 | Docker-first testing | ✅ | Uses litellm service URL from Docker network |
| 5 | aria_memories only writable path | ❌ | No file writes |
| 6 | No soul modification | ❌ | No soul access |

## Dependencies
- S1-01 must complete first (needs aria_engine package structure)

## Verification
```bash
# 1. Module imports:
python -c "from aria_engine.llm_gateway import LLMGateway, LLMResponse, StreamChunk; print('OK')"
# EXPECTED: OK

# 2. Config integration:
python -c "
from aria_engine.config import EngineConfig
from aria_engine.llm_gateway import LLMGateway
gw = LLMGateway(EngineConfig())
print(gw.get_stats())
"
# EXPECTED: {'circuit_failures': 0, 'circuit_open': False, 'latency_samples': 0}

# 3. Model resolution works:
python -c "
from aria_engine.config import EngineConfig
from aria_engine.llm_gateway import LLMGateway
gw = LLMGateway(EngineConfig())
print(gw._resolve_model('step-35-flash-free'))
"
# EXPECTED: model string from models.yaml
```

## Prompt for Agent
```
Implement the LLM Gateway for Aria Engine — a native Python gateway that calls litellm.acompletion() directly.

FILES TO READ FIRST:
- aria_engine/config.py (created in S1-01)
- aria_engine/exceptions.py (created in S1-01)
- aria_models/loader.py (full file — model resolution functions)
- aria_models/models.yaml (lines 1-100 — provider config, routing)
- aria_mind/gateway.py (full file — existing GatewayInterface ABC)
- aria_agents/coordinator.py (lines 56-144 — how LLMAgent currently calls LLM)
- aria_skills/litellm/__init__.py (lines 1-100 — current litellm skill)

STEPS:
1. Read all files above
2. Create aria_engine/llm_gateway.py with LLMGateway class
3. Implement complete() — non-streaming completion
4. Implement stream() — async generator for streaming
5. Add circuit breaker (threshold=5, reset=30s)
6. Add model resolution via aria_models.loader
7. Add thinking token extraction (reasoning_content)
8. Add tool calling support
9. Run verification commands

CONSTRAINTS:
- Constraint 2: LITELLM_MASTER_KEY from environment
- Constraint 3: All model references resolved through models.yaml
```
