# aria_skills/llm.py
"""
LLM skills for Gemini and Moonshot.

Handles model selection, prompting, and response parsing.
"""
import os
from abc import abstractmethod
from typing import Any, Dict, List, Optional

import httpx

from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus
from aria_skills.registry import SkillRegistry


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
class GeminiSkill(BaseLLMSkill):
    """
    Google Gemini API skill.
    
    Config:
        api_key: Gemini API key (use env:GOOGLE_GEMINI_KEY)
        model: Model name (default: gemini-3-flash)
        
    Uses:
        - General conversation
        - Fact-based answers
        - Social media content
    """
    
    MODELS = {
        "gemini-3-pro": "Most capable",
        "gemini-3-flash": "Fast, efficient (recommended)",
        "gemini-2.5-flash": "Strong quality/speed",
        "gemini-2.0-flash": "Stable, fast",
        "gemini-banana": "Alias (experimental)",
    }
    
    def __init__(self, config: SkillConfig):
        super().__init__(config)
        self._model = config.config.get("model", "gemini-3-flash")
        self._base_url = "https://generativelanguage.googleapis.com/v1beta"
    
    @property
    def name(self) -> str:
        return "gemini"
    
    async def initialize(self) -> bool:
        """Initialize Gemini API."""
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
                    params={"key": self._api_key},
                    timeout=10,
                )
                
                if response.status_code == 200:
                    self._status = SkillStatus.AVAILABLE
                elif response.status_code == 401:
                    self.logger.error("Invalid API key")
                    self._status = SkillStatus.UNAVAILABLE
                elif response.status_code == 429:
                    self._status = SkillStatus.RATE_LIMITED
                else:
                    self._status = SkillStatus.ERROR
                    
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
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
        Generate content with Gemini.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system instruction
            temperature: Creativity (0-1)
            max_tokens: Max response length
            
        Returns:
            SkillResult with generated text
        """
        if not self.is_available:
            return SkillResult.fail("Gemini not available")
        
        # Build content
        contents = []
        if system_prompt:
            contents.append({"role": "user", "parts": [{"text": system_prompt}]})
            contents.append({"role": "model", "parts": [{"text": "Understood."}]})
        contents.append({"role": "user", "parts": [{"text": prompt}]})
        
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self._base_url}/models/{self._model}:generateContent",
                    params={"key": self._api_key},
                    json=payload,
                    timeout=60,
                )
                
                if response.status_code == 200:
                    data = response.json()
                    text = data["candidates"][0]["content"]["parts"][0]["text"]
                    self._log_usage("generate", True)
                    
                    return SkillResult.ok({
                        "text": text,
                        "model": self._model,
                        "usage": data.get("usageMetadata", {}),
                    })
                elif response.status_code == 429:
                    self._status = SkillStatus.RATE_LIMITED
                    return SkillResult.fail("Rate limited")
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
        Multi-turn chat with Gemini.
        
        Args:
            messages: List of {"role": "user"|"model", "content": "..."}
            temperature: Creativity (0-1)
            max_tokens: Max response length
            
        Returns:
            SkillResult with model response
        """
        if not self.is_available:
            return SkillResult.fail("Gemini not available")
        
        # Convert to Gemini format
        contents = [
            {"role": msg["role"], "parts": [{"text": msg["content"]}]}
            for msg in messages
        ]
        
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self._base_url}/models/{self._model}:generateContent",
                    params={"key": self._api_key},
                    json=payload,
                    timeout=60,
                )
                
                if response.status_code == 200:
                    data = response.json()
                    text = data["candidates"][0]["content"]["parts"][0]["text"]
                    self._log_usage("chat", True)
                    
                    return SkillResult.ok({
                        "text": text,
                        "model": self._model,
                    })
                else:
                    self._log_usage("chat", False)
                    return SkillResult.fail(f"HTTP {response.status_code}")
                    
        except Exception as e:
            self._log_usage("chat", False)
            return SkillResult.fail(str(e))


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
    - qwen3-vl:8b (default) - Vision capable, local, free (as per SOUL.md)
    - Falls back to cloud APIs only when local unavailable
    
    Config:
        url: Ollama server URL (default: http://ollama:11434)
        model: Model name (default from env:OLLAMA_MODEL or qwen3-vl:8b)
        
    This is Aria's primary thinking engine - local, private, fast.
    """
    
    MODELS = {
        "qwen3-vl:8b": "Default - vision capable, local/free (SOUL.md)",
        "qwen2.5:14b": "Higher quality text, slower",
        "llama3.2:8b": "Alternative general model",
        "codellama:7b": "Code-focused tasks",
    }
    
    def __init__(self, config: SkillConfig):
        super().__init__(config)
        # Respect environment config first, then SOUL.md defaults
        self._model = os.getenv("OLLAMA_MODEL", config.config.get("model", "qwen3-vl:8b"))
        self._base_url = os.getenv("OLLAMA_URL", config.config.get("url", "http://ollama:11434"))
    
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
