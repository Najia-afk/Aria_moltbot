# aria_skills/model_switcher.py
"""
Model Switcher Skill - Switch between Ollama models at runtime.

Aria can switch between GLM (smart text) and Qwen3-VL (vision) models
without OpenClaw/LiteLLM needing to know. Ollama serves any loaded model
per-request, so we just update the preference.

This skill allows Aria to:
- List available models in Ollama
- Switch active model for subsequent LLM calls
- Pull new models if needed
- Check current model status
"""
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus
from aria_skills.registry import SkillRegistry

# Shared state file for model preference (persists across restarts)
MODEL_STATE_FILE = Path("/root/.openclaw/workspace/memory/model_preference.json")


def _read_model_preference() -> Optional[str]:
    """Read current model preference from shared state file."""
    if MODEL_STATE_FILE.exists():
        try:
            data = json.loads(MODEL_STATE_FILE.read_text())
            return data.get("current_model")
        except Exception:
            pass
    return None


def _write_model_preference(model: str) -> None:
    """Write model preference to shared state file."""
    MODEL_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    MODEL_STATE_FILE.write_text(json.dumps({
        "current_model": model,
        "updated_by": "model_switcher",
    }))


@SkillRegistry.register
class ModelSwitcherSkill(BaseSkill):
    """
    Switch between Ollama models at runtime.
    
    Ollama can serve any loaded model per-request. This skill:
    - Lists available models
    - Sets the active model preference (stored in file + env)
    - Pulls new models if needed
    
    Supported models (aliases):
    - glm: GLM-4.7-Flash-REAP (smart, text-focused, default)
    - qwen3-vl: Qwen3-VL 8B (vision capable, for image tasks)
    - qwen2.5: Qwen2.5 7B (backup text model)
    """
    
    # Model aliases -> full Ollama model names
    MODELS = {
        "glm": "hf.co/unsloth/GLM-4.7-Flash-REAP-23B-A3B-GGUF:Q3_K_S",
        "qwen3-vl": "qwen3-vl:8b",
        "qwen2.5": "qwen2.5:7b",
    }
    
    # Reverse mapping for display
    MODEL_ALIASES = {v: k for k, v in MODELS.items()}
    
    def __init__(self, config: SkillConfig):
        super().__init__(config)
        self._base_url = os.getenv(
            "OLLAMA_URL",
            config.config.get("url", "http://host.docker.internal:11434"),
        )
        # Read from shared state first, then env, then default to GLM
        self._current_model = (
            _read_model_preference()
            or os.getenv("OLLAMA_MODEL")
            or self.MODELS["glm"]
        )
    
    @property
    def name(self) -> str:
        return "model_switcher"
    
    async def initialize(self) -> bool:
        """Initialize connection to Ollama."""
        status = await self.health_check()
        return status == SkillStatus.AVAILABLE
    
    async def health_check(self) -> SkillStatus:
        """Check Ollama is reachable."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self._base_url}/api/tags",
                    timeout=5,
                )
                if response.status_code == 200:
                    self._status = SkillStatus.AVAILABLE
                else:
                    self._status = SkillStatus.UNAVAILABLE
        except Exception as e:
            self.logger.error(f"Ollama not reachable: {e}")
            self._status = SkillStatus.UNAVAILABLE
        return self._status
    
    async def list_models(self) -> SkillResult:
        """
        List all available Ollama models.
        
        Returns:
            SkillResult with:
            - models: List of installed models with name/size
            - current: Currently active model
            - aliases: Available shorthand aliases
        """
        if not self.is_available:
            return SkillResult.fail("Ollama not available")
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self._base_url}/api/tags",
                    timeout=10,
                )
                
                if response.status_code == 200:
                    data = response.json()
                    models = []
                    for m in data.get("models", []):
                        name = m["name"]
                        alias = self.MODEL_ALIASES.get(name, None)
                        models.append({
                            "name": name,
                            "alias": alias,
                            "size_gb": round(m.get("size", 0) / 1e9, 2),
                            "modified": m.get("modified_at", ""),
                        })
                    
                    # Get current alias if exists
                    current_alias = self.MODEL_ALIASES.get(self._current_model)
                    
                    self._log_usage("list_models", True)
                    return SkillResult.ok({
                        "models": models,
                        "current": self._current_model,
                        "current_alias": current_alias,
                        "available_aliases": list(self.MODELS.keys()),
                    })
                else:
                    return SkillResult.fail(f"HTTP {response.status_code}")
        except Exception as e:
            self._log_usage("list_models", False)
            return SkillResult.fail(str(e))
    
    async def switch_model(self, model: str) -> SkillResult:
        """
        Switch the active Ollama model.
        
        Args:
            model: Model name or alias (glm, qwen3-vl, qwen2.5) or full name
            
        Returns:
            SkillResult with previous and new active model
            
        Example:
            switch_model("glm")       -> Switch to GLM-4.7
            switch_model("qwen3-vl")  -> Switch to Qwen3-VL for vision
        """
        if not self.is_available:
            return SkillResult.fail("Ollama not available")
        
        # Resolve alias to full name
        target_model = self.MODELS.get(model.lower(), model)
        
        # Verify model is available in Ollama
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self._base_url}/api/tags",
                    timeout=10,
                )
                
                if response.status_code == 200:
                    data = response.json()
                    available = [m["name"] for m in data.get("models", [])]
                    
                    # Check if model is loaded (partial match for GGUF names)
                    model_base = target_model.split(":")[0]
                    found = any(model_base in m for m in available)
                    
                    if not found:
                        return SkillResult.fail(
                            f"Model '{target_model}' not found in Ollama. "
                            f"Available: {available}. "
                            f"Use pull_model to download it first."
                        )
                    
                    # Update preference
                    old_model = self._current_model
                    old_alias = self.MODEL_ALIASES.get(old_model)
                    
                    self._current_model = target_model
                    new_alias = self.MODEL_ALIASES.get(target_model)
                    
                    # Persist to shared state file
                    _write_model_preference(target_model)
                    
                    # Also update environment for current process
                    os.environ["OLLAMA_MODEL"] = target_model
                    
                    self._log_usage("switch_model", True)
                    return SkillResult.ok({
                        "previous": old_model,
                        "previous_alias": old_alias,
                        "current": target_model,
                        "current_alias": new_alias,
                        "message": f"Switched from {old_alias or old_model} to {new_alias or target_model}",
                    })
                else:
                    return SkillResult.fail(f"HTTP {response.status_code}")
        except Exception as e:
            self._log_usage("switch_model", False)
            return SkillResult.fail(str(e))
    
    async def pull_model(self, model: str) -> SkillResult:
        """
        Pull/download a model to Ollama.
        
        Args:
            model: Model name or alias to pull
            
        Returns:
            SkillResult with pull status
            
        Note: This can take several minutes for large models.
        """
        if not self.is_available:
            return SkillResult.fail("Ollama not available")
        
        # Resolve alias
        target_model = self.MODELS.get(model.lower(), model)
        
        try:
            async with httpx.AsyncClient() as client:
                # Ollama pull can take a long time for large models
                response = await client.post(
                    f"{self._base_url}/api/pull",
                    json={"name": target_model, "stream": False},
                    timeout=1200,  # 20 minutes for large models
                )
                
                if response.status_code == 200:
                    self._log_usage("pull_model", True)
                    return SkillResult.ok({
                        "model": target_model,
                        "alias": self.MODEL_ALIASES.get(target_model),
                        "status": "pulled",
                        "message": f"Successfully pulled {target_model}",
                    })
                else:
                    self._log_usage("pull_model", False)
                    return SkillResult.fail(
                        f"Pull failed: HTTP {response.status_code} - {response.text}"
                    )
        except httpx.TimeoutException:
            return SkillResult.fail(
                "Pull timed out after 20 minutes. "
                "Try pulling directly: ollama pull " + target_model
            )
        except Exception as e:
            self._log_usage("pull_model", False)
            return SkillResult.fail(str(e))
    
    async def get_current_model(self) -> SkillResult:
        """
        Get the currently active model.
        
        Returns:
            SkillResult with current model and alias
        """
        alias = self.MODEL_ALIASES.get(self._current_model)
        env_model = os.getenv("OLLAMA_MODEL", "not set")
        file_model = _read_model_preference()
        
        return SkillResult.ok({
            "current": self._current_model,
            "alias": alias,
            "env_var": env_model,
            "state_file": file_model,
            "available_aliases": self.MODELS,
        })
