# aria_agents/scoring.py
"""
Pheromone-inspired agent scoring.

Score formula: success_rate * 0.6 + speed_score * 0.3 + cost_score * 0.1
Decay factor: 0.95 per day (recent performance matters more).
Cold start: 0.5 (neutral — don't penalize untested agents).
"""
from datetime import datetime, timezone

DECAY_FACTOR = 0.95
WEIGHTS = {"success": 0.6, "speed": 0.3, "cost": 0.1}
COLD_START_SCORE = 0.5


def compute_pheromone(records: list[dict]) -> float:
    """Compute pheromone score from performance records.

    Args:
        records: List of dicts with keys: success (bool), speed_score (float 0-1),
                 cost_score (float 0-1), created_at (datetime).

    Returns:
        Float score between 0.0 and 1.0.
    """
    if not records:
        return COLD_START_SCORE

    score = 0.0
    weight_sum = 0.0
    now = datetime.now(timezone.utc)

    for r in records:
        created = r.get("created_at", now)
        if isinstance(created, str):
            # Handle ISO format strings
            created = datetime.fromisoformat(created.replace("Z", "+00:00"))
        age_days = max((now - created).total_seconds() / 86400, 0)
        decay = DECAY_FACTOR ** age_days

        s = (
            float(r.get("success", False)) * WEIGHTS["success"]
            + r.get("speed_score", 0.5) * WEIGHTS["speed"]
            + r.get("cost_score", 0.5) * WEIGHTS["cost"]
        )
        score += s * decay
        weight_sum += decay

    return score / weight_sum if weight_sum > 0 else COLD_START_SCORE


def select_best_agent(
    candidates: list[str],
    scores: dict[str, float],
) -> str:
    """Select the best agent from candidates based on pheromone scores.

    Args:
        candidates: List of agent IDs to choose from.
        scores: Dict mapping agent_id -> pheromone score.

    Returns:
        Agent ID with the highest score. Falls back to first candidate.
    """
    if not candidates:
        raise ValueError("No candidate agents provided")

    return max(candidates, key=lambda a: scores.get(a, COLD_START_SCORE))
