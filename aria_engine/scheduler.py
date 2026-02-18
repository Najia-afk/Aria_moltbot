"""
Scheduler — APScheduler + PostgreSQL-backed cron job management.

TODO (Sprint 3):
- APScheduler with PostgreSQL job store
- Cron job CRUD operations
- Job execution with agent routing
- Heartbeat integration
"""


class EngineScheduler:
    """APScheduler-based cron job manager with PostgreSQL persistence."""

    def __init__(self, session_factory=None, agent_pool=None, config=None):
        self.session_factory = session_factory
        self.agent_pool = agent_pool
        self.config = config
        self.is_running = False

    async def start(self):
        """Start the scheduler."""
        self.is_running = True

    async def stop(self):
        """Stop the scheduler."""
        self.is_running = False
