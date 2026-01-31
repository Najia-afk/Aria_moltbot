# aria_skills/base.py
"""
Base classes for Aria skills.
"""
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class SkillStatus(Enum):
    """Skill availability status."""
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    RATE_LIMITED = "rate_limited"
    ERROR = "error"


@dataclass
class SkillConfig:
    """Configuration for a skill."""
    name: str
    enabled: bool = True
    config: dict = field(default_factory=dict)
    rate_limit: Optional[dict] = None
    
    @classmethod
    def from_dict(cls, data: dict) -> "SkillConfig":
        return cls(
            name=data.get("skill", data.get("name", "unknown")),
            enabled=data.get("enabled", True),
            config=data.get("config", {}),
            rate_limit=data.get("rate_limit"),
        )


@dataclass
class SkillResult:
    """Result from a skill operation."""
    success: bool
    data: Any = None
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    @classmethod
    def ok(cls, data: Any = None) -> "SkillResult":
        return cls(success=True, data=data)
    
    @classmethod
    def fail(cls, error: str) -> "SkillResult":
        return cls(success=False, error=error)


class BaseSkill(ABC):
    """
    Abstract base class for all skills.
    
    Skills must implement:
    - name: Unique skill identifier
    - initialize(): Setup and validation
    - health_check(): Verify availability
    """
    
    def __init__(self, config: SkillConfig):
        self.config = config
        self.logger = logging.getLogger(f"aria.skills.{self.name}")
        self._status = SkillStatus.UNAVAILABLE
        self._last_used: Optional[datetime] = None
        self._use_count = 0
        self._error_count = 0
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique skill identifier."""
        pass
    
    @abstractmethod
    async def initialize(self) -> bool:
        """
        Initialize the skill.
        Validate configuration, test connections, etc.
        
        Returns:
            True if initialization successful
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> SkillStatus:
        """
        Check if skill is available and healthy.
        
        Returns:
            Current skill status
        """
        pass
    
    @property
    def is_available(self) -> bool:
        """Check if skill is available for use."""
        return self._status == SkillStatus.AVAILABLE
    
    @property
    def status(self) -> SkillStatus:
        """Current skill status."""
        return self._status
    
    def _log_usage(self, operation: str, success: bool):
        """Log skill usage for metrics."""
        self._last_used = datetime.utcnow()
        self._use_count += 1
        if not success:
            self._error_count += 1
        
        self.logger.info(
            f"{operation}: {'success' if success else 'failed'} "
            f"(total: {self._use_count}, errors: {self._error_count})"
        )
    
    def _get_env_value(self, key: str) -> Optional[str]:
        """
        Get value from config, resolving env: prefix.
        
        Args:
            key: Config key to look up
            
        Returns:
            Resolved value or None
        """
        import os
        
        value = self.config.config.get(key)
        if value and isinstance(value, str) and value.startswith("env:"):
            env_var = value[4:]  # Remove "env:" prefix
            return os.environ.get(env_var)
        return value
    
    def get_metrics(self) -> dict:
        """Get skill usage metrics."""
        return {
            "name": self.name,
            "status": self._status.value,
            "last_used": self._last_used.isoformat() if self._last_used else None,
            "use_count": self._use_count,
            "error_count": self._error_count,
            "error_rate": self._error_count / max(self._use_count, 1),
        }
