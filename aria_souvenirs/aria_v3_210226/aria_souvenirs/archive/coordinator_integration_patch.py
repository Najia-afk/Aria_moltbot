"""
Coordinator Integration Patch for Task-Type-Aware Routing

This file documents the changes needed in coordinator.py to enable
task-type-aware agent selection.

Integration Steps:
1. Import the TaskTypeRouter at the top of coordinator.py
2. Modify the process() method to extract/detect task type
3. Pass task_type to the tracker.get_best_agent() call
"""

# === STEP 1: Add to coordinator.py imports ===
IMPORT_PATCH = '''
from aria_agents.scoring import (
    compute_pheromone,
    select_best_agent,
    COLD_START_SCORE,
    get_performance_tracker,
    PerformanceTracker,
)
# NEW: Import task-type routing
from aria_memories.knowledge.task_type_routing import TaskTypeRouter, route_with_task_type
'''

# === STEP 2: Add to AgentCoordinator.__init__ ===
INIT_PATCH = '''
    def __init__(self, skill_registry: Optional["SkillRegistry"] = None):
        self._skill_registry = skill_registry
        self._agents: Dict[str, BaseAgent] = {}
        self._configs: Dict[str, AgentConfig] = {}
        self._hierarchy: Dict[str, List[str]] = {}
        self._main_agent_id: Optional[str] = None
        self._tracker: PerformanceTracker = get_performance_tracker()
        self._task_router: TaskTypeRouter = TaskTypeRouter(self._tracker)  # NEW
        self.logger = logging.getLogger("aria.coordinator")
'''

# === STEP 3: Modify process() method ===
PROCESS_PATCH = '''
    async def process(self, message: str, agent_id: Optional[str] = None, **kwargs) -> AgentMessage:
        """
        Process a message through an agent with performance tracking.
        
        Enhanced with:
        - Pheromone-based agent selection when no specific agent requested
        - Task-type-aware routing for specialized delegation  # NEW
        - Performance recording after each invocation
        - Auto-detection of roundtable needs
        """
        # Auto-detect if this needs roundtable collaboration
        if not agent_id and self.detect_roundtable_need(message):
            self.logger.info("Auto-detected roundtable need — gathering perspectives")
            perspectives = await self.roundtable(message)
            if perspectives:
                synthesis_prompt = self._build_synthesis_prompt(message, perspectives)
                agent_id = self._main_agent_id
                message = synthesis_prompt
        
        # Select target agent — use pheromone scores if no specific agent requested
        target_id = agent_id
        if not target_id:
            if len(self._agents) > 1 and self._tracker:
                # NEW: Extract task type and use task-aware routing
                task_type = kwargs.get("task_type") or self._task_router.classify_task(message)
                target_id = self._tracker.get_best_agent(
                    list(self._agents.keys()), 
                    task_type=task_type
                )
                self.logger.debug(
                    f"Task-type routing [{task_type}]: {target_id} "
                    f"(score={self._tracker.get_score(target_id):.3f})"
                )
            else:
                target_id = self._main_agent_id
        
        if not target_id:
            return AgentMessage(role="system", content="No agents configured")
        
        agent = self._agents.get(target_id)
        if not agent:
            return AgentMessage(role="system", content=f"Agent {target_id} not found")
        
        # Execute with timing for performance tracking
        start = datetime.now(timezone.utc)
        try:
            result = await agent.process(message, **kwargs)
            elapsed_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
            
            # Record success with task type
            success = bool(result.content) and not result.content.startswith("[Error")
            task_type = kwargs.get("task_type") or self._task_router.classify_task(message)  # NEW
            self._tracker.record(
                agent_id=target_id,
                success=success,
                duration_ms=elapsed_ms,
                task_type=task_type,  # NEW: Record task type for learning
            )
            
            return result
            
        except Exception as e:
            elapsed_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
            
            # Record failure with task type
            task_type = kwargs.get("task_type") or self._task_router.classify_task(message)  # NEW
            self._tracker.record(
                agent_id=target_id,
                success=False,
                duration_ms=elapsed_ms,
                task_type=task_type,  # NEW: Record task type for learning
            )
            
            self.logger.error(f"Agent {target_id} failed: {e}")
            return AgentMessage(role="system", content=f"[Error: {e}]", agent_id=target_id)
'''

# === STEP 4: Add new method for explicit task routing ===
ROUTE_TASK_METHOD = '''
    async def route_task(
        self, 
        task: str, 
        candidates: Optional[List[str]] = None,
        task_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Route a task to the best agent based on task-type performance history.
        
        This is the primary method for autonomous agent selection - the coordinator
        learns which agents excel at which task types and routes accordingly.
        
        Args:
            task: Task description
            candidates: Optional list of agent IDs (defaults to all agents)
            task_type: Optional explicit task type (auto-detected if not provided)
            
        Returns:
            Dict with routing decision details
        """
        candidates = candidates or list(self._agents.keys())
        
        decision = self._task_router.route_task(candidates, task, task_type)
        
        self.logger.info(
            f"Task routed to {decision.agent_id} "
            f"(type: {decision.task_type}, confidence: {decision.confidence:.2f})"
        )
        
        return {
            "agent_id": decision.agent_id,
            "task_type": decision.task_type,
            "confidence": decision.confidence,
            "reason": decision.reason,
        }
'''

# === STEP 5: Add method to get specialization report ===
SPECIALIZATION_REPORT_METHOD = '''
    def get_specialization_report(self) -> Dict[str, Any]:
        """
        Get a report of which agents specialize in which task types.
        
        This helps understand the swarm's emergent specialization patterns.
        
        Returns:
            Dict with agent specializations and task-type experts
        """
        return self._task_router.get_specialization_report()
'''

# Full integration summary
INTEGRATION_GUIDE = """
================================================================================
TASK-TYPE-AWARE ROUTING INTEGRATION GUIDE
================================================================================

This patch adds intelligent task routing to the AgentCoordinator.

CHANGES NEEDED IN coordinator.py:

1. IMPORT SECTION (line ~20):
   Add: from aria_memories.knowledge.task_type_routing import TaskTypeRouter

2. __init__ METHOD:
   Add: self._task_router = TaskTypeRouter(self._tracker)

3. process() METHOD:
   - Replace: target_id = self._tracker.get_best_agent(candidates)
   - With:    target_id = self._tracker.get_best_agent(candidates, task_type=task_type)
   - Add task_type detection before agent selection
   - Pass task_type to tracker.record() calls

4. ADD NEW METHODS:
   - route_task() - for explicit task routing with full decision details
   - get_specialization_report() - to see emergent specializations

BENEFITS:
- Analyst agent becomes preferred for "data_analysis" tasks
- Creator agent becomes preferred for "content_creation" tasks
- DevOps agent becomes preferred for "security_scan" tasks
- System learns and adapts based on historical performance
- Confidence scores help decide when to use roundtable vs single agent

EXAMPLE USAGE:
    # Route automatically based on task content
    result = await coordinator.process("Analyze this CSV file")
    # -> Routes to analyst (classified as data_analysis)
    
    # Explicit task type
    result = await coordinator.process("Write a blog post", task_type="content_creation")
    # -> Routes to creator
    
    # Get routing details
    routing = await coordinator.route_task("Debug this error", task_type="debugging")
    print(routing["agent_id"])  # -> "devops"
    print(routing["confidence"])  # -> 0.85
"""

if __name__ == "__main__":
    print(INTEGRATION_GUIDE)
