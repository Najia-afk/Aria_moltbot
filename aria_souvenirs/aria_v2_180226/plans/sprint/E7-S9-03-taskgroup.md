# S9-03: Use asyncio.TaskGroup in Agent Pool
**Epic:** E7 — Python 3.13+ Modernization | **Priority:** P1 | **Points:** 3 | **Phase:** 9

## Problem
Agent spawning in `aria_engine/agent_pool.py`, roundtable discussions in `aria_engine/roundtable.py`, and parallel cron execution in `aria_engine/scheduler.py` use `asyncio.gather()` for concurrent operations. `asyncio.gather()` has weak error semantics: if one task fails, others continue running in an undefined state. Python 3.11+ provides `asyncio.TaskGroup` with structured concurrency — all tasks in a group are cancelled if any raises, and errors surface as `ExceptionGroup`.

## Root Cause
The engine code was written to be compatible with Python 3.10+. `asyncio.TaskGroup` was added in Python 3.11. Now that we target 3.13+, we can use structured concurrency for better error handling and resource cleanup in agent lifecycle management.

## Fix
### `aria_engine/agent_pool.py` (updated sections)
```python
"""
Agent Pool — Async agent lifecycle with structured concurrency.

Uses asyncio.TaskGroup (Python 3.11+) for:
- Spawning multiple agents concurrently
- Running agent tasks with proper cancellation
- Structured error propagation via ExceptionGroup
"""
import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from aria_engine.config import EngineConfig
from aria_engine.exceptions import AgentError

logger = logging.getLogger("aria.engine.agent_pool")


@dataclass
class AgentTask:
    """Represents a running agent task."""
    agent_id: str
    task: asyncio.Task[Any] | None = None
    started_at: float = field(default_factory=time.monotonic)
    status: str = "pending"


class AgentPool:
    """
    Manages async agent lifecycle with structured concurrency.
    
    Uses asyncio.TaskGroup for:
    - Parallel agent spawning with automatic cleanup on failure
    - Bounded concurrency (max 5 agents)
    - Proper cancellation propagation
    """
    
    MAX_CONCURRENT = 5
    
    def __init__(self, config: EngineConfig):
        self.config = config
        self._agents: dict[str, AgentTask] = {}
        self._semaphore = asyncio.Semaphore(self.MAX_CONCURRENT)
        self._shutdown = asyncio.Event()
    
    async def spawn_agents(self, agent_configs: list[dict[str, Any]]) -> dict[str, str]:
        """
        Spawn multiple agents concurrently using TaskGroup.
        
        If any agent fails to spawn, all others in the batch are cancelled.
        Returns mapping of agent_id → status.
        """
        results: dict[str, str] = {}
        
        try:
            async with asyncio.TaskGroup() as tg:
                for config in agent_configs:
                    agent_id = config["agent_id"]
                    task = tg.create_task(
                        self._spawn_single_agent(config),
                        name=f"spawn-{agent_id}",
                    )
                    self._agents[agent_id] = AgentTask(
                        agent_id=agent_id,
                        task=task,
                        status="spawning",
                    )
            
            # All tasks completed successfully
            for agent_id in [c["agent_id"] for c in agent_configs]:
                results[agent_id] = "running"
                self._agents[agent_id].status = "running"
                
        except* AgentError as eg:
            # Handle agent-specific errors
            for exc in eg.exceptions:
                agent_id = getattr(exc, "agent_id", "unknown")
                logger.error("Agent %s failed to spawn: %s", agent_id, exc)
                results[agent_id] = f"error: {exc}"
                if agent_id in self._agents:
                    self._agents[agent_id].status = "error"
                    
        except* Exception as eg:
            # Handle unexpected errors
            for exc in eg.exceptions:
                logger.error("Unexpected error during agent spawn: %s", exc)
            # Mark all agents from this batch as failed
            for config in agent_configs:
                agent_id = config["agent_id"]
                results.setdefault(agent_id, f"error: {eg}")
                if agent_id in self._agents:
                    self._agents[agent_id].status = "error"
        
        return results
    
    async def _spawn_single_agent(self, config: dict[str, Any]) -> None:
        """Spawn a single agent with semaphore-bounded concurrency."""
        agent_id = config["agent_id"]
        async with self._semaphore:
            logger.info("Spawning agent: %s", agent_id)
            
            # Load agent configuration from DB
            from aria_engine.session_manager import NativeSessionManager
            session_mgr = NativeSessionManager(self.config)
            
            # Create isolated session for this agent
            session = await session_mgr.create_session(
                agent_id=agent_id,
                session_type="agent",
                model=config.get("model", self.config.default_model),
                system_prompt=config.get("system_prompt"),
            )
            
            self._agents[agent_id].status = "running"
            logger.info("Agent %s spawned with session %s", agent_id, session["id"])
    
    async def run_parallel_tasks(
        self,
        tasks: list[dict[str, Any]],
        timeout: float = 300.0,
    ) -> list[dict[str, Any]]:
        """
        Run multiple agent tasks in parallel with structured concurrency.
        
        Each task is: {"agent_id": str, "prompt": str, "kwargs": dict}
        Returns list of results with agent_id, status, and output.
        """
        results: list[dict[str, Any]] = []
        
        try:
            async with asyncio.TaskGroup() as tg:
                task_futures: list[tuple[str, asyncio.Task[dict[str, Any]]]] = []
                
                for task_spec in tasks:
                    agent_id = task_spec["agent_id"]
                    future = tg.create_task(
                        asyncio.wait_for(
                            self._execute_agent_task(task_spec),
                            timeout=timeout,
                        ),
                        name=f"task-{agent_id}",
                    )
                    task_futures.append((agent_id, future))
            
            # Collect results from completed tasks
            for agent_id, future in task_futures:
                try:
                    result = future.result()
                    results.append({"agent_id": agent_id, "status": "success", **result})
                except Exception as e:
                    results.append({"agent_id": agent_id, "status": "error", "error": str(e)})
                    
        except* asyncio.TimeoutError as eg:
            logger.warning("Agent tasks timed out after %.1fs", timeout)
            for exc in eg.exceptions:
                results.append({"agent_id": "unknown", "status": "timeout", "error": str(exc)})
                
        except* Exception as eg:
            for exc in eg.exceptions:
                logger.error("Agent task error: %s", exc)
                results.append({"agent_id": "unknown", "status": "error", "error": str(exc)})
        
        return results
    
    async def _execute_agent_task(self, task_spec: dict[str, Any]) -> dict[str, Any]:
        """Execute a single agent task."""
        agent_id = task_spec["agent_id"]
        prompt = task_spec["prompt"]
        
        async with self._semaphore:
            start = time.monotonic()
            from aria_engine.chat_engine import ChatEngine
            chat = ChatEngine(self.config)
            
            # Route to agent's session
            agent_state = self._agents.get(agent_id)
            if not agent_state:
                raise AgentError(f"Agent {agent_id} not found in pool")
            
            response = await chat.send_message(
                session_id=task_spec.get("session_id"),
                content=prompt,
                agent_id=agent_id,
            )
            
            elapsed = time.monotonic() - start
            return {
                "output": response.get("content", ""),
                "latency_ms": int(elapsed * 1000),
                "tokens": response.get("tokens_output", 0),
            }
    
    async def shutdown(self, timeout: float = 30.0) -> None:
        """Gracefully shutdown all agents using TaskGroup for parallel cleanup."""
        self._shutdown.set()
        agent_ids = list(self._agents.keys())
        
        if not agent_ids:
            return
        
        logger.info("Shutting down %d agents...", len(agent_ids))
        
        try:
            async with asyncio.TaskGroup() as tg:
                for agent_id in agent_ids:
                    tg.create_task(
                        asyncio.wait_for(
                            self._terminate_agent(agent_id),
                            timeout=timeout / len(agent_ids),
                        ),
                        name=f"shutdown-{agent_id}",
                    )
        except* asyncio.TimeoutError:
            logger.warning("Some agents did not shut down gracefully")
        except* Exception as eg:
            for exc in eg.exceptions:
                logger.error("Error during agent shutdown: %s", exc)
        
        self._agents.clear()
        logger.info("All agents terminated")
    
    async def _terminate_agent(self, agent_id: str) -> None:
        """Terminate a single agent."""
        agent = self._agents.get(agent_id)
        if agent and agent.task and not agent.task.done():
            agent.task.cancel()
            try:
                await agent.task
            except asyncio.CancelledError:
                pass
        agent_state = self._agents.get(agent_id)
        if agent_state:
            agent_state.status = "terminated"
        logger.info("Agent %s terminated", agent_id)
    
    def get_pool_status(self) -> dict[str, Any]:
        """Return pool status summary."""
        return {
            "total_agents": len(self._agents),
            "max_concurrent": self.MAX_CONCURRENT,
            "agents": {
                aid: {
                    "status": a.status,
                    "uptime_s": int(time.monotonic() - a.started_at),
                }
                for aid, a in self._agents.items()
            },
            "shutdown_requested": self._shutdown.is_set(),
        }
```

