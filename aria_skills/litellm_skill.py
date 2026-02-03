# aria_skills/litellm_skill.py
"""
LiteLLM proxy management skill.
"""
import logging
from typing import Any, Dict, Optional

import httpx

from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus
from aria_skills.registry import SkillRegistry

logger = logging.getLogger("aria.skills.litellm")


@SkillRegistry.register
class LiteLLMSkill(BaseSkill):
    """
    Skill for managing LiteLLM proxy and tracking spend.
    """
    
    name = "litellm"
    description = "Manage LiteLLM proxy, models, and API spend tracking"
    
    def __init__(self, config: SkillConfig):
        super().__init__(config)
        self.api_base = config.config.get("api_url", "http://aria-api:8000")
    
    async def initialize(self) -> bool:
        """Initialize the skill."""
        status = await self.health_check()
        return status == SkillStatus.AVAILABLE
    
    async def health_check(self) -> SkillStatus:
        """Check if LiteLLM is accessible."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.api_base}/litellm/health", timeout=5.0)
                if response.status_code == 200:
                    return SkillStatus.AVAILABLE
                return SkillStatus.ERROR
        except Exception as e:
            logger.error(f"LiteLLM health check failed: {e}")
            return SkillStatus.UNAVAILABLE
    
    async def models(self) -> SkillResult:
        """
        List available models from LiteLLM proxy.
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_base}/litellm/models",
                    timeout=10.0
                )
                response.raise_for_status()
                return SkillResult(success=True, data=response.json())
        except Exception as e:
            logger.error(f"Failed to get models: {e}")
            return SkillResult(success=False, error=str(e))
    
    async def health(self) -> SkillResult:
        """
        Check LiteLLM proxy health status.
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_base}/litellm/health",
                    timeout=10.0
                )
                response.raise_for_status()
                return SkillResult(success=True, data=response.json())
        except Exception as e:
            logger.error(f"LiteLLM health check failed: {e}")
            return SkillResult(success=False, error=str(e))
    
    async def spend(
        self,
        limit: int = 50,
        model: Optional[str] = None
    ) -> SkillResult:
        """
        Get API spend logs.
        
        Args:
            limit: Maximum log entries
            model: Filter by model name
        """
        try:
            params = {"limit": limit}
            if model:
                params["model"] = model
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_base}/litellm/spend",
                    params=params,
                    timeout=10.0
                )
                response.raise_for_status()
                return SkillResult(success=True, data=response.json())
        except Exception as e:
            logger.error(f"Failed to get spend logs: {e}")
            return SkillResult(success=False, error=str(e))
    
    async def global_spend(self) -> SkillResult:
        """
        Get global spend summary across all models.
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_base}/litellm/global-spend",
                    timeout=10.0
                )
                response.raise_for_status()
                return SkillResult(success=True, data=response.json())
        except Exception as e:
            logger.error(f"Failed to get global spend: {e}")
            return SkillResult(success=False, error=str(e))
    
    async def provider_balances(self) -> SkillResult:
        """
        Get wallet balances from all configured providers.
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_base}/providers/balances",
                    timeout=10.0
                )
                response.raise_for_status()
                return SkillResult(success=True, data=response.json())
        except Exception as e:
            logger.error(f"Failed to get provider balances: {e}")
            return SkillResult(success=False, error=str(e))
