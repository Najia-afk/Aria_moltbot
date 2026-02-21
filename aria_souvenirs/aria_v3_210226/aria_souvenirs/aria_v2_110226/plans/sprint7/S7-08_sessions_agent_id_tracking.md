# S7-08: Sessions Agent ID Tracking for Swarm

## Summary
Sessions page only shows "main" agent (3,523 sessions) and "pytest" (4 sessions). Swarm agents (coordinator, researcher, etc.) don't pass their `agent_id` when creating sessions — they all default to "main". Fix: ensure swarm agent sessions are tagged with their actual agent name.

## Priority / Points
- **Priority**: P2-Medium
- **Story Points**: 3
- **Sprint**: 7 — Dashboard Data Fixes

## Acceptance Criteria
- [ ] Swarm agents pass their agent_id when creating sessions
- [ ] Sessions page shows breakdown by actual agent (coordinator, researcher, etc.)
- [ ] Existing sessions remain unaffected
- [ ] Sessions filter by agent_id works

## Technical Details
- The `agent_id` field exists on the Session model and API endpoint
- The issue is at the caller level — swarm agents call `api_client.create_session()` without an `agent_id` param
- Need to trace where sessions are created in agent/coordinator code and pass the agent name

### Key files to investigate:
- `aria_agents/coordinator.py` — creates sessions for swarm orchestration
- `aria_agents/base.py` — base agent might create sessions
- `aria_skills/api_client/__init__.py` — `create_session()` method
- `aria_mind/cognition.py` — main cognitive loop creates "main" sessions

## Files to Modify
| File | Change |
|------|--------|
| aria_agents/coordinator.py | Pass agent_id when creating sessions |
| aria_agents/base.py | Pass self.name as agent_id |
| aria_skills/api_client/__init__.py | Ensure agent_id param is forwarded |

## Verification
```bash
# After fix, trigger a swarm task, then check:
docker exec aria-db psql -U aria_admin -d aria_warehouse -c \
  "SELECT agent_id, COUNT(*) FROM sessions GROUP BY agent_id ORDER BY count DESC"
# Should show more than just 'main' and 'pytest'
```

## Dependencies
- None (independent, but requires swarm execution to verify)
