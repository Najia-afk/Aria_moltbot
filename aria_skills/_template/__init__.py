"""
Template skill — replace with a short description of your skill.

Copy this directory to aria_skills/<your_skill_name>/ and fill in
the placeholders marked with TODO.
"""
from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus, logged_method
from aria_skills.registry import SkillRegistry


@SkillRegistry.register
class TemplateSkill(BaseSkill):
    """TODO: One-line description of what this skill does."""

    def __init__(self, config: SkillConfig):
        super().__init__(config)
        # TODO: declare any instance variables you need
        self._api = None

    # ── Identity ────────────────────────────────────────────────────────
    @property
    def name(self) -> str:
        # TODO: return your skill's snake_case name (must match directory name)
        return "template"

    # ── Lifecycle ───────────────────────────────────────────────────────
    async def initialize(self) -> bool:
        """
        Set up connections, validate config, and mark the skill available.

        Returns:
            True if initialisation succeeded.
        """
        # TODO: add your initialisation logic
        # Example: self._api = await get_api_client()
        self._status = SkillStatus.AVAILABLE
        self.logger.info(f"{self.name} skill initialised")
        return True

    async def health_check(self) -> SkillStatus:
        """Return current availability status."""
        return self._status

    # ── Public tools (listed in skill.json) ─────────────────────────────
    @logged_method()
    async def do_something(self, param: str) -> SkillResult:
        """
        TODO: Describe what this tool does.

        Args:
            param: TODO — describe parameter.

        Returns:
            SkillResult with the output data on success.
        """
        try:
            result = await self._internal_logic(param)
            self._log_usage("do_something", True)
            return SkillResult.ok(result)
        except Exception as e:
            self._log_usage("do_something", False, error=str(e))
            return SkillResult.fail(str(e))

    # ── Private helpers ─────────────────────────────────────────────────
    async def _internal_logic(self, param: str) -> dict:
        """Private implementation detail — not exposed as a tool."""
        # TODO: replace with real logic
        return {"echo": param}
