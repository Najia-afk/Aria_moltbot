# Agent-Managing-Agent System Architecture

## Core Concept
Hierarchical swarm where a Meta-Agent coordinates specialized sub-agents, each with pheromone scoring for adaptive delegation.

## Components

### 1. Meta-Agent (Orchestrator)
- Receives all incoming tasks
- Analyzes task type and complexity
- Selects optimal sub-agent via pheromone scoring
- Monitors sub-agent performance
- Escalates/retry on failure

### 2. Sub-Agent Pool
| Agent | Focus | Scoring Weight |
|-------|-------|----------------|
| devops | DevSecOps | success_rate × 0.6 + speed × 0.3 + cost × 0.1 |
| analyst | Data/Trading | same formula |
| creator | Creative/Social | same formula |
| memory | Storage/Recall | same formula |

### 3. Pheromone System
- Tracks: success/failure, latency, token cost per task
- Decay: 0.95/day (recent performance weighted)
- Cold-start: 0.5 (neutral for untested agents)

## Task Flow
```
Task → Meta-Agent → Classify → Score Agents → Delegate → Monitor → Update Score
```

## Implementation Status
- [x] Base agent classes (aria_agents/base.py)
- [x] Pheromone scoring (aria_agents/scoring.py)
- [ ] Meta-Agent orchestrator loop
- [ ] Failure recovery & retry logic
- [ ] Performance dashboard

## Next Action
Implement Meta-Agent delegation loop with health monitoring.