### `aria_engine/roundtable.py` (updated sections)
```python
"""
Roundtable — Multi-agent collaborative discussion using TaskGroup.

Replaces asyncio.gather() with structured concurrency for
parallel agent thinking rounds.
"""
import asyncio
import logging
from typing import Any

from aria_engine.agent_pool import AgentPool
from aria_engine.config import EngineConfig

logger = logging.getLogger("aria.engine.roundtable")


class Roundtable:
    """
    Multi-agent roundtable discussion.
    
    Each round: all agents think in parallel (TaskGroup),
    then results are shared as context for the next round.
    """
    
    def __init__(self, config: EngineConfig, pool: AgentPool):
        self.config = config
        self.pool = pool
    
    async def discuss(
        self,
        topic: str,
        agent_ids: list[str],
        rounds: int = 3,
        timeout_per_round: float = 120.0,
    ) -> list[dict[str, Any]]:
        """
        Run a multi-round discussion with parallel agent responses.
        
        Args:
            topic: Discussion topic/prompt
            agent_ids: List of agent IDs to participate
            rounds: Number of discussion rounds
            timeout_per_round: Max time per round in seconds
            
        Returns:
            List of round results with all agent responses
        """
        all_rounds: list[dict[str, Any]] = []
        context = topic
        
        for round_num in range(1, rounds + 1):
            logger.info("Roundtable round %d/%d: %d agents", round_num, rounds, len(agent_ids))
            
            round_results: dict[str, str] = {}
            
            try:
                async with asyncio.TaskGroup() as tg:
                    futures: dict[str, asyncio.Task[str]] = {}
                    for agent_id in agent_ids:
                        prompt = (
                            f"[Round {round_num}/{rounds}] "
                            f"Topic: {context}\n\n"
                            f"Previous responses:\n"
                            + "\n".join(
                                f"- {aid}: {resp}"
                                for aid, resp in round_results.items()
                            )
                        )
                        future = tg.create_task(
                            asyncio.wait_for(
                                self._get_agent_response(agent_id, prompt),
                                timeout=timeout_per_round,
                            ),
                            name=f"round-{round_num}-{agent_id}",
                        )
                        futures[agent_id] = future
                
                # Collect results
                for agent_id, future in futures.items():
                    try:
                        round_results[agent_id] = future.result()
                    except Exception as e:
                        round_results[agent_id] = f"[Error: {e}]"
                        
            except* asyncio.TimeoutError:
                logger.warning("Round %d timed out", round_num)
                for agent_id in agent_ids:
                    round_results.setdefault(agent_id, "[Timeout]")
                    
            except* Exception as eg:
                for exc in eg.exceptions:
                    logger.error("Round %d error: %s", round_num, exc)
            
            all_rounds.append({
                "round": round_num,
                "responses": round_results,
            })
            
            # Build context for next round
            context = topic + "\n\n" + "\n".join(
                f"[Round {round_num}] {aid}: {resp}"
                for aid, resp in round_results.items()
            )
        
        return all_rounds
    
    async def _get_agent_response(self, agent_id: str, prompt: str) -> str:
        """Get a single agent's response."""
        from aria_engine.chat_engine import ChatEngine
        chat = ChatEngine(self.config)
        
        result = await chat.send_message(
            session_id=None,
            content=prompt,
            agent_id=agent_id,
        )
        return result.get("content", "")
```

