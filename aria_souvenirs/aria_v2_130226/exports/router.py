"""Automated model router for intelligent model selection.

Implements smart routing logic that selects the optimal model based on:
- Task complexity and type
- Context length requirements
- Cost constraints (local → free → paid)
- Focus/agent specialization

Usage:
    from aria_models.router import ModelRouter
    
    router = ModelRouter()
    model = router.select_for_task(
        task_type="code_generation",
        estimated_tokens=5000,
        focus="devsecops"
    )
    # Returns: "litellm/qwen3-coder-free"
"""
from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass

from aria_models.loader import load_catalog, get_focus_default, get_model_entry


class TaskType(str, Enum):
    """Supported task types for routing."""
    CODE_GENERATION = "code_generation"
    COMPLEX_REASONING = "complex_reasoning"
    CREATIVE_WRITING = "creative_writing"
    LONG_CONTEXT = "long_context"
    FAST_SIMPLE = "fast_simple"
    EMBEDDING = "embedding"
    GENERAL = "default"


class Tier(str, Enum):
    """Model tiers in priority order."""
    LOCAL = "local"
    FREE = "free"
    PAID = "paid"


@dataclass(frozen=True)
class RoutingDecision:
    """Result of a model routing decision."""
    model_id: str
    provider_prefix: str
    tier: Tier
    reason: str
    estimated_cost: float  # 0.0 for free/local


