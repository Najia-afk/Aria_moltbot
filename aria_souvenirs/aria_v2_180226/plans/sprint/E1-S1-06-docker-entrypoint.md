# S1-06: Docker Entrypoint & Service Configuration
**Epic:** E1 — Engine Core | **Priority:** P0 | **Points:** 3 | **Phase:** 1

## Problem
The current `aria-brain` service uses `openclaw-entrypoint.sh` to boot via OpenClaw's Node.js runtime. The new `aria_engine` must have its own entrypoint that:
1. Boots `aria_engine` as a standalone Python process
2. Initializes DB connections and runs pending migrations
3. Starts the APScheduler for cron jobs
4. Launches the agent pool
5. Provides a health endpoint
6. Replaces `clawdbot` Docker service entirely

## Root Cause
The `clawdbot` service in `stacks/brain/docker-compose.yml` wraps OpenClaw's Node.js runtime. The `aria-brain` service delegates to `openclaw-entrypoint.sh` which pipes work through OpenClaw before reaching Aria's Python code. Both must be replaced by a single Python process.

## Fix
### `aria_engine/entrypoint.py`
```python
"""
Aria Engine — Standalone Runtime Entrypoint
Replaces openclaw-entrypoint.sh and clawdbot service.
"""
import asyncio
import signal
import sys
import logging
from contextlib import asynccontextmanager

from aria_engine.config import EngineConfig

logger = logging.getLogger("aria_engine")


class AriaEngine:
    """Main engine process — manages DB, scheduler, agents, health."""

    def __init__(self, config: EngineConfig | None = None):
        self.config = config or EngineConfig.from_env()
        self._shutdown_event = asyncio.Event()
        self._scheduler = None
        self._agent_pool = None
        self._health_server = None
        self._db_engine = None

    async def start(self):
        """Boot sequence (replaces startup.py + openclaw-entrypoint.sh)."""
        logger.info("🚀 Aria Engine starting...")
        
        # Phase 1: Database
        await self._init_database()
        logger.info("✅ Phase 1: Database connected")
        
        # Phase 2: Run pending migrations
        await self._run_migrations()
        logger.info("✅ Phase 2: Migrations applied")
        
        # Phase 3: Load agent state from DB
        await self._init_agents()
        logger.info("✅ Phase 3: Agents initialized")
        
        # Phase 4: Start scheduler (cron jobs from DB)
        await self._init_scheduler()
        logger.info("✅ Phase 4: Scheduler started")
        
        # Phase 5: Health endpoint
        await self._init_health()
        logger.info("✅ Phase 5: Health server on :8081")
        
        logger.info("🟢 Aria Engine running — all systems nominal")
        
        # Wait for shutdown signal
        await self._shutdown_event.wait()
        await self._cleanup()
        logger.info("🔴 Aria Engine stopped")

    async def _init_database(self):
        """Create async SQLAlchemy engine + session factory."""
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
        
        self._db_engine = create_async_engine(
            self.config.database_url,
            pool_size=self.config.db_pool_size,
            max_overflow=self.config.db_max_overflow,
            pool_pre_ping=True,
            echo=self.config.debug,
        )
        self._session_factory = async_sessionmaker(
            self._db_engine,
            expire_on_commit=False,
        )
        # Verify connection
        async with self._db_engine.begin() as conn:
            await conn.execute(sa_text("SELECT 1"))

    async def _run_migrations(self):
        """Run Alembic migrations programmatically."""
        from alembic.config import Config
        from alembic import command
        
        alembic_cfg = Config()
        alembic_cfg.set_main_option("script_location", "src/api/alembic")
        alembic_cfg.set_main_option("sqlalchemy.url", self.config.database_url.replace("+asyncpg", ""))
        
        # Run in thread to avoid blocking event loop
        await asyncio.to_thread(command.upgrade, alembic_cfg, "head")

    async def _init_agents(self):
        """Load agent definitions from DB and instantiate pool."""
        from aria_engine.agent_pool import AgentPool
        
        self._agent_pool = AgentPool(
            session_factory=self._session_factory,
            config=self.config,
        )
        await self._agent_pool.load_agents()

    async def _init_scheduler(self):
        """Start APScheduler with PostgreSQL job store."""
        from aria_engine.scheduler import EngineScheduler
        
        self._scheduler = EngineScheduler(
            session_factory=self._session_factory,
            agent_pool=self._agent_pool,
            config=self.config,
        )
        await self._scheduler.start()

    async def _init_health(self):
        """Minimal aiohttp health server on port 8081."""
        from aiohttp import web
        
        async def health_handler(request):
            return web.json_response({
                "status": "healthy",
                "engine": "aria_engine",
                "scheduler": self._scheduler.is_running if self._scheduler else False,
                "agents": self._agent_pool.agent_count if self._agent_pool else 0,
                "db": self._db_engine is not None,
            })
        
        app = web.Application()
        app.router.add_get("/health", health_handler)
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", 8081)
        await site.start()
        self._health_server = runner

    async def _cleanup(self):
        """Graceful shutdown."""
        if self._scheduler:
            await self._scheduler.stop()
        if self._agent_pool:
            await self._agent_pool.shutdown()
        if self._health_server:
            await self._health_server.cleanup()
        if self._db_engine:
            await self._db_engine.dispose()

    def request_shutdown(self):
        """Signal the engine to shut down gracefully."""
        self._shutdown_event.set()


def main():
    """CLI entrypoint — called by Docker CMD."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    
    engine = AriaEngine()
    loop = asyncio.new_event_loop()
    
    # Handle SIGTERM/SIGINT for Docker stop
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, engine.request_shutdown)
    
    try:
        loop.run_until_complete(engine.start())
    except KeyboardInterrupt:
        engine.request_shutdown()
        loop.run_until_complete(engine._cleanup())
    finally:
        loop.close()


if __name__ == "__main__":
    main()
```

