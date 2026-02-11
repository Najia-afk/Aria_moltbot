"""Agent coordinator — orchestrates sub-agents and manages delegation.

The coordinator is the central hub for spawning agents, routing tasks,
and managing the agent lifecycle.
"""
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from .base import AgentConfig, AgentResult, BaseAgent
from .scoring import PerformanceRecord, default_tracker

# Lazy import to avoid circular dependency
_agents_module = None


def _get_agents_module():
    """Lazy load agents module to avoid circular imports."""
    global _agents_module
    if _agents_module is None:
        from . import agents as _agents_module
    return _agents_module


class AgentCoordinator:
    """Central coordinator for all Aria agents.
    
    Manages agent registry, delegates tasks, tracks performance,
    and implements the solve() cycle for complex tasks.
    """
    
    MAX_CONCURRENT = 5  # Max concurrent sub-agents
    
    def __init__(self):
        """Initialize coordinator with empty registry."""
        self._agents: dict[str, BaseAgent] = {}
        self._tracker = default_tracker
    
    def register(self, agent: BaseAgent) -> None:
        """Register an agent with the coordinator.
        
        Args:
            agent: BaseAgent instance to register
        """
        self._agents[agent.id] = agent
    
    def unregister(self, agent_id: str) -> bool:
        """Unregister an agent.
        
        Args:
            agent_id: Agent to remove
            
        Returns:
            True if agent was found and removed
        """
        if agent_id in self._agents:
            del self._agents[agent_id]
            return True
        return False
    
    def get_agent(self, agent_id: str) -> BaseAgent | None:
        """Get agent by ID.
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            Agent instance or None
        """
        return self._agents.get(agent_id)
    
    def list_agents(self) -> list[dict]:
        """List all registered agents.
        
        Returns:
            List of agent config dicts
        """
        return [agent.to_dict() for agent in self._agents.values()]
    
    def find_capable(self, task_type: str) -> list[BaseAgent]:
        """Find all agents capable of handling a task.
        
        Args:
            task_type: Type of task
            
        Returns:
            List of agents that can handle it
        """
        return [
            agent for agent in self._agents.values()
            if agent.can_handle(task_type)
        ]
    
    def delegate(self, agent_id: str, task: dict) -> AgentResult:
        """Delegate a task to a specific agent.
        
        Args:
            agent_id: Target agent ID
            task: Task dict with type, params, etc.
            
        Returns:
            AgentResult from execution
        """
        agent = self._agents.get(agent_id)
        if not agent:
            return AgentResult(
                success=False,
                error=f"Agent {agent_id} not found"
            )
        
        start = time.time()
        tokens = 0  # Would come from actual LLM call
        
        try:
            result = agent.execute(task)
            result.agent_id = agent_id
            result.duration_ms = int((time.time() - start) * 1000)
            result.tokens_used = tokens
        except Exception as e:
            result = AgentResult(
                success=False,
                error=str(e),
                duration_ms=int((time.time() - start) * 1000),
                agent_id=agent_id
            )
        
        # Record performance
        self._tracker.record(PerformanceRecord(
            agent_id=agent_id,
            task_type=task.get("type", "unknown"),
            success=result.success,
            duration_ms=result.duration_ms,
            tokens_used=result.tokens_used
        ))
        
        return result
    
    def route(self, task: dict) -> AgentResult:
        """Automatically route task to best capable agent.
        
        Uses pheromone scores to select the best agent for the task.
        
        Args:
            task: Task dict with type, params, etc.
            
        Returns:
            AgentResult from best agent
        """
        task_type = task.get("type", "unknown")
        capable = self.find_capable(task_type)
        
        if not capable:
            return AgentResult(
                success=False,
                error=f"No agent capable of handling task type: {task_type}"
            )
        
        # Get best by pheromone score
        candidates = [agent.id for agent in capable]
        best_id = self._tracker.select_for_task(candidates)
        
        if not best_id:
            best_id = capable[0].id  # Fallback to first
        
        return self.delegate(best_id, task)
    
    def solve(
        self,
        task: dict,
        max_attempts: int = 3
    ) -> AgentResult:
        """Full solve cycle: explore → work → validate with retry.
        
        For complex tasks that need validation and potential retry.
        
        Args:
            task: Task dict with type, params, validation criteria
            max_attempts: Max retry attempts
            
        Returns:
            AgentResult (success or final failure)
        """
        task_type = task.get("type", "unknown")
        last_error = None
        
        for attempt in range(max_attempts):
            # Route to best agent
            result = self.route(task)
            
            if result.success:
                # Validate if validation func provided
                validator = task.get("validate")
                if validator and callable(validator):
                    try:
                        if validator(result.data):
                            return result
                        else:
                            last_error = "Validation failed"
                            continue
                    except Exception as e:
                        last_error = f"Validation error: {e}"
                        continue
                else:
                    return result
            else:
                last_error = result.error
                # Try different agent on retry
                capable = self.find_capable(task_type)
                if len(capable) > 1:
                    # Exclude last failed agent
                    other_agents = [a for a in capable if a.id != result.agent_id]
                    if other_agents:
                        next_best = self._tracker.select_for_task([a.id for a in other_agents])
                        if next_best:
                            result = self.delegate(next_best, task)
                            if result.success:
                                return result
        
        return AgentResult(
            success=False,
            error=f"Failed after {max_attempts} attempts. Last error: {last_error}"
        )
    
    def roundtable(
        self,
        question: str,
        agent_ids: list[str] | None = None
    ) -> dict[str, AgentResult]:
        """Gather perspectives from multiple agents.
        
        For cross-domain tasks needing input from multiple focuses.
        
        Args:
            question: The question/prompt to ask each agent
            agent_ids: Specific agents to consult (None = all)
            
        Returns:
            Dict mapping agent_id to their response
        """
        if agent_ids:
            agents = [self._agents.get(aid) for aid in agent_ids if aid in self._agents]
        else:
            agents = list(self._agents.values())
        
        results = {}
        task = {
            "type": "consult",
            "params": {"question": question}
        }
        
        with ThreadPoolExecutor(max_workers=self.MAX_CONCURRENT) as executor:
            futures = {
                executor.submit(self.delegate, agent.id, task): agent.id
                for agent in agents
            }
            
            for future in as_completed(futures):
                agent_id = futures[future]
                try:
                    results[agent_id] = future.result()
                except Exception as e:
                    results[agent_id] = AgentResult(
                        success=False,
                        error=str(e),
                        agent_id=agent_id
                    )
        
        return results
    
    def consult(self, agent_id: str, question: str) -> AgentResult:
        """Single-turn consultation with a specific agent.
        
        Args:
            agent_id: Agent to ask
            question: The question
            
        Returns:
            AgentResult with their response
        """
        return self.delegate(agent_id, {
            "type": "consult",
            "params": {"question": question}
        })
    
    def initialize_default_agents(self) -> list[str]:
        """Register all default Aria agents.
        
        Returns:
            List of registered agent IDs
        """
        agents_mod = _get_agents_module()
        agents = agents_mod.create_all_agents()
        
        registered = []
        for agent in agents:
            self.register(agent)
            registered.append(agent.id)
        
        return registered


# Global coordinator instance
coordinator = AgentCoordinator()