class ModelRouter:
    """Intelligent model router with cost-aware selection."""
    
    # Complexity thresholds (estimated tokens)
    SIMPLE_TOKEN_THRESHOLD = 100
    MEDIUM_TOKEN_THRESHOLD = 1000
    LONG_CONTEXT_THRESHOLD = 32768  # 32K
    
    # Task type → preferred model list (from models.yaml criteria.use_cases)
    TASK_PREFERENCES: Dict[TaskType, List[str]] = {
        TaskType.CODE_GENERATION: ["qwen3-coder-free", "gpt-oss-free"],
        TaskType.COMPLEX_REASONING: ["chimera-free", "deepseek-free", "kimi-k2-thinking"],
        TaskType.CREATIVE_WRITING: ["trinity-free", "glm-free"],
        TaskType.LONG_CONTEXT: ["qwen3-next-free", "nemotron-free", "kimi"],
        TaskType.FAST_SIMPLE: ["gpt-oss-small-free", "qwen3-mlx"],
        TaskType.EMBEDDING: ["nomic-embed-text"],
        TaskType.GENERAL: ["kimi"],
    }
    
    # Tier priority order (local first for cost, then free, then paid)
    TIER_PRIORITY = [Tier.LOCAL, Tier.FREE, Tier.PAID]
    
    def __init__(self, catalog: Optional[Dict[str, Any]] = None):
        """Initialize router with model catalog.
        
        Args:
            catalog: Pre-loaded catalog or None to load from disk
        """
        self._catalog = catalog or load_catalog()
        self._models = self._catalog.get("models", {})
        self._criteria = self._catalog.get("criteria", {})
        self._tiers = self._criteria.get("tiers", {})
    
    def _get_models_in_tier(self, tier: Tier) -> Set[str]:
        """Get all model IDs for a given tier."""
        return set(self._tiers.get(tier.value, []))
    
    def _estimate_complexity(self, estimated_tokens: int) -> str:
        """Estimate task complexity from token count."""
        if estimated_tokens < self.SIMPLE_TOKEN_THRESHOLD:
            return "simple"
        elif estimated_tokens < self.MEDIUM_TOKEN_THRESHOLD:
            return "medium"
        return "complex"
    
    def _requires_long_context(self, estimated_tokens: int) -> bool:
        """Check if task requires long context support."""
        return estimated_tokens > self.LONG_CONTEXT_THRESHOLD
    
    def _get_model_tier(self, model_id: str) -> Optional[Tier]:
        """Determine which tier a model belongs to."""
        for tier in Tier:
            if model_id in self._get_models_in_tier(tier):
                return tier
        return None
    
    def _get_model_cost(self, model_id: str) -> float:
        """Get estimated cost per 1K tokens for a model."""
        entry = get_model_entry(model_id, self._catalog)
        if not entry:
            return float('inf')
        cost = entry.get("cost", {})
        # Sum input + output cost as proxy
        return cost.get("input", 0) + cost.get("output", 0)
    
    def _get_model_context_window(self, model_id: str) -> int:
        """Get context window size for a model."""
        entry = get_model_entry(model_id, self._catalog)
        if not entry:
            return 0
        return entry.get("contextWindow", 0)
    
    def _can_handle_tokens(self, model_id: str, token_count: int) -> bool:
        """Check if model can handle the estimated token count."""
        context_window = self._get_model_context_window(model_id)
        # Leave 20% buffer for output tokens
        return context_window > 0 and token_count <= int(context_window * 0.8)
    
    def select_for_task(
        self,
        task_type: str = "default",
        estimated_tokens: int = 1000,
        focus: Optional[str] = None,
        require_reasoning: bool = False,
        prefer_local: bool = True,
    ) -> RoutingDecision:
        """Select the best model for a given task.
        
        Args:
            task_type: Type of task (code_generation, complex_reasoning, etc.)
            estimated_tokens: Estimated token count for the task
            focus: Agent focus type (orchestrator, devsecops, etc.)
            require_reasoning: Whether reasoning/thinking mode is required
            prefer_local: Prefer local models over cloud when possible
            
        Returns:
            RoutingDecision with selected model and metadata
        """
        # Normalize task type
        try:
            task_enum = TaskType(task_type)
        except ValueError:
            task_enum = TaskType.GENERAL
        
        candidates: List[tuple[str, Tier, float, str]] = []
        
        # Get focus default if specified
        if focus:
            focus_model = get_focus_default(focus, self._catalog)
            if focus_model and self._can_handle_tokens(focus_model, estimated_tokens):
                tier = self._get_model_tier(focus_model) or Tier.FREE
                cost = self._get_model_cost(focus_model)
                candidates.append((
                    focus_model,
                    tier,
                    cost,
                    f"focus default for {focus}"
                ))
        
        # Get task-specific preferences
        preferred_models = self.TASK_PREFERENCES.get(task_enum, [])
        
        # Filter by context window capacity
        for model_id in preferred_models:
            if not self._can_handle_tokens(model_id, estimated_tokens):
                continue
            
            # Check reasoning requirement
            entry = get_model_entry(model_id, self._catalog)
            if require_reasoning and not entry.get("reasoning", False):
                continue
            
            tier = self._get_model_tier(model_id)
            if tier is None:
                continue
                
            cost = self._get_model_cost(model_id)
            candidates.append((
                model_id,
                tier,
                cost,
                f"task preference ({task_type})"
            ))
        
        # If long context needed, ensure we have capable models
        if self._requires_long_context(estimated_tokens):
            long_context_models = self.TASK_PREFERENCES[TaskType.LONG_CONTEXT]
            for model_id in long_context_models:
                if not self._can_handle_tokens(model_id, estimated_tokens):
                    continue
                if any(c[0] == model_id for c in candidates):
                    continue  # Already in candidates
                    
                tier = self._get_model_tier(model_id)
                if tier:
                    cost = self._get_model_cost(model_id)
                    candidates.append((
                        model_id,
                        tier,
                        cost,
                        "long context requirement"
                    ))
        
        # Sort candidates by: tier priority, then cost
        def sort_key(candidate: tuple) -> tuple:
            model_id, tier, cost, _ = candidate
            tier_order = self.TIER_PRIORITY.index(tier)
            # If not prefer_local, reverse tier order for paid models
            if not prefer_local and tier == Tier.PAID:
                tier_order = -1  # Prioritize paid when prefer_local=False
            return (tier_order, cost)
        
        candidates.sort(key=sort_key)
        
        if not candidates:
            # Fallback to routing.primary from config
            primary = self._catalog.get("routing", {}).get("primary", "litellm/kimi")
            model_id = primary.split("/")[-1] if "/" in primary else primary
            return RoutingDecision(
                model_id=model_id,
                provider_prefix="litellm",
                tier=Tier.PAID,
                reason="fallback to primary routing",
                estimated_cost=self._get_model_cost(model_id)
            )
        
        selected = candidates[0]
        model_id, tier, cost, reason = selected
        
        return RoutingDecision(
            model_id=model_id,
            provider_prefix="litellm",
            tier=tier,
            reason=reason,
            estimated_cost=cost
        )
    
    def get_fallback_chain(
        self,
        primary_model: str,
        estimated_tokens: int = 1000,
        max_fallbacks: int = 3
    ) -> List[str]:
        """Get a fallback chain for a primary model selection.
        
        Args:
            primary_model: The primary model ID
            estimated_tokens: Token count requirements
            max_fallbacks: Maximum number of fallback models
            
        Returns:
            List of fallback model IDs (litellm/ prefixed)
        """
        fallbacks: List[str] = []
        
        # Get routing fallback list from config
        routing_fallbacks = self._catalog.get("routing", {}).get("fallbacks", [])
        
        for fb in routing_fallbacks:
            model_id = fb.split("/")[-1] if "/" in fb else fb
            
            # Skip primary if it appears in fallbacks
            if model_id == primary_model:
                continue
            
            # Check if it can handle the tokens
            if not self._can_handle_tokens(model_id, estimated_tokens):
                continue
            
            fallbacks.append(f"litellm/{model_id}")
            
            if len(fallbacks) >= max_fallbacks:
                break
        
        return fallbacks
    
    def build_complete_routing(
        self,
        task_type: str = "default",
        estimated_tokens: int = 1000,
        focus: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build complete routing configuration for a task.
        
        Returns dict compatible with OpenClaw agent routing format:
        {
            "primary": "litellm/model-id",
            "fallbacks": ["litellm/fallback-1", ...],
            "metadata": {...}
        }
        """
        decision = self.select_for_task(
            task_type=task_type,
            estimated_tokens=estimated_tokens,
            focus=focus
        )
        
        fallbacks = self.get_fallback_chain(
            primary_model=decision.model_id,
            estimated_tokens=estimated_tokens
        )
        
        return {
            "primary": f"litellm/{decision.model_id}",
            "fallbacks": fallbacks,
            "metadata": {
                "tier": decision.tier.value,
                "reason": decision.reason,
                "estimated_cost_per_1k": decision.estimated_cost,
            }
        }


# Convenience function for direct usage
def select_model(
    task_type: str = "default",
    estimated_tokens: int = 1000,
    focus: Optional[str] = None,
    require_reasoning: bool = False,
) -> str:
    """Quick-select a model for a task.
    
    Returns the full litellm/ prefixed model ID.
    """
    router = ModelRouter()
    decision = router.select_for_task(
        task_type=task_type,
        estimated_tokens=estimated_tokens,
        focus=focus,
        require_reasoning=require_reasoning
    )
    return f"litellm/{decision.model_id}"


def get_routing_for_agent(
    focus: str,
    task_type: str = "default",
    estimated_tokens: int = 1000,
) -> Dict[str, Any]:
    """Get complete routing config for an agent focus.
    
    Example:
        >>> get_routing_for_agent("devsecops", "code_generation", 2000)
        {
            'primary': 'litellm/qwen3-coder-free',
            'fallbacks': ['litellm/qwen3-next-free', 'litellm/kimi'],
            'metadata': {...}
        }
    """
    router = ModelRouter()
    return router.build_complete_routing(
        task_type=task_type,
        estimated_tokens=estimated_tokens,
        focus=focus
    )
