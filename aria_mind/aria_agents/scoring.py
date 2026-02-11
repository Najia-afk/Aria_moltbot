"""Agent scoring system — pheromone-based performance tracking.

Implements adaptive agent selection based on historical performance.
Score formula: success_rate × 0.6 + speed_score × 0.3 + cost_score × 0.1
"""
import json
import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Constants from AGENTS.md
DECAY_FACTOR = 0.95  # Per day
COLD_START_SCORE = 0.5
MAX_RECORDS_PER_AGENT = 200


def compute_pheromone(records: list[dict]) -> float:
    """Compute pheromone score from performance records.
    
    Formula: success_rate × 0.6 + speed_score × 0.3 + cost_score × 0.1
    With time decay factor of 0.95/day.
    
    Args:
        records: List of performance records for an agent
        
    Returns:
        Float score between 0.0 and 1.0
    """
    if not records:
        return COLD_START_SCORE
    
    now = time.time()
    weights = []
    successes = []
    speeds = []
    costs = []
    
    for record in records:
        age_days = (now - record.get("timestamp", now)) / 86400
        weight = DECAY_FACTOR ** age_days
        weights.append(weight)
        
        successes.append(1.0 if record.get("success", False) else 0.0)
        # Speed: inverse of duration (normalized later)
        duration = record.get("duration_ms", 60000)
        speeds.append(1.0 / max(duration, 1))
        # Cost: normalized tokens (lower is better)
        tokens = record.get("tokens_used", 1000)
        costs.append(1.0 / max(tokens, 1))
    
    if not weights:
        return COLD_START_SCORE
    
    total_weight = sum(weights)
    
    # Weighted averages
    success_rate = sum(s * w for s, w in zip(successes, weights)) / total_weight
    
    # Normalize speeds (max speed = best)
    max_speed = max(speeds) if speeds else 1.0
    speed_score = sum((s / max_speed) * w for s, w in zip(speeds, weights)) / total_weight
    
    # Normalize costs (min cost = best)
    max_cost = max(costs) if costs else 1.0
    cost_score = sum((s / max_cost) * w for s, w in zip(costs, weights)) / total_weight
    
    # Final formula
    score = success_rate * 0.6 + speed_score * 0.3 + cost_score * 0.1
    return min(max(score, 0.0), 1.0)


def select_best_agent(candidates: list[str], scores: dict[str, float]) -> str | None:
    """Select the highest-scoring agent from candidates.
    
    Args:
        candidates: List of agent IDs to consider
        scores: Dict mapping agent_id to pheromone score
        
    Returns:
        The agent_id with highest score, or None if no candidates
    """
    if not candidates:
        return None
    
    best = None
    best_score = -1.0
    
    for agent_id in candidates:
        score = scores.get(agent_id, COLD_START_SCORE)
        if score > best_score:
            best_score = score
            best = agent_id
    
    return best


@dataclass
class PerformanceRecord:
    """Single performance record for an agent invocation."""
    agent_id: str
    task_type: str
    success: bool
    duration_ms: int
    tokens_used: int
    timestamp: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)


class PerformanceTracker:
    """Tracks agent performance and persists scores to disk."""
    
    def __init__(self, storage_path: Path | None = None):
        """Initialize tracker with optional custom storage path.
        
        Args:
            storage_path: Path to JSON file for persistence.
                         Defaults to aria_memories/skills/agent_performance.json
        """
        if storage_path is None:
            storage_path = Path("/root/.openclaw/aria_memories/skills/agent_performance.json")
        self.storage_path = storage_path
        self._records: dict[str, list[dict]] = {}
        self._scores: dict[str, float] = {}
        self._load()
    
    def _load(self) -> None:
        """Load records from disk."""
        if self.storage_path.exists():
            try:
                data = json.loads(self.storage_path.read_text())
                self._records = data.get("records", {})
                self._scores = data.get("scores", {})
            except (json.JSONDecodeError, IOError):
                self._records = {}
                self._scores = {}
    
    def _save(self) -> None:
        """Save records to disk."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "records": self._records,
            "scores": self._scores,
            "last_updated": time.time()
        }
        self.storage_path.write_text(json.dumps(data, indent=2))
    
    def record(self, record: PerformanceRecord) -> None:
        """Record a performance entry and update scores.
        
        Args:
            record: PerformanceRecord to store
        """
        agent_id = record.agent_id
        
        # Initialize if needed
        if agent_id not in self._records:
            self._records[agent_id] = []
        
        # Add record
        self._records[agent_id].append({
            "task_type": record.task_type,
            "success": record.success,
            "duration_ms": record.duration_ms,
            "tokens_used": record.tokens_used,
            "timestamp": record.timestamp,
            "metadata": record.metadata
        })
        
        # Prune old records
        if len(self._records[agent_id]) > MAX_RECORDS_PER_AGENT:
            # Keep most recent
            self._records[agent_id] = self._records[agent_id][-MAX_RECORDS_PER_AGENT:]
        
        # Recompute score
        self._scores[agent_id] = compute_pheromone(self._records[agent_id])
        
        # Persist
        self._save()
    
    def get_score(self, agent_id: str) -> float:
        """Get current pheromone score for an agent.
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            Pheromone score (0.0-1.0), or COLD_START_SCORE if unknown
        """
        return self._scores.get(agent_id, COLD_START_SCORE)
    
    def get_scores(self) -> dict[str, float]:
        """Get all agent scores.
        
        Returns:
            Dict mapping agent_id to score
        """
        return self._scores.copy()
    
    def select_for_task(self, candidates: list[str]) -> str | None:
        """Select best agent for a task from candidates.
        
        Args:
            candidates: List of agent IDs that can handle the task
            
        Returns:
            Best agent_id or None
        """
        return select_best_agent(candidates, self._scores)
    
    def get_history(self, agent_id: str, limit: int = 10) -> list[dict]:
        """Get recent performance history for an agent.
        
        Args:
            agent_id: Agent identifier
            limit: Max records to return
            
        Returns:
            List of performance records
        """
        records = self._records.get(agent_id, [])
        return records[-limit:] if records else []


# Global instance for convenience
default_tracker = PerformanceTracker()
