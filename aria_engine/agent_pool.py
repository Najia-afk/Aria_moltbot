"""
Agent Pool — Async agent lifecycle management.

TODO (Sprint 4):
- Agent spawn/track/terminate
- Per-agent session isolation
- Agent auto-routing with pheromone scoring
- Roundtable multi-agent collaboration
"""


class AgentPool:
    """Manages async agent lifecycle and task routing."""

    def __init__(self, session_factory=None, config=None):
        self.session_factory = session_factory
        self.config = config
        self.agent_count = 0

    async def load_agents(self):
        """Load agent definitions from DB."""
        pass

    async def shutdown(self):
        """Gracefully shutdown all agents."""
        pass