### Docker Compose changes (`stacks/brain/docker-compose.yml`)
```yaml
  # REMOVE this entire service block:
  # clawdbot:
  #   image: ...
  #   ...

  # ADD new service:
  aria-engine:
    build:
      context: ../../
      dockerfile: Dockerfile
    container_name: aria-engine
    command: ["python", "-m", "aria_engine.entrypoint"]
    environment:
      - DATABASE_URL=postgresql+asyncpg://aria_admin:${POSTGRES_PASSWORD}@aria-db:5432/aria_warehouse
      - LITELLM_URL=http://litellm:4000
      - LITELLM_API_KEY=${LITELLM_API_KEY}
      - ENGINE_DEBUG=${ENGINE_DEBUG:-false}
    volumes:
      - ../../aria_memories:/app/aria_memories
      - ../../aria_mind/soul:/app/aria_mind/soul:ro
    depends_on:
      aria-db:
        condition: service_healthy
      litellm:
        condition: service_started
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8081/health"]
      interval: 30s
      timeout: 5s
      retries: 3
    restart: unless-stopped
    networks:
      - aria-network
    labels:
      - "com.aria.service=engine"
```

### `pyproject.toml` script entry:
```toml
[project.scripts]
aria-engine = "aria_engine.entrypoint:main"
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ✅ | Layer 4 — Infrastructure |
| 2 | .env for secrets | ✅ | DB password, LiteLLM key from env |
| 3 | models.yaml | ❌ | No model routing |
| 4 | Docker-first | ✅ | Full Docker service definition |
| 5 | aria_memories writable | ✅ | Volume mount preserves write access |
| 6 | No soul modification | ✅ | Soul mounted read-only |

## Dependencies
- S1-01 (engine package structure)
- S1-02 (LLM Gateway — used by agents)
- S1-05 (Alembic migrations — run at boot)

## Verification
```bash
# 1. Engine boots locally:
python -m aria_engine.entrypoint
# EXPECTED: 5 phases complete, health on :8081

# 2. Health check works:
curl http://localhost:8081/health
# EXPECTED: {"status": "healthy", "engine": "aria_engine", ...}

# 3. Docker build succeeds:
docker compose -f stacks/brain/docker-compose.yml build aria-engine
# EXPECTED: Build completes

# 4. Docker start with dependencies:
docker compose -f stacks/brain/docker-compose.yml up -d aria-engine
# EXPECTED: Container starts, health check passes

# 5. Graceful shutdown:
docker stop aria-engine
# EXPECTED: Clean shutdown in logs, no orphan connections
```

## Prompt for Agent
```
Create the Aria Engine Docker entrypoint that replaces openclaw-entrypoint.sh.

FILES TO READ FIRST:
- stacks/brain/docker-compose.yml (full file — existing 12 services)
- stacks/brain/openclaw-entrypoint.sh (what we're replacing)
- aria_mind/startup.py (existing boot sequence to preserve)
- Dockerfile (current build process)
- aria_engine/config.py (from S1-01)

STEPS:
1. Create aria_engine/entrypoint.py with 5-phase boot
2. Add aria-engine service to docker-compose.yml
3. Keep clawdbot service but mark it deprecated (comments)
4. Add pyproject.toml script entry
5. Test: python -m aria_engine.entrypoint
6. Test: docker compose build + up

CONSTRAINTS:
- Constraint 2: All secrets from environment variables
- Constraint 4: Docker-native — healthcheck, depends_on, restart policy
- Constraint 5: aria_memories mounted read-write
- Constraint 6: soul mounted read-only
```
