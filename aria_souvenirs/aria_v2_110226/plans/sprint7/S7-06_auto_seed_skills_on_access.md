# S7-06: Auto-Seed Skills on First Access

## Summary
The Skills page shows empty because `skill_status` table has 0 rows. The skill graph (vis.js) works fine because it uses `skill_graph_entities` (populated by `POST /skills/seed` at startup). But skill_status is a separate tracking table that was never seeded. Fix: auto-seed skill_status from available skill directories on first access if empty.

## Priority / Points
- **Priority**: P2-Medium
- **Story Points**: 2
- **Sprint**: 7 — Dashboard Data Fixes

## Acceptance Criteria
- [ ] GET /skills returns skill data (not empty list) even if skill_status table is empty
- [ ] Either auto-seed skill_status on first GET /skills, or fetch live from skill registry
- [ ] Skills page shows available skills with names and status
- [ ] Skill stats page shows basic info

## Technical Details

### Option A: Auto-seed on first access
In the GET /skills endpoint, if `skill_status` table is empty, scan the `aria_skills/` directory for `skill.json` files and create initial `SkillStatus` entries.

### Option B: Fallback to registry (preferred)
If `skill_status` has no rows, query the skill registry/catalog as a fallback. The skill catalog (`aria_skills/catalog.py`) already has a function to discover skills.

### Files
| File | Change |
|------|--------|
| src/api/routers/skills.py | Add fallback: if skill_status empty, scan registry |
| src/api/db/models.py | Verify SkillStatus model matches expected fields |

## Verification
```bash
# Current state (empty):
docker exec aria-db psql -U aria_admin -d aria_warehouse -c "SELECT COUNT(*) FROM skill_status"
# After fix:
curl -s 'http://localhost:8000/skills' | python3 -m json.tool | head -20
# Should return skill entries
```

## Dependencies
- None (independent)
