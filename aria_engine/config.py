"""Engine configuration — all settings from environment + models.yaml."""

import os
from dataclasses import dataclass, field
from typing import Any
from pathlib import Path


@dataclass
class EngineConfig:
    """Runtime configuration for Aria Engine."""

    # Database
    database_url: str = field(default_factory=lambda: os.environ.get(
        "DATABASE_URL", "postgresql://admin:admin@localhost:5432/aria_warehouse"
    ))

    # LLM
    litellm_base_url: str = field(default_factory=lambda: os.environ.get(
        "LITELLM_BASE_URL", "http://litellm:4000/v1"
    ))
    litellm_master_key: str = field(default_factory=lambda: os.environ.get(
        "LITELLM_MASTER_KEY", ""
    ))
    default_model: str = "kimi"
    default_temperature: float = 0.7
    default_max_tokens: int = 4096

    # Agent pool
    max_concurrent_agents: int = 5
    agent_context_limit: int = 50

    # Scheduler
    scheduler_enabled: bool = True
    heartbeat_interval_seconds: int = 3600

    # Paths
    models_yaml_path: str = field(default_factory=lambda: str(
        Path(__file__).parent.parent / "aria_models" / "models.yaml"
    ))
    soul_path: str = field(default_factory=lambda: str(
        Path(__file__).parent.parent / "aria_mind" / "soul"
    ))
    memories_path: str = field(default_factory=lambda: os.environ.get(
        "ARIA_MEMORIES_PATH", str(Path(__file__).parent.parent / "aria_memories")
    ))

    # WebSocket
    ws_ping_interval: int = 30
    ws_ping_timeout: int = 10

    # Database pool
    db_pool_size: int = 10
    db_max_overflow: int = 20

    # Debug
    debug: bool = field(default_factory=lambda: os.environ.get(
        "ENGINE_DEBUG", "false"
    ).lower() in ("true", "1", "yes"))

    @classmethod
    def from_env(cls) -> "EngineConfig":
        """Create config from environment variables."""
        return cls()
