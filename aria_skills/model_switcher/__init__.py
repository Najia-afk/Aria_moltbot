# aria_skills/model_switcher.py
"""
Model switching skill.

Allows Aria to switch between different LLM backends at runtime.
Supports thinking mode toggle for reasoning models.
"""
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus
from aria_skills.registry import SkillRegistry


@SkillRegistry.register
class ModelSwitcherSkill(BaseSkill):
    """
    Runtime model switching with thinking mode control.
    
    Manages which LLM backend Aria uses for different tasks.
    Supports toggling thinking/reasoning mode on supported models.
    
    Config:
        default_model: Default model identifier
        available_models: List of available model configs
        thinking_enabled: Whether thinking mode is enabled (default: True)
    """
    
    def __init__(self, config: SkillConfig):
        super().__init__(config)
        self._current_model: Optional[str] = None
        self._available_models: Dict[str, Dict] = {}
        self._usage_history: List[Dict] = []
        self._thinking_enabled: bool = True  # Default: thinking ON
    
    @property
    def name(self) -> str:
        return "model_switcher"
    
    async def initialize(self) -> bool:
        """Initialize model switcher."""
        # Load available models from config
        models = self.config.config.get("available_models", [])
        
        for model in models:
            model_id = model.get("id")
            if model_id:
                self._available_models[model_id] = model
        
        # Set default if specified
        default = self.config.config.get("default_model")
        if default and default in self._available_models:
            self._current_model = default
        elif self._available_models:
            self._current_model = list(self._available_models.keys())[0]
        
        # Initialize thinking mode from config
        self._thinking_enabled = self.config.config.get("thinking_enabled", True)
        
        self._status = SkillStatus.AVAILABLE
        self.logger.info(f"Model switcher initialized with {len(self._available_models)} models, thinking={self._thinking_enabled}")
        return True
    
    async def health_check(self) -> SkillStatus:
        """Check switcher availability."""
        return self._status
    
    async def get_current_model(self) -> SkillResult:
        """Get current model information."""
        if not self._current_model:
            return SkillResult.fail("No model selected")
        
        model_config = self._available_models.get(self._current_model, {})
        
        return SkillResult.ok({
            "current_model": self._current_model,
            "config": model_config,
            "thinking_enabled": self._thinking_enabled,
            "available_models": list(self._available_models.keys()),
        })
    
    async def switch_model(
        self,
        model_id: str,
        reason: Optional[str] = None,
    ) -> SkillResult:
        """
        Switch to a different model.
        
        Args:
            model_id: Target model identifier
            reason: Optional reason for switching
            
        Returns:
            SkillResult with switch confirmation
        """
        if model_id not in self._available_models:
            return SkillResult.fail(f"Unknown model: {model_id}. Available: {list(self._available_models.keys())}")
        
        previous = self._current_model
        self._current_model = model_id
        
        # Log switch
        self._usage_history.append({
            "from": previous,
            "to": model_id,
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat(),
        })
        
        # Keep history manageable
        if len(self._usage_history) > 100:
            self._usage_history = self._usage_history[-100:]
        
        return SkillResult.ok({
            "previous_model": previous,
            "current_model": model_id,
            "reason": reason,
            "config": self._available_models[model_id],
        })
    
    async def list_models(self) -> SkillResult:
        """List all available models."""
        models = []
        
        for model_id, config in self._available_models.items():
            models.append({
                "id": model_id,
                "name": config.get("name", model_id),
                "type": config.get("type", "unknown"),
                "is_current": model_id == self._current_model,
                "capabilities": config.get("capabilities", []),
                "cost_tier": config.get("cost_tier", "unknown"),
            })
        
        return SkillResult.ok({
            "models": models,
            "current": self._current_model,
            "total": len(models),
        })
    
    async def register_model(
        self,
        model_id: str,
        config: Dict[str, Any],
    ) -> SkillResult:
        """
        Register a new model at runtime.
        
        Args:
            model_id: Unique model identifier
            config: Model configuration
            
        Returns:
            SkillResult with registration confirmation
        """
        if model_id in self._available_models:
            return SkillResult.fail(f"Model {model_id} already registered")
        
        self._available_models[model_id] = config
        
        return SkillResult.ok({
            "model_id": model_id,
            "config": config,
            "total_models": len(self._available_models),
        })
    
    async def get_model_for_task(self, task_type: str) -> SkillResult:
        """
        Get recommended model for a task type.
        
        Args:
            task_type: Type of task (coding, creative, analysis, etc.)
            
        Returns:
            SkillResult with recommended model
        """
        # Simple matching based on capabilities
        for model_id, config in self._available_models.items():
            capabilities = config.get("capabilities", [])
            if task_type in capabilities:
                return SkillResult.ok({
                    "task_type": task_type,
                    "recommended_model": model_id,
                    "config": config,
                    "match_type": "capability_match",
                })
        
        # Fallback to current model
        return SkillResult.ok({
            "task_type": task_type,
            "recommended_model": self._current_model,
            "config": self._available_models.get(self._current_model, {}),
            "match_type": "fallback",
        })
    
    async def get_switch_history(self, limit: int = 10) -> SkillResult:
        """Get recent model switch history."""
        return SkillResult.ok({
            "history": self._usage_history[-limit:],
            "total_switches": len(self._usage_history),
            "current_model": self._current_model,
        })

    async def set_thinking_mode(
        self,
        enabled: bool,
        reason: Optional[str] = None,
    ) -> SkillResult:
        """
        Toggle thinking/reasoning mode for supported models.
        
        When enabled (default), reasoning models show their <think>...</think> process.
        When disabled (/no_think), models skip reasoning for faster, cheaper responses.
        
        Args:
            enabled: True for thinking mode, False for no_think mode
            reason: Optional reason for the change
            
        Returns:
            SkillResult with thinking mode status
        """
        previous = self._thinking_enabled
        self._thinking_enabled = enabled
        
        mode_name = "thinking" if enabled else "no_think"
        
        # Log the change
        self._usage_history.append({
            "type": "thinking_mode_change",
            "from": "thinking" if previous else "no_think",
            "to": mode_name,
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat(),
        })
        
        self.logger.info(f"Thinking mode changed to {mode_name}: {reason}")
        
        return SkillResult.ok({
            "thinking_enabled": self._thinking_enabled,
            "mode": mode_name,
            "previous_mode": "thinking" if previous else "no_think",
            "reason": reason,
            "hint": "Use thinking=True for complex tasks (code, math, analysis). Use thinking=False for simple queries (status, facts).",
        })

    async def get_thinking_mode(self) -> SkillResult:
        """
        Get current thinking mode status.
        
        Returns:
            SkillResult with thinking mode info
        """
        mode_name = "thinking" if self._thinking_enabled else "no_think"
        
        return SkillResult.ok({
            "thinking_enabled": self._thinking_enabled,
            "mode": mode_name,
            "current_model": self._current_model,
            "supported_models": [
                "deepseek-free",   # DeepSeek R1 - native thinking
                "chimera-free",    # R1T2 Chimera - reasoning
                "qwen3-mlx",       # Qwen3 - /think support
                "qwen3-coder-free", # Qwen3 Coder - /think support
                "qwen3-next-free", # Qwen3 Next - /think support
                "glm-free",        # GLM 4.5 - thinking mode
            ],
            "usage": {
                "thinking_on": "Complex reasoning, code review, math, analysis, debugging",
                "thinking_off": "Simple queries, status checks, facts, faster responses",
            },
        })

    def get_thinking_prefix(self) -> str:
        """
        Get the prompt prefix for current thinking mode.
        
        Returns:
            Empty string if thinking enabled, '/no_think' if disabled
        """
        return "" if self._thinking_enabled else "/no_think "
