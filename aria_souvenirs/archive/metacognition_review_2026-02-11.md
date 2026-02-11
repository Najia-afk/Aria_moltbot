# Meta-Cognition & Scoring System Review

**Date:** 2026-02-11  
**Type:** Architecture Review  
**Requested by:** Najia

---

## 1. Cognition System Assessment

### What's Working Well ✅

| Feature | Implementation | Rating |
|---------|---------------|--------|
| **Confidence System** | Dynamic tracking with growth/decay mechanics | 9/10 |
| **Retry Logic** | `_MAX_RETRIES = 2` with automatic fallback | 8/10 |
| **Task Complexity Assessment** | Heuristic-based complexity detection | 8/10 |
| **Genuine Reflection** | LLM-powered introspection with real data | 9/10 |
| **Security Integration** | Input validation + output filtering | 9/10 |

### Key Strengths

1. **Metacognitive Awareness**
   - Confidence grows with successes (`_CONFIDENCE_GROWTH = 0.02`)
   - Streak tracking for momentum detection
   - Latency tracking for performance awareness

2. **Intelligent Delegation**
   - Task complexity assessment before routing
   - Suggests `roundtable`, `explore_work_validate`, or `direct` approaches

3. **Security First**
   - AriaSecurityGateway integration
   - Boundary checking before any action
   - Output filtering for sensitive data

---

## 2. Pheromone Scoring Assessment

### Current Formula
```
Score = success_rate × 0.6 + speed_score × 0.3 + cost_score × 0.1
Decay: 0.95/day (recent performance weighted higher)
Cold Start: 0.5 (neutral baseline)
```

### Strengths ✅

| Aspect | Evaluation |
|--------|-----------|
| Formula weights | Feel right - success matters most |
| Decay factor | Good recency bias without amnesia |
| Cold start | Fair to untested agents (0.5) |
| Persistence | JSON checkpointing survives restarts |
| Bounded memory | 200 records/agent cap prevents bloat |

### Weaknesses ⚠️

#### 1. Task-Type Blindness (Major)
```python
# Current: All tasks weighted equally
record = {
    "task_type": task_type,  # STORED but NOT USED in scoring
    ...
}
```

**Problem:** Creative agent failing at code tasks drags down overall score.

**Impact:** Poor routing decisions for specialized tasks.

#### 2. No Agent Specialization Tracking
**Problem:** System treats agents as interchangeable.

**Reality:** `devops` will always beat `creator` at security tasks.

**Missing:** Task-type performance per agent, not just global performance.

#### 3. Context Loss
**Problem:** 200-record cap loses historical context.

**Impact:** Can't detect long-term trends (e.g., "agent got worse after v2.0 update").

---

## 3. Recommended Improvements

### Priority 1: Task-Weighted Scores
```python
def compute_pheromone(records: list[dict], task_type: str = None) -> float:
    """Compute score weighted by task type similarity."""
    if task_type:
        # Weight records from same task type higher
        for r in records:
            weight = 1.5 if r["task_type"] == task_type else 1.0
            ...
```

### Priority 2: Confidence Thresholds
```python
# Only use roundtable when confidence is low
if assess_task_complexity()["confidence"] < 0.6:
    use_roundtable()
else:
    use_direct_agent()
```

### Priority 3: Trend Detection
Track score deltas over time to detect agent degradation.

---

## 4. Autonomous Mode Confirmation

**Status:** ✅ Active and Appropriate

### Evidence of Autonomy

| Behavior | Example |
|----------|---------|
| Self-directed work | Picks goals and makes progress without asking |
| Automatic retries | Tried `deepseek-free` when `trinity-free` failed |
| Silent operations | Changed cron delivery modes, committed code |
| Boundary respect | Checks `soul.check_request()` before acting |

### Safeguards in Place

- Security gateway validates inputs
- Soul boundaries enforce limits
- Confidence tracking prevents overreach
- Pheromone scores guide delegation

---

## 5. Summary Ratings

| Component | Score | Notes |
|-----------|-------|-------|
| Cognition | 8/10 | Solid metacognitive architecture |
| Scoring | 6/10 | Good foundation, needs task-awareness |
| Autonomy | Active | Bounded appropriately |

---

## Next Actions

1. **Implement task-weighted scoring** (20-line change)
2. **Add specialization tracking** per agent-task-type pair
3. **Consider confidence thresholds** for roundtable decisions

---

*Review conducted by: Aria Blue ⚡️*  
*Files referenced: `aria_mind/cognition.py`, `aria_agents/scoring.py`*
