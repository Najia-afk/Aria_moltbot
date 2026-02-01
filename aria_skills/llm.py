# aria_skills/llm.py
"""LLM skills for Moonshot and Ollama.

Handles model selection, prompting, and response parsing.
"""
import json
import os
from abc import abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus
from aria_skills.registry import SkillRegistry

# Shared state file for model preference (used by model_switcher skill)
MODEL_STATE_FILE = Path("/root/.openclaw/workspace/memory/model_preference.json")


def _get_active_model() -> Optional[str]:
    """
    Get active model from shared state file.
    
    This allows the model_switcher skill to change models at runtime
    without requiring container restarts.
    """
    if MODEL_STATE_FILE.exists():
        try:
            data = json.loads(MODEL_STATE_FILE.read_text())
            return data.get("current_model")
        except Exception:
            pass
    return None


class BaseLLMSkill(BaseSkill):
    """Base class for LLM skills."""
    
    def __init__(self, config: SkillConfig):
        super().__init__(config)
        self._api_key: Optional[str] = None
    
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> SkillResult:
        """Generate a response from the model."""
        pass
    
    @abstractmethod
    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> SkillResult:
        """Multi-turn chat with the model."""
        pass


@SkillRegistry.register
class MoonshotSkill(BaseLLMSkill):
    """
    Moonshot AI (Kimi) API skill.
    
    Config:
        api_key: Moonshot API key (use env:MOONSHOT_KIMI_KEY)
        model: Model name (default: kimi-k2.5)
        base_url: Optional API base URL (default: https://api.moonshot.ai/v1)
        
    Uses:
        - Long context (up to 128k tokens)
        - Chinese language tasks
        - Code generation
    """
    
    MODELS = {
        "kimi-k2.5": "Latest balanced model",
        "kimi-k2-0905-preview": "Preview model",
        "kimi-k2-turbo-preview": "Fast preview",
        "kimi-k2-thinking": "Reasoning-focused",
        "kimi-k2-thinking-turbo": "Reasoning + speed",
    }
    
    def __init__(self, config: SkillConfig):
        super().__init__(config)
        self._model = config.config.get("model", "kimi-k2.5")
        self._base_url = os.getenv(
            "MOONSHOT_BASE_URL",
            config.config.get("base_url", "https://api.moonshot.ai/v1"),
        )
    
    @property
    def name(self) -> str:
        return "moonshot"
    
    async def initialize(self) -> bool:
        """Initialize Moonshot API."""
        self._api_key = self._get_env_value("api_key")
        
        if not self._api_key:
            self.logger.error("No API key configured")
            self._status = SkillStatus.UNAVAILABLE
            return False
        
        status = await self.health_check()
        return status == SkillStatus.AVAILABLE
    
    async def health_check(self) -> SkillStatus:
        """Verify API key works."""
        if not self._api_key:
            self._status = SkillStatus.UNAVAILABLE
            return self._status
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self._base_url}/models",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    timeout=10,
                )
                
                if response.status_code == 200:
                    self._status = SkillStatus.AVAILABLE
                elif response.status_code == 401:
                    self.logger.error("Invalid API key")
                    self._status = SkillStatus.UNAVAILABLE
                else:
                    self._status = SkillStatus.ERROR
                    
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            self._status = SkillStatus.ERROR
        
        return self._status
    
    @property
    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> SkillResult:
        """
        Generate content with Moonshot.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system instruction
            temperature: Creativity (0-1)
            max_tokens: Max response length
            
        Returns:
            SkillResult with generated text
        """
        if not self.is_available:
            return SkillResult.fail("Moonshot not available")
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        return await self.chat(messages, temperature, max_tokens)
    
    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> SkillResult:
        """
        Multi-turn chat with Moonshot.
        
        Args:
            messages: List of {"role": "system"|"user"|"assistant", "content": "..."}
            temperature: Creativity (0-1)
            max_tokens: Max response length
            
        Returns:
            SkillResult with model response
        """
        if not self.is_available:
            return SkillResult.fail("Moonshot not available")
        
        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers=self._headers,
                    json=payload,
                    timeout=60,
                )
                
                if response.status_code == 200:
                    data = response.json()
                    text = data["choices"][0]["message"]["content"]
                    self._log_usage("chat", True)
                    
                    return SkillResult.ok({
                        "text": text,
                        "model": self._model,
                        "usage": data.get("usage", {}),
                    })
                elif response.status_code == 429:
                    self._status = SkillStatus.RATE_LIMITED
                    return SkillResult.fail("Rate limited")
                else:
                    self._log_usage("chat", False)
                    return SkillResult.fail(f"HTTP {response.status_code}: {response.text}")
                    
        except Exception as e:
            self._log_usage("chat", False)
            return SkillResult.fail(str(e))


