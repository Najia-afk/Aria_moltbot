"""
Model Router - Smart model selection logic for Aria.

Routes requests automatically based on:
- Task complexity
- Token count / context length  
- Use case (code, reasoning, creative, etc.)
- Priority: local MLX → free cloud → paid (LAST RESORT)
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from aria_models.loader import load_catalog, get_model_entry


class TaskType(Enum):
    """Classification of task types for model selection."""
    CODE_GENERATION = "code_generation"
    COMPLEX_REASONING = "complex_reasoning"
    CREATIVE_WRITING = "creative_writing"
    LONG_CONTEXT = "long_context"
    FAST_SIMPLE = "fast_simple"
    DEFAULT = "default"


class TierPriority(Enum):
    """Tier preference order. Lower = tried first."""
    LOCAL = 0
    FREE = 1
    PAID = 2


@dataclass
class TaskProfile:
    """Characteristics of a task for routing decisions."""
    task_type: TaskType
    estimated_tokens: int  # Estimated input + output tokens
    context_length: int    # Required context window
    needs_reasoning: bool
    needs_tools: bool
    priority: str = "normal"  # low, normal, high, critical


@dataclass
class ModelScore:
    """Scoring result for a model candidate."""
    model_id: str
    score: float  # 0.0 to 1.0, higher = better fit
    tier: str
    reason: str


def estimate_task_complexity(prompt: str, task_hint: Optional[str] = None) -> TaskProfile:
    """Estimate task characteristics from prompt and optional hint."""
    prompt_lower = prompt.lower()
    word_count = len(prompt.split())
    estimated_tokens = min(word_count * 1.5, 100000)
    
    task_type = TaskType.DEFAULT
    needs_reasoning = False
    needs_tools = "tool" in prompt_lower or "function" in prompt_lower
    
    if task_hint:
        hint_lower = task_hint.lower()
        if any(k in hint_lower for k in ["code", "program", "debug", "refactor"]):
            task_type = TaskType.CODE_GENERATION
        elif any(k in hint_lower for k in ["reason", "analyze", "think", "complex"]):
            task_type = TaskType.COMPLEX_REASONING
            needs_reasoning = True
        elif any(k in hint_lower for k in ["write", "creative", "story", "poem"]):
            task_type = TaskType.CREATIVE_WRITING
        elif any(k in hint_lower for k in ["fast", "simple", "quick"]):
            task_type = TaskType.FAST_SIMPLE
    else:
        code_keywords = ["def ", "class ", "import ", "function", "code", "script", "bug", "error"]
        if any(k in prompt_lower for k in code_keywords):
            task_type = TaskType.CODE_GENERATION
        
        reasoning_keywords = ["analyze", "explain why", "compare", "evaluate", "reasoning"]
        if any(k in prompt_lower for k in reasoning_keywords):
            task_type = TaskType.COMPLEX_REASONING
            needs_reasoning = True
            
        creative_keywords = ["write", "story", "poem", "creative", "imagine"]
        if any(k in prompt_lower for k in creative_keywords):
            task_type = TaskType.CREATIVE_WRITING
    
    context_length = 8192
    if word_count > 4000:
        context_length = 131072
        task_type = TaskType.LONG_CONTEXT
    elif word_count > 2000:
        context_length = 32768
    elif word_count > 1000:
        context_length = 16384
    
    return TaskProfile(
        task_type=task_type,
        estimated_tokens=int(estimated_tokens),
        context_length=context_length,
        needs_reasoning=needs_reasoning,
        needs_tools=needs_tools,
    )


def score_model_for_task(model_id: str, task: TaskProfile, catalog: Optional[Dict[str, Any]] = None) -> Optional[ModelScore]:
    """Score a single model for a given task. Returns None if unsuitable."""
    catalog = catalog or load_catalog()
    entry = get_model_entry(model_id, catalog)
    
    if not entry:
        return None
    
    model_ctx = entry.get("contextWindow", 8192)
    model_max_tokens = entry.get("maxTokens", 4096)
    model_tier = entry.get("tier", "free")
    has_reasoning = entry.get("reasoning", False)
    
    if model_ctx < task.context_length:
        return None
    if model_max_tokens < task.estimated_tokens * 0.5:
        return None
    
    score = 1.0
    reasons = []
    
    tier_scores = {"local": 1.0, "free": 0.9, "paid": 0.7}
    tier_mult = tier_scores.get(model_tier, 0.5)
    score *= tier_mult
    reasons.append(f"tier={model_tier}({tier_mult})")
    
    if task.needs_reasoning:
        if has_reasoning:
            score *= 1.2
            reasons.append("reasoning=yes(+0.2)")
        else:
            score *= 0.7
            reasons.append("reasoning=no(-0.3)")
    
    ctx_ratio = task.context_length / model_ctx
    if ctx_ratio < 0.5:
        score *= 1.1
        reasons.append("ctx_headroom=yes(+0.1)")
    elif ctx_ratio > 0.9:
        score *= 0.8
        reasons.append("ctx_tight(-0.2)")
    
    criteria = catalog.get("criteria", {})
    use_cases = criteria.get("use_cases", {})
    
    for case_type, case_models in use_cases.items():
        if model_id in case_models and task.task_type.value == case_type:
            score *= 1.3
            reasons.append(f"use_case={case_type}(+0.3)")
            break
    
    return ModelScore(model_id=model_id, score=round(score, 3), tier=model_tier, reason=",".join(reasons))


def select_model(prompt: str, task_hint: Optional[str] = None, preferred_tier: Optional[str] = None,
                 require_reasoning: Optional[bool] = None, catalog: Optional[Dict[str, Any]] = None) -> Tuple[str, Dict[str, Any]]:
    """Select the best model for a given prompt."""
    catalog = catalog or load_catalog()
    task = estimate_task_complexity(prompt, task_hint)
    
    if require_reasoning is not None:
        task.needs_reasoning = require_reasoning
    
    models = catalog.get("models", {})
    scores: List[ModelScore] = []
    
    for model_id in models:
        if preferred_tier:
            entry = get_model_entry(model_id, catalog)
            if entry and entry.get("tier") != preferred_tier:
                continue
        
        score = score_model_for_task(model_id, task, catalog)
        if score:
            scores.append(score)
    
    if not scores:
        routing = catalog.get("routing", {})
        fallback = routing.get("primary", "litellm/kimi")
        return fallback, {"fallback": True, "reason": "no suitable models found"}
    
    scores.sort(key=lambda x: x.score, reverse=True)
    best = scores[0]
    
    metadata = {
        "selected": best.model_id,
        "score": best.score,
        "tier": best.tier,
        "reason": best.reason,
        "candidates_considered": len(scores),
        "top_alternatives": [s.model_id for s in scores[1:4]],
        "task_profile": {
            "type": task.task_type.value,
            "tokens": task.estimated_tokens,
            "context": task.context_length,
            "needs_reasoning": task.needs_reasoning,
        }
    }
    
    return best.model_id, metadata


def quick_select(task_type: str = "default", context_tokens: int = 4096, prefer_local: bool = True) -> str:
    """Quick model selection without full prompt analysis."""
    catalog = load_catalog()
    criteria = catalog.get("criteria", {})
    use_cases = criteria.get("use_cases", {})
    candidates = use_cases.get(task_type, use_cases.get("default", ["kimi"]))
    
    valid = [m for m in candidates if get_model_entry(m, catalog) and 
             get_model_entry(m, catalog).get("contextWindow", 0) >= context_tokens]
    
    if not valid:
        for model_id, entry in catalog.get("models", {}).items():
            if entry.get("contextWindow", 0) >= context_tokens:
                valid.append(model_id)
    
    if not valid:
        return "litellm/kimi"
    
    if prefer_local:
        tiers = criteria.get("tiers", {})
        local_models = tiers.get("local", [])
        for model_id in valid:
            if model_id in local_models:
                return f"litellm/{model_id}"
    
    return f"litellm/{valid[0]}"
