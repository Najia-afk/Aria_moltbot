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
                "budget_tokens": 4096,
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
