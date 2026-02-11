"""
Task-Type-Aware Agent Routing Extension

This module extends the pheromone scoring system with task-type-specific routing.
It enables the agent swarm to learn which agents excel at specific task types
and route tasks accordingly.

Usage:
    from aria_agents.scoring import get_performance_tracker
    from aria_memories.knowledge.task_type_routing import TaskTypeRouter
    
    tracker = get_performance_tracker()
    router = TaskTypeRouter(tracker)
    
    # Route a task to the best agent
    best_agent = router.route_task(
        candidates=["analyst", "creator", "devops"],
        task="Analyze market trends",
        task_type="data_analysis"
    )
"""
import re
from typing import Dict, List, Optional, Set
from dataclasses import dataclass

from aria_agents.scoring import (
    PerformanceTracker,
    compute_pheromone,
    COLD_START_SCORE,
)


# Task type classification patterns
TASK_TYPE_PATTERNS = {
    "code_review": r"\b(code review|review.*code|PR|pull request|code quality)\b",
    "security_scan": r"\b(security|vulnerability|scan|audit|CVE|exploit)\b",
    "data_analysis": r"\b(analy[sz]e|analysis|data|metrics|statistics|correlation)\b",
    "market_analysis": r"\b(market|stock|portfolio|trading|financial|price)\b",
    "content_creation": r"\b(write|create|draft|content|blog|post|article|story)\b",
    "social_media": r"\b(social|tweet|post|engagement|community|moltbook)\b",
    "research": r"\b(research|investigate|find|lookup|search|discover)\b",
    "debugging": r"\b(debug|fix|bug|error|issue|broken|failing)\b",
    "testing": r"\b(test|pytest|unittest|coverage|CI/CD|pipeline)\b",
    "deployment": r"\b(deploy|release|launch|publish|ship)\b",
    "refactoring": r"\b(refactor|restructure|clean up|simplify|optimize)\b",
    "documentation": r"\b(document|docstring|README|wiki|guide|tutorial)\b",
}


@dataclass
class RoutingDecision:
    """Result of a routing decision."""
    agent_id: str
    confidence: float
    task_type: str
    reason: str


class TaskTypeRouter:
    """
    Routes tasks to agents based on task-type-specific performance history.
    
    This enables the swarm to learn specializations:
    - Analyst becomes preferred for data_analysis tasks
    - Creator becomes preferred for content_creation tasks  
    - Devops becomes preferred for security_scan tasks
    """
    
    def __init__(self, tracker: PerformanceTracker):
        self.tracker = tracker
    
    def classify_task(self, task: str) -> str:
        """
        Auto-classify a task into a task type based on keywords.
        
        Args:
            task: Task description
            
        Returns:
            Task type string (or "general" if no match)
        """
        task_lower = task.lower()
        
        for task_type, pattern in TASK_TYPE_PATTERNS.items():
            if re.search(pattern, task_lower, re.IGNORECASE):
                return task_type
        
        return "general"
    
    def get_task_scores(self, candidates: List[str], task_type: str) -> Dict[str, float]:
        """
        Get pheromone scores for each candidate on a specific task type.
        
        Args:
            candidates: List of agent IDs
            task_type: Type of task
            
        Returns:
            Dict mapping agent_id -> task-specific score
        """
        task_scores: Dict[str, float] = {}
        
        for agent_id in candidates:
            records = self.tracker._records.get(agent_id, [])
            # Filter records by task type
            task_records = [r for r in records if r.get("task_type") == task_type]
            
            if task_records:
                # Compute task-specific score
                task_scores[agent_id] = compute_pheromone(task_records)
            else:
                # No data - cold start with slight penalty
                task_scores[agent_id] = COLD_START_SCORE * 0.9
        
        return task_scores
    
    def route_task(
        self, 
        candidates: List[str], 
        task: str,
        task_type: Optional[str] = None
    ) -> RoutingDecision:
        """
        Route a task to the best agent based on task-type performance.
        
        Args:
            candidates: List of agent IDs to choose from
            task: Task description (used for auto-classification if task_type not given)
            task_type: Optional explicit task type
            
        Returns:
            RoutingDecision with selected agent and confidence
        """
        # Auto-classify if not provided
        if task_type is None:
            task_type = self.classify_task(task)
        
        # Get task-specific scores
        task_scores = self.get_task_scores(candidates, task_type)
        
        # Select best agent
        best_agent = max(candidates, key=lambda a: task_scores.get(a, COLD_START_SCORE))
        best_score = task_scores.get(best_agent, COLD_START_SCORE)
        
        # Calculate confidence based on data availability
        records = self.tracker._records.get(best_agent, [])
        task_records = [r for r in records if r.get("task_type") == task_type]
        
        if task_records:
            # More records = higher confidence, cap at 0.95
            confidence = min(0.5 + (len(task_records) * 0.05), 0.95)
            reason = f"Selected based on {len(task_records)} prior '{task_type}' tasks (score: {best_score:.3f})"
        else:
            # No data - low confidence
            confidence = 0.3
            reason = f"No prior '{task_type}' experience; using cold-start score"
        
        return RoutingDecision(
            agent_id=best_agent,
            confidence=confidence,
            task_type=task_type,
            reason=reason
        )
    
    def get_specialization_report(self) -> Dict:
        """
        Generate a report of agent specializations.
        
        Returns:
            Dict with task_type -> best_agent mappings and confidence scores
        """
        report = {
            "agent_specializations": {},
            "task_type_experts": {},
        }
        
        # Collect all task types seen
        all_task_types: Set[str] = set()
        for records in self.tracker._records.values():
            for r in records:
                if "task_type" in r:
                    all_task_types.add(r["task_type"])
        
        # For each task type, find the expert
        for task_type in all_task_types:
            agents = list(self.tracker._records.keys())
            task_scores = self.get_task_scores(agents, task_type)
            
            if task_scores:
                best_agent = max(agents, key=lambda a: task_scores.get(a, 0))
                best_score = task_scores.get(best_agent, 0)
                
                report["task_type_experts"][task_type] = {
                    "agent_id": best_agent,
                    "score": round(best_score, 3),
                }
        
        # Per-agent specializations
        for agent_id in self.tracker._records:
            records = self.tracker._records[agent_id]
            task_types = {}
            
            for task_type in all_task_types:
                task_records = [r for r in records if r.get("task_type") == task_type]
                if task_records:
                    score = compute_pheromone(task_records)
                    task_types[task_type] = {
                        "count": len(task_records),
                        "score": round(score, 3),
                    }
            
            if task_types:
                # Sort by score
                sorted_tasks = sorted(
                    task_types.items(), 
                    key=lambda x: x[1]["score"], 
                    reverse=True
                )
                report["agent_specializations"][agent_id] = {
                    "top_tasks": sorted_tasks[:3],
                    "all_tasks": task_types,
                }
        
        return report


# Convenience function for coordinator integration
def route_with_task_type(
    tracker: PerformanceTracker,
    candidates: List[str],
    task: str,
    task_type: Optional[str] = None
) -> str:
    """
    Convenience function to route a task and return just the agent ID.
    
    Args:
        tracker: PerformanceTracker instance
        candidates: List of agent IDs
        task: Task description
        task_type: Optional explicit task type
        
    Returns:
        Selected agent ID
    """
    router = TaskTypeRouter(tracker)
    decision = router.route_task(candidates, task, task_type)
    return decision.agent_id