### `aria_engine/scheduler.py` (updated section — parallel cron execution)
```python
    async def _execute_batch(
        self,
        jobs: list[dict[str, Any]],
        timeout: float = 300.0,
    ) -> list[dict[str, Any]]:
        """
        Execute a batch of cron jobs in parallel using TaskGroup.
        
        Replaces:
            results = await asyncio.gather(*[self._run_job(j) for j in jobs])
        With structured concurrency:
            async with asyncio.TaskGroup() ...
        """
        results: list[dict[str, Any]] = []
        
        try:
            async with asyncio.TaskGroup() as tg:
                futures: list[tuple[str, asyncio.Task[dict[str, Any]]]] = []
                for job in jobs:
                    future = tg.create_task(
                        asyncio.wait_for(
                            self._run_single_job(job),
                            timeout=timeout,
                        ),
                        name=f"cron-{job['id']}",
                    )
                    futures.append((job["id"], future))
            
            for job_id, future in futures:
                try:
                    result = future.result()
                    results.append({"job_id": job_id, "status": "success", **result})
                except Exception as e:
                    results.append({"job_id": job_id, "status": "error", "error": str(e)})
                    
        except* asyncio.TimeoutError as eg:
            logger.warning("Batch execution timed out: %d jobs affected", len(eg.exceptions))
            for exc in eg.exceptions:
                results.append({"job_id": "unknown", "status": "timeout"})
                
        except* Exception as eg:
            for exc in eg.exceptions:
                logger.error("Batch execution error: %s", exc)
                results.append({"job_id": "unknown", "status": "error", "error": str(exc)})
        
        return results
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | AgentPool is engine layer, above DB/ORM |
| 2 | .env for secrets (zero in code) | ❌ | No secrets involved |
| 3 | models.yaml single source of truth | ❌ | No model references |
| 4 | Docker-first testing | ✅ | Must test in Docker with Python 3.13+ |
| 5 | aria_memories only writable path | ❌ | Code refactor only |
| 6 | No soul modification | ❌ | No soul access |

## Dependencies
- S9-01 must complete first (Python 3.13+ in pyproject.toml)
- S4-01 must complete first (AgentPool exists)
- S3-01 must complete first (Scheduler exists)

## Verification
```bash
# 1. No asyncio.gather() in engine code:
python -c "
import subprocess, sys
result = subprocess.run(
    ['grep', '-rn', 'asyncio.gather', '--include=*.py', 'aria_engine/'],
    capture_output=True, text=True
)
if result.stdout.strip():
    print('WARNING: asyncio.gather() still used:')
    print(result.stdout)