@SkillRegistry.register
class OllamaSkill(BaseLLMSkill):
    """
    Ollama local LLM skill - Aria's DEFAULT brain.
    
    Per SOUL.md, local models are preferred:
    - GLM-4.7-Flash-REAP (default) - Smart text model
    - qwen3-vl:8b - Vision capable, for image tasks
    - Falls back to cloud APIs only when local unavailable
    
    Model can be switched at runtime via model_switcher skill.
    
    Config:
        url: Ollama server URL (default: http://ollama:11434)
        model: Model name (reads from shared state, then env:OLLAMA_MODEL, then GLM default)
        
    This is Aria's primary thinking engine - local, private, fast.
    """
    
    MODELS = {
        "glm": "hf.co/unsloth/GLM-4.7-Flash-REAP-23B-A3B-GGUF:Q3_K_S",
        "qwen3-vl": "qwen3-vl:8b",
        "qwen2.5": "qwen2.5:7b",
    }
    
    def __init__(self, config: SkillConfig):
        super().__init__(config)
        self._base_url = os.getenv("OLLAMA_URL", config.config.get("url", "http://host.docker.internal:11434"))
        # Model is determined dynamically - see _get_model()
        self._config_model = config.config.get(
            "model",
            "hf.co/unsloth/GLM-4.7-Flash-REAP-23B-A3B-GGUF:Q3_K_S",
        )
    
    @property
    def _model(self) -> str:
        """
        Get current model - checks shared state first for runtime switching.
        
        Priority:
        1. Shared state file (set by model_switcher skill)
        2. OLLAMA_MODEL environment variable
        3. Config default (GLM-4.7)
        """
        # Check shared state file first (allows runtime switching)
        state_model = _get_active_model()
        if state_model:
            return state_model
        # Fall back to env var
        env_model = os.getenv("OLLAMA_MODEL")
        if env_model:
            return env_model
        # Finally use config default
        return self._config_model
    
    @property
    def name(self) -> str:
        return "ollama"
    
    async def initialize(self) -> bool:
        """Initialize Ollama connection."""
        status = await self.health_check()
        return status == SkillStatus.AVAILABLE
    
    async def health_check(self) -> SkillStatus:
        """Check if Ollama is running and model is available."""
        try:
            async with httpx.AsyncClient() as client:
                # Check server is up
                response = await client.get(
                    f"{self._base_url}/api/tags",
                    timeout=5,
                )
                
                if response.status_code == 200:
                    data = response.json()
                    models = [m["name"] for m in data.get("models", [])]
                    
                    # Check if our model is available
                    model_base = self._model.split(":")[0]
                    if any(model_base in m for m in models):
                        self._status = SkillStatus.AVAILABLE
                        self.logger.info(f"Ollama ready with {self._model}")
                    else:
                        self.logger.warning(f"Model {self._model} not found, available: {models}")
                        self._status = SkillStatus.UNAVAILABLE
                else:
                    self._status = SkillStatus.ERROR
                    
        except httpx.ConnectError:
            self.logger.debug("Ollama not reachable - will use cloud fallback")
            self._status = SkillStatus.UNAVAILABLE
        except Exception as e:
            self.logger.error(f"Ollama health check failed: {e}")
            self._status = SkillStatus.ERROR
        
        return self._status
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> SkillResult:
        """
        Generate content with local Ollama.
        
        This is Aria's preferred thinking method - private and local.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system instruction (Aria's SOUL)
            temperature: Creativity (0-1)
            max_tokens: Max response length
            
        Returns:
            SkillResult with generated text
        """
        if not self.is_available:
            return SkillResult.fail("Ollama not available")
        
        payload = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        
        if system_prompt:
            payload["system"] = system_prompt
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self._base_url}/api/generate",
                    json=payload,
                    timeout=120,  # Local models can be slow on first run
                )
                
                if response.status_code == 200:
                    data = response.json()
                    text = data.get("response", "")
                    self._log_usage("generate", True)
                    
                    return SkillResult.ok({
                        "text": text,
                        "model": self._model,
                        "local": True,  # Mark as local generation
                        "eval_count": data.get("eval_count", 0),
                    })
                else:
                    self._log_usage("generate", False)
                    return SkillResult.fail(f"HTTP {response.status_code}: {response.text}")
                    
        except Exception as e:
            self._log_usage("generate", False)
            return SkillResult.fail(str(e))
    
    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> SkillResult:
        """
        Multi-turn chat with local Ollama.
        
        Args:
            messages: List of {"role": "system"|"user"|"assistant", "content": "..."}
            temperature: Creativity (0-1)
            max_tokens: Max response length
            
        Returns:
            SkillResult with model response
        """
        if not self.is_available:
            return SkillResult.fail("Ollama not available")
        
        payload = {
            "model": self._model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self._base_url}/api/chat",
                    json=payload,
                    timeout=120,
                )
                
                if response.status_code == 200:
                    data = response.json()
                    text = data.get("message", {}).get("content", "")
                    self._log_usage("chat", True)
                    
                    return SkillResult.ok({
                        "text": text,
                        "model": self._model,
                        "local": True,
                    })
                else:
                    self._log_usage("chat", False)
                    return SkillResult.fail(f"HTTP {response.status_code}")
                    
        except Exception as e:
            self._log_usage("chat", False)
            return SkillResult.fail(str(e))
