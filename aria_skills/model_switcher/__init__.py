"""Model switcher skill — catalog-backed active model and thinking-mode state."""


from datetime import datetime, timezone

from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus
from aria_skills.registry import SkillRegistry


@SkillRegistry.register
class ModelSwitcherSkill(BaseSkill):
    def __init__(self, config: SkillConfig):
        super().__init__(config)
        self._catalog: dict = {}
        self._current_model: str | None = None
        self._thinking_enabled: bool = True
        self._history: list[dict] = []

    @property
    def name(self) -> str:
        return "model_switcher"

    async def initialize(self) -> bool:
        try:
            from aria_models.loader import load_catalog

            self._catalog = load_catalog() or {}
            model_ids = list((self._catalog.get("models") or {}).keys())
            self._current_model = model_ids[0] if model_ids else "qwen-cpu-fallback"
            self._status = SkillStatus.AVAILABLE
            return True
        except Exception:
            self._catalog = {"models": {"qwen-cpu-fallback": {}}}
            self._current_model = "qwen-cpu-fallback"
            self._status = SkillStatus.AVAILABLE
            return True

    async def health_check(self) -> SkillStatus:
        return self._status

    def _record(self, action: str, payload: dict):
        self._history.append(
            {
                "action": action,
                "payload": payload,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        self._history = self._history[-100:]

    async def list_models(self) -> SkillResult:
        models = []
        for model_id, meta in (self._catalog.get("models") or {}).items():
            litellm_model = ((meta or {}).get("litellm") or {}).get("model")
            models.append({"model": model_id, "litellm_model": litellm_model})
        return SkillResult.ok({"current_model": self._current_model, "models": models})

    async def switch_model(self, model: str, reason: str | None = None) -> SkillResult:
        if model not in (self._catalog.get("models") or {}):
            return SkillResult.fail(f"Unknown model: {model}")
        previous = self._current_model
        self._current_model = model
        self._record("switch_model", {"from": previous, "to": model, "reason": reason})
        return SkillResult.ok({"previous_model": previous, "current_model": model, "reason": reason})

    async def get_current_model(self) -> SkillResult:
        return SkillResult.ok({"current_model": self._current_model, "thinking_mode": self._thinking_enabled})

    async def set_thinking_mode(self, enabled: bool, reason: str | None = None) -> SkillResult:
        self._thinking_enabled = bool(enabled)
        self._record("set_thinking_mode", {"enabled": self._thinking_enabled, "reason": reason})
        return SkillResult.ok({"thinking_mode": self._thinking_enabled, "reason": reason})

    async def get_thinking_mode(self) -> SkillResult:
        models = list((self._catalog.get("models") or {}).keys())
        return SkillResult.ok({"thinking_mode": self._thinking_enabled, "catalog_models": models})

    async def get_switch_history(self, limit: int = 10) -> SkillResult:
        return SkillResult.ok({"history": self._history[-max(1, limit):][::-1]})
