# S1-03: Thinking Token Handling
**Epic:** E1 — Engine Core | **Priority:** P0 | **Points:** 3 | **Phase:** 1

## Problem
Qwen3 models and Claude models expose reasoning/thinking tokens via `reasoning_content` field. OpenClaw handled this opaquely. The native engine must explicitly capture, store, and expose thinking tokens so the dashboard can display Aria's reasoning process.

## Root Cause
The `litellm` library supports thinking tokens via the `reasoning_content` field on message deltas and response objects. However, the current `LLMAgent.process()` in `aria_agents/coordinator.py` (line 130-139) only extracts `result.data.get("text", "")` — no thinking token extraction.

## Fix
### `aria_engine/thinking.py`
```python
"""
Thinking token handler for models with reasoning capabilities.

Supported formats:
- Qwen3: reasoning_content field with enable_thinking=True
- Claude: extended thinking with thinking_budget parameter
- DeepSeek: reasoning_content field
"""
import re
from dataclasses import dataclass
from typing import Optional, Dict, Any, List


@dataclass
class ThinkingBlock:
    """A block of thinking/reasoning content."""
    content: str
    model: str
    token_count: int = 0
    duration_ms: int = 0


def extract_thinking_from_response(response: Any) -> Optional[str]:
    """Extract thinking content from a litellm response object."""
    if not response or not response.choices:
        return None
    
    choice = response.choices[0]
    message = choice.message
    
    # Method 1: reasoning_content field (Qwen3, DeepSeek)
    reasoning = getattr(message, "reasoning_content", None)
    if reasoning:
        return reasoning
    
    # Method 2: thinking field (Claude extended thinking)
    thinking = getattr(message, "thinking", None)
    if thinking:
        return thinking
    
    # Method 3: Check content for <think> tags (some models wrap thinking)
    content = getattr(message, "content", "") or ""
    think_match = re.search(r"<think>(.*?)</think>", content, re.DOTALL)
    if think_match:
        return think_match.group(1).strip()
    
    return None


def strip_thinking_from_content(content: str) -> str:
    """Remove <think>...</think> tags from content if present."""
    return re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()


def build_thinking_params(model: str, enable: bool = True) -> Dict[str, Any]:
    """Build model-specific parameters for enabling thinking mode."""
    params: Dict[str, Any] = {}
    
    if not enable:
        return params
    
    model_lower = model.lower()
    
    # Qwen3 models
    if "qwen" in model_lower:
        params["extra_body"] = {"enable_thinking": True}
    
    # DeepSeek models  
    elif "deepseek" in model_lower:
        params["extra_body"] = {"enable_thinking": True}
    
    # Claude models (extended thinking)
    elif "claude" in model_lower:
        params["extra_body"] = {
            "thinking": {
                "type": "enabled",
                "budget_tokens": 4096
            }
        }
    
    return params


def format_thinking_for_display(thinking: str, max_length: int = 2000) -> str:
    """Format thinking content for dashboard display."""
    if not thinking:
        return ""
    
    # Truncate if too long
    if len(thinking) > max_length:
        thinking = thinking[:max_length] + "\n\n... [truncated]"
    
    return thinking
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ❌ | Utility module, no DB access |
| 2 | .env for secrets | ❌ | No secrets used |
| 3 | models.yaml | ✅ | Model names used for format detection |
| 4 | Docker-first | ✅ | Must work in container |
| 5 | aria_memories writable | ❌ | No file writes |
| 6 | No soul modification | ❌ | No soul access |

## Dependencies
- S1-01 must complete first (needs aria_engine package)

## Verification
```bash
# 1. Imports work:
python -c "from aria_engine.thinking import extract_thinking_from_response, build_thinking_params; print('OK')"
# EXPECTED: OK

# 2. Thinking params for Qwen3:
python -c "
from aria_engine.thinking import build_thinking_params
params = build_thinking_params('qwen3-mlx', enable=True)
print(params)
"
# EXPECTED: {'extra_body': {'enable_thinking': True}}

# 3. Strip thinking tags:
python -c "
from aria_engine.thinking import strip_thinking_from_content
result = strip_thinking_from_content('<think>reasoning here</think>Final answer')
print(result)
"
# EXPECTED: Final answer
```

## Prompt for Agent
```
Implement thinking token handling for Aria Engine — supports Qwen3, DeepSeek, and Claude reasoning formats.

FILES TO READ FIRST:
- aria_models/models.yaml (lines 1-200 — model definitions)
- aria_agents/coordinator.py (lines 56-144 — current LLM call patterns)
- aria_engine/llm_gateway.py (created in S1-02 — uses thinking module)

STEPS:
1. Create aria_engine/thinking.py
2. Implement extract_thinking_from_response() — handles reasoning_content, thinking, <think> tags
3. Implement build_thinking_params() — model-specific params for enabling thinking
4. Implement strip_thinking_from_content() — remove <think> tags from output
5. Implement format_thinking_for_display() — truncation and formatting
6. Run verification commands

CONSTRAINTS: None directly apply — this is a pure utility module.
```