else:
    print('OK: No asyncio.gather() — all replaced with TaskGroup')
"
# EXPECTED: OK: No asyncio.gather()

# 2. TaskGroup usage verified:
python -c "
import subprocess
result = subprocess.run(
    ['grep', '-rn', 'asyncio.TaskGroup', '--include=*.py', 'aria_engine/'],
    capture_output=True, text=True
)
print(result.stdout)
"
# EXPECTED: agent_pool.py, roundtable.py, scheduler.py all show TaskGroup usage

# 3. ExceptionGroup handling verified:
python -c "
import subprocess
result = subprocess.run(
    ['grep', '-rn', 'except\*', '--include=*.py', 'aria_engine/'],
    capture_output=True, text=True
)
print(result.stdout)
"
# EXPECTED: except* AgentError, except* asyncio.TimeoutError, except* Exception

# 4. Module imports:
python -c "from aria_engine.agent_pool import AgentPool; print('OK')"
python -c "from aria_engine.roundtable import Roundtable; print('OK')"
# EXPECTED: OK, OK
```

## Prompt for Agent
```
Replace asyncio.gather() with asyncio.TaskGroup in aria_engine for structured concurrency.

FILES TO READ FIRST:
- aria_engine/agent_pool.py (full file — current gather usage)
- aria_engine/roundtable.py (full file — parallel agent thinking)
- aria_engine/scheduler.py (full file — batch cron execution)
- aria_engine/config.py (EngineConfig reference)
- aria_engine/exceptions.py (AgentError definition)

STEPS:
1. Read all files to find every asyncio.gather() call
2. Replace each with asyncio.TaskGroup context manager
3. Add except* handlers for ExceptionGroup (AgentError, TimeoutError)
4. Ensure cancellation propagates correctly
5. Run verification commands

CONSTRAINTS:
- Every asyncio.gather() in aria_engine/ must be replaced
- Use except* syntax for granular ExceptionGroup handling
- Maintain the MAX_CONCURRENT=5 limit via Semaphore (inside TaskGroup)
- Keep the same public API (spawn_agents, run_parallel_tasks, shutdown)
- Name each task with tg.create_task(coro, name="descriptive-name")
```
