"""
Automated Model Router for Aria

Routes requests to appropriate models based on:
- Task complexity
- Context length requirements  
- Token count estimates
- Focus/agent type
- Cost optimization (local → free → paid)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Try imports for different environments
try:
    from aria_models.loader import load_catalog, get_model_entry, list_all_model_ids
except ImportError:
    import sys
    sys.path.insert(0, "/root/.openclaw/workspace")
    from aria_models.loader import load_catalog, get_model_entry, list_all_model_ids


class TaskComplexity(Enum):
    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"
    EXPERT = "expert"


class ModelTier(Enum):
    LOCAL = "local"
    FREE = "free"
    PAID = "paid"


@dataclass
class RoutingDecision:
    """Result of model routing decision."""
    model_id: str
    model_name: str
    reason: str
    tier: ModelTier
    estimated_cost: float
    context_window: int
    confidence: float  # 0.0 - 1.0


@dataclass  
class TaskProfile:
    """Profile of the task being routed."""
    complexity: TaskComplexity
    estimated_input_tokens: int
    estimated_output_tokens: int
    requires_tools: bool
    requires_reasoning: bool
    focus_type: Optional[str] = None
    preferred_models: Optional[List[str]] = None


class ModelRouter:
    """Intelligent model selection based on task characteristics."""
    
    # Context window thresholds
    CONTEXT_SMALL = 4096      # < 4K
    CONTEXT_MEDIUM = 32768    # 4K - 32K  
    CONTEXT_LARGE = 131072    # 32K - 128K
    # > 128K is extra large
    
    # Focus-based defaults from heuristics
    FOCUS_DEFAULTS = {
        "orchestrator": "qwen3-mlx",
        "devsecops": "qwen3-coder-free",
        "data": "deepseek-free",
        "trader": "qwen3-next-free",
        "creative": "trinity-free",
        "social": "qwen3-mlx",
        "journalist": "deepseek-free",
        "conversational": "qwen3-mlx",
    }
    
    def __init__(self, catalog: Optional[Dict[str, Any]] = None):
        self.catalog = catalog or load_catalog()
        self.models = self.catalog.get("models", {})
        self.criteria = self.catalog.get("criteria", {})
        self.routing = self.catalog.get("routing", {})
        
    def estimate_tokens(self, text: str) -> int:
        """Rough token estimation: ~4 chars per token."""
        return len(text) // 4 + 1
    
    def classify_complexity(
        self, 
        prompt: str,
        has_code: bool = False,
        requires_analysis: bool = False
    ) -> TaskComplexity:
        """Classify task complexity based on prompt characteristics."""
        tokens = self.estimate_tokens(prompt)
        
        # Check for expert-level indicators
        expert_indicators = [
            "design", "architecture", "audit", "security review",
            "novel", "research", "complex debug", "optimize"
        ]
        if any(ind in prompt.lower() for ind in expert_indicators):
            return TaskComplexity.EXPERT
            
        # Check for complex indicators
        complex_indicators = [
            "analyze", "explain", "review", "compare", "evaluate",
            "implement", "refactor", "test"
        ]
        if has_code or requires_analysis or any(ind in prompt.lower() for ind in complex_indicators):
            if tokens > 8000:
                return TaskComplexity.COMPLEX
            return TaskComplexity.MEDIUM
            
        # Simple tasks
        if tokens < 500:
            return TaskComplexity.SIMPLE
            
        return TaskComplexity.MEDIUM
    
    def get_models_by_tier(self, tier: ModelTier) -> List[Tuple[str, Dict[str, Any]]]:
        """Get all models in a specific tier, sorted by capability."""
        tier_models = [
            (mid, entry) for mid, entry in self.models.items()
            if entry.get("tier") == tier.value
        ]
        # Sort by context window (larger first for capability)
        tier_models.sort(key=lambda x: x[1].get("contextWindow", 0), reverse=True)
        return tier_models
    
    def select_by_context(
        self, 
        context_tokens: int,
        tier: ModelTier,
        requires_reasoning: bool = False
    ) -> Optional[Tuple[str, Dict[str, Any]]]:
        """Select appropriate model based on context requirements."""
        candidates = self.get_models_by_tier(tier)
        
        # Filter by reasoning requirement
        if requires_reasoning:
            candidates = [
                (mid, entry) for mid, entry in candidates
                if entry.get("reasoning", False)
            ]
        
        # Find first model that can handle the context
        for model_id, entry in candidates:
            if entry.get("contextWindow", 0) >= context_tokens:
                return (model_id, entry)
        
        return None
    
    def route(
        self,
        prompt: str,
        focus_type: Optional[str] = None,
        requires_tools: bool = False,
        requires_reasoning: bool = False,
        max_tokens: Optional[int] = None,
        preferred_model: Optional[str] = None
    ) -> RoutingDecision:
        """
        Route a request to the best model.
        
        Strategy:
        1. Use preferred model if specified and available
        2. Use focus default if focus_type provided
        3. Estimate complexity and context needs
        4. Try local → free → paid tiers
        5. Select within tier based on context/reasoning needs
        """
        # 1. Check preferred model
        if preferred_model and preferred_model in self.models:
            entry = self.models[preferred_model]
            return RoutingDecision(
                model_id=preferred_model,
                model_name=entry.get("name", preferred_model),
                reason="User preferred model",
                tier=ModelTier(entry.get("tier", "free")),
                estimated_cost=0.0 if entry.get("tier") != "paid" else 0.001,
                context_window=entry.get("contextWindow", 8192),
                confidence=0.9
            )
        
        # 2. Check focus default
        if focus_type and focus_type in self.FOCUS_DEFAULTS:
            default_model = self.FOCUS_DEFAULTS[focus_type]
            if default_model in self.models:
                entry = self.models[default_model]
                return RoutingDecision(
                    model_id=default_model,
                    model_name=entry.get("name", default_model),
                    reason=f"Focus default for {focus_type}",
                    tier=ModelTier(entry.get("tier", "free")),
                    estimated_cost=0.0 if entry.get("tier") != "paid" else 0.001,
                    context_window=entry.get("contextWindow", 8192),
                    confidence=0.85
                )
        
        # 3. Analyze task
        complexity = self.classify_complexity(prompt, requires_analysis=requires_reasoning)
        input_tokens = self.estimate_tokens(prompt)
        output_tokens = max_tokens or 2048
        total_context = input_tokens + output_tokens
        
        # 4. Try tiers in priority order
        tiers_to_try = [ModelTier.LOCAL, ModelTier.FREE, ModelTier.PAID]
        reasons_tried = []
        
        for tier in tiers_to_try:
            result = self.select_by_context(
                total_context, 
                tier, 
                requires_reasoning=requires_reasoning
            )
            
            if result:
                model_id, entry = result
                
                # Skip if task too complex for simple models
                if complexity == TaskComplexity.EXPERT and tier == ModelTier.LOCAL:
                    reasons_tried.append(f"Skipped {model_id}: expert task needs stronger model")
                    continue
                    
                cost = entry.get("cost", {})
                estimated_cost = (
                    cost.get("input", 0) * input_tokens +
                    cost.get("output", 0) * output_tokens
                ) / 1000  # Cost per 1K tokens
                
                reason = f"{tier.value} tier selected for {complexity.value} task"
                if requires_reasoning:
                    reason += " with reasoning"
                    
                return RoutingDecision(
                    model_id=model_id,
                    model_name=entry.get("name", model_id),
                    reason=reason,
                    tier=tier,
                    estimated_cost=estimated_cost,
                    context_window=entry.get("contextWindow", 8192),
                    confidence=0.8 if tier == ModelTier.LOCAL else 0.75
                )
            else:
                reasons_tried.append(f"No {tier.value} model can handle {total_context} tokens")
        
        # 5. Ultimate fallback to primary routing model
        primary = self.routing.get("primary", "litellm/kimi")
        primary_id = primary.split("/")[-1] if "/" in primary else primary
        
        return RoutingDecision(
            model_id=primary_id,
            model_name="Primary Fallback",
            reason="No suitable model found; using primary fallback",
            tier=ModelTier.PAID,
            estimated_cost=0.001,
            context_window=128000,
            confidence=0.5
        )
    
    def get_fallback_chain(self, primary_model: str) -> List[str]:
        """Get fallback chain for a model."""
        return self.routing.get("fallbacks", [])
    
    def to_litellm_model(self, model_id: str) -> str:
        """Convert model ID to litellm format."""
        entry = self.models.get(model_id, {})
        litellm = entry.get("litellm", {})
        return litellm.get("model", f"litellm/{model_id}")


def route_request(
    prompt: str,
    focus_type: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """Convenience function for one-off routing."""
    router = ModelRouter()
    decision = router.route(prompt, focus_type=focus_type, **kwargs)
    return {
        "model_id": decision.model_id,
        "model_name": decision.model_name,
        "litellm_model": router.to_litellm_model(decision.model_id),
        "reason": decision.reason,
        "tier": decision.tier.value,
        "estimated_cost_usd": round(decision.estimated_cost, 6),
        "context_window": decision.context_window,
        "confidence": decision.confidence,
    }


if __name__ == "__main__":
    # Test examples
    test_prompts = [
        ("What is 2+2?", "orchestrator"),
        ("Explain the architecture of a distributed system with event sourcing and CQRS patterns", "devsecops"),
        ("Write a Python function to calculate fibonacci numbers", "creative"),
        ("Analyze this security vulnerability: buffer overflow in C code", "devsecops"),
    ]
    
    router = ModelRouter()
    for prompt, focus in test_prompts:
        result = route_request(prompt, focus_type=focus)
        print(f"\nPrompt: {prompt[:50]}...")
        print(f"Focus: {focus}")
        print(f"Routed to: {result['model_name']} ({result['model_id']})")
        print(f"Reason: {result['reason']}")
        print(f"Tier: {result['tier']}, Cost: ${result['estimated_cost_usd']:.6f}")
