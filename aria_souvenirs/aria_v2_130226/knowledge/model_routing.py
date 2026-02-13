"""Automated model routing based on task complexity, token count, and context length.

Routes requests through the priority chain: local → free → paid
using heuristics defined in models.yaml criteria section.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from aria_models.loader import load_catalog, get_model_entry, get_focus_default


class TaskComplexity(Enum):
    """Task complexity levels for routing decisions."""
    SIMPLE = "simple"          # < 500 tokens, straightforward
    MODERATE = "moderate"      # 500-2000 tokens, some reasoning
    COMPLEX = "complex"        # 2000-8000 tokens, multi-step
    VERY_COMPLEX = "very_complex"  # > 8000 tokens, deep analysis


class RoutingTier(Enum):
    """Routing priority tiers."""
    LOCAL = "local"
    FREE = "free"
    PAID = "paid"


@dataclass
class RoutingRequest:
    """A request to be routed to an appropriate model."""
    content: str = ""
    estimated_tokens: Optional[int] = None
    context_length: int = 0
    requires_reasoning: bool = False
    requires_tools: bool = False
    focus_type: Optional[str] = None
    preferred_model: Optional[str] = None
    timeout_seconds: Optional[int] = None
    
    def estimate_tokens(self) -> int:
        """Estimate token count if not provided."""
        if self.estimated_tokens is not None:
            return self.estimated_tokens
        # Rough estimate: ~4 chars per token for English text
        return len(self.content) // 4 + self.context_length // 4
    
    @property
    def complexity(self) -> TaskComplexity:
        """Determine task complexity based on tokens and features."""
        tokens = self.estimate_tokens()
        
        if tokens > 8000 or self.requires_reasoning and tokens > 4000:
            return TaskComplexity.VERY_COMPLEX
        elif tokens > 2000 or self.requires_reasoning:
            return TaskComplexity.COMPLEX
        elif tokens > 500:
            return TaskComplexity.MODERATE
        return TaskComplexity.SIMPLE


@dataclass
class RoutingResult:
    """Result of a routing decision."""
    model_id: str
    model_name: str
    tier: RoutingTier
    reason: str
    estimated_cost: float = 0.0
    context_window: int = 8192
    confidence: float = 1.0
    fallback_chain: List[str] = field(default_factory=list)


class ModelRouter:
    """Smart model router with tiered fallback logic."""
    
    def __init__(self, catalog: Optional[Dict[str, Any]] = None):
        self.catalog = catalog or load_catalog()
        self.criteria = self.catalog.get("criteria", {})
        self.models = self.catalog.get("models", {})
        self.routing_config = self.catalog.get("routing", {})
        
    def _get_tier_models(self, tier: RoutingTier) -> List[str]:
        """Get models for a specific tier."""
        tiers = self.criteria.get("tiers", {})
        return tiers.get(tier.value, [])
    
    def _select_from_tier(
        self, 
        tier: RoutingTier, 
        request: RoutingRequest,
        use_case: Optional[str] = None
    ) -> Optional[str]:
        """Select best model from a tier for the request."""
        tier_models = self._get_tier_models(tier)
        
        if not tier_models:
            return None
            
        # If focus default is in this tier, prefer it
        if request.focus_type:
            focus_default = get_focus_default(request.focus_type, self.catalog)
            if focus_default and focus_default.split("/")[-1] in tier_models:
                return focus_default.split("/")[-1]
        
        # Use case-based selection
        use_cases = self.criteria.get("use_cases", {})
        if use_case and use_case in use_cases:
            for model_id in use_cases[use_case]:
                if model_id in tier_models:
                    return model_id
        
        # Context-length based selection
        total_tokens_needed = request.estimate_tokens() + request.context_length
        for model_id in tier_models:
            entry = self.models.get(model_id, {})
            ctx_window = entry.get("contextWindow", 8192)
            if ctx_window >= total_tokens_needed:
                return model_id
        
        # Fallback to first available
        return tier_models[0] if tier_models else None
    
    def route(self, request: RoutingRequest) -> RoutingResult:
        """Route a request to the appropriate model.
        
        Routing logic:
        1. Check if preferred model is specified and available
        2. Start with local tier for simple tasks
        3. Escalate to free tier for moderate complexity
        4. Use paid tier for complex tasks or when context requires it
        5. Build fallback chain through remaining tiers
        """
        # Honor explicit preferred model
        if request.preferred_model:
            entry = get_model_entry(request.preferred_model, self.catalog)
            if entry:
                return RoutingResult(
                    model_id=request.preferred_model,
                    model_name=entry.get("name", request.preferred_model),
                    tier=RoutingTier(entry.get("tier", "free")),
                    reason="User preferred model",
                    estimated_cost=self._estimate_cost(entry, request),
                    context_window=entry.get("contextWindow", 8192),
                    fallback_chain=self._build_fallback_chain(request)
                )
        
        # Determine target tier based on complexity
        complexity = request.complexity
        total_context = request.estimate_tokens() + request.context_length
        
        # Check if we need paid tier due to context length
        max_free_ctx = max(
            (self.models.get(m, {}).get("contextWindow", 0) 
             for m in self._get_tier_models(RoutingTier.FREE)),
            default=0
        )
        
        # Route based on complexity and context requirements
        if complexity == TaskComplexity.SIMPLE and not request.requires_reasoning:
            # Try local first for simple tasks
            target_tiers = [RoutingTier.LOCAL, RoutingTier.FREE, RoutingTier.PAID]
            reason = f"Simple task ({request.estimate_tokens()} tokens), trying local first"
        elif complexity in (TaskComplexity.MODERATE, TaskComplexity.SIMPLE):
            # Moderate tasks → free tier
            target_tiers = [RoutingTier.FREE, RoutingTier.PAID]
            reason = f"Moderate complexity ({request.estimate_tokens()} tokens), using free tier"
        elif total_context > max_free_ctx * 0.8:
            # Large context → paid tier for reliability
            target_tiers = [RoutingTier.PAID, RoutingTier.FREE]
            reason = f"Large context ({total_context} tokens), using paid tier"
        else:
            # Complex reasoning → start with free, fallback to paid
            target_tiers = [RoutingTier.FREE, RoutingTier.PAID]
            reason = f"Complex task ({complexity.value}), using best available"
        
        # Select model from appropriate tier
        selected_model = None
        selected_tier = None
        
        for tier in target_tiers:
            use_case = None
            if request.focus_type == "devsecops":
                use_case = "code_generation"
            elif request.requires_reasoning:
                use_case = "complex_reasoning"
                
            model_id = self._select_from_tier(tier, request, use_case)
            if model_id:
                selected_model = model_id
                selected_tier = tier
                break
        
        # Fallback to primary from routing config
        if not selected_model:
            primary = self.routing_config.get("primary", "litellm/kimi")
            selected_model = primary.split("/")[-1]
            selected_tier = RoutingTier.PAID
            reason = "Fallback to primary model"
        
        entry = self.models.get(selected_model, {})
        
        return RoutingResult(
            model_id=selected_model,
            model_name=entry.get("name", selected_model),
            tier=selected_tier or RoutingTier.FREE,
            reason=reason,
            estimated_cost=self._estimate_cost(entry, request),
            context_window=entry.get("contextWindow", 8192),
            fallback_chain=self._build_fallback_chain(request, exclude=selected_model)
        )
    
    def _estimate_cost(self, model_entry: Dict[str, Any], request: RoutingRequest) -> float:
        """Estimate cost for the request."""
        cost_info = model_entry.get("cost", {})
        input_cost = cost_info.get("input", 0)
        output_cost = cost_info.get("output", 0)
        
        # Estimate: input tokens + 50% for output
        est_tokens = request.estimate_tokens()
        est_output = est_tokens // 2
        
        # Cost per 1M tokens
        input_cost_total = (est_tokens / 1_000_000) * input_cost
        output_cost_total = (est_output / 1_000_000) * output_cost
        
        return round(input_cost_total + output_cost_total, 6)
    
    def _build_fallback_chain(
        self, 
        request: RoutingRequest,
        exclude: Optional[str] = None
    ) -> List[str]:
        """Build a fallback chain of models."""
        chain = []
        
        # Use routing config fallbacks as base
        config_fallbacks = self.routing_config.get("fallbacks", [])
        for fb in config_fallbacks:
            model_id = fb.split("/")[-1]
            if model_id != exclude and model_id not in chain:
                chain.append(model_id)
        
        # Add tier-based fallbacks
        for tier in [RoutingTier.FREE, RoutingTier.PAID, RoutingTier.LOCAL]:
            for model_id in self._get_tier_models(tier):
                if model_id != exclude and model_id not in chain:
                    entry = self.models.get(model_id, {})
                    ctx = entry.get("contextWindow", 8192)
                    if ctx >= request.estimate_tokens():
                        chain.append(model_id)
        
        return chain[:5]  # Limit to 5 fallbacks
    
    def get_profile(self, profile_name: str) -> Optional[Dict[str, Any]]:
        """Get a predefined routing profile."""
        profiles = self.catalog.get("profiles", {})
        return profiles.get(profile_name)
    
    def route_with_profile(
        self, 
        request: RoutingRequest, 
        profile_name: str
    ) -> RoutingResult:
        """Route using a predefined profile."""
        profile = self.get_profile(profile_name)
        if not profile:
            return self.route(request)
        
        # Override request with profile settings
        model_id = profile.get("model")
        if model_id:
            request.preferred_model = model_id
        
        result = self.route(request)
        result.reason = f"Profile '{profile_name}': {result.reason}"
        return result


# Convenience functions for common routing scenarios

def route_simple_query(content: str, context_length: int = 0) -> RoutingResult:
    """Route a simple text query."""
    router = ModelRouter()
    request = RoutingRequest(
        content=content,
        context_length=context_length,
        requires_reasoning=False
    )
    return router.route(request)


def route_code_task(code: str, language: str = "python") -> RoutingResult:
    """Route a code-related task."""
    router = ModelRouter()
    request = RoutingRequest(
        content=code,
        focus_type="devsecops",
        requires_reasoning=True
    )
    return router.route(request)


def route_complex_analysis(content: str, context_length: int = 0) -> RoutingResult:
    """Route a complex analysis task."""
    router = ModelRouter()
    request = RoutingRequest(
        content=content,
        context_length=context_length,
        requires_reasoning=True
    )
    # Force start at free tier minimum
    request.estimated_tokens = max(len(content) // 4, 2000)
    return router.route(request)


def route_with_focus(content: str, focus_type: str) -> RoutingResult:
    """Route using focus-specific defaults."""
    router = ModelRouter()
    request = RoutingRequest(
        content=content,
        focus_type=focus_type,
        requires_reasoning=True
    )
    return router.route(request)


def get_routing_summary() -> Dict[str, Any]:
    """Get a summary of routing configuration."""
    router = ModelRouter()
    catalog = router.catalog
    criteria = router.criteria
    
    return {
        "priority_order": criteria.get("priority", []),
        "tiers": {
            tier: len(models) 
            for tier, models in criteria.get("tiers", {}).items()
        },
        "use_cases": list(criteria.get("use_cases", {}).keys()),
        "focus_defaults": criteria.get("focus_defaults", {}),
        "profiles": list(catalog.get("profiles", {}).keys()),
        "primary": catalog.get("routing", {}).get("primary"),
        "fallbacks": catalog.get("routing", {}).get("fallbacks", []),
    }
