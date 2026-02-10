"""Syncs SkillRegistry health status to the skill_status DB table."""
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


async def sync_skill_status_to_db(registry, api_client):
    """Write current skill status to DB via api_client.

    Called at brain startup and periodically by the heartbeat loop.

    Parameters
    ----------
    registry : SkillRegistry
        The live skill registry whose ``_skills`` dict we iterate.
    api_client : httpx.AsyncClient (or similar)
        An async HTTP client pointed at the Aria Brain API.
    """
    for name, skill in registry._skills.items():
        try:
            status = await skill.health_check()
            await api_client.post("/skills/sync", json={
                "skill_name": name,
                "canonical_name": getattr(skill, "canonical_name", name),
                "layer": getattr(skill, "layer", None),
                "status": status.value if hasattr(status, "value") else str(status),
                "use_count": getattr(skill, "_use_count", 0),
                "error_count": getattr(skill, "_error_count", 0),
            })
        except Exception as e:
            logger.warning("Failed to sync skill %s: %s", name, e)
