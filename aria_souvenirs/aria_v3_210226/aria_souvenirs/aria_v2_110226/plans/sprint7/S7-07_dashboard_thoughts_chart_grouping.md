# S7-07: Dashboard Thoughts Chart Category Grouping

## Summary
The "Thoughts by Type" doughnut chart on the dashboard has too many subcategories — the `category` field has fine-grained values like "reflection", "analysis", "observation", "planning", etc. A doughnut chart with 15+ slices is unreadable. Fix: group into 4-5 high-level categories.

## Priority / Points
- **Priority**: P2-Low
- **Story Points**: 2
- **Sprint**: 7 — Dashboard Data Fixes

## Acceptance Criteria
- [ ] Thoughts doughnut chart groups into ≤6 high-level categories
- [ ] Small categories rolled into "Other"
- [ ] Chart is readable with clear labels
- [ ] Tooltip still shows count per category

## Technical Details

### Current (dashboard.html ~line 416):
```javascript
const raw = await fetch(`${API_URL}/thoughts?limit=100`);
// Uses raw category field → 15+ slices
```

### Fix options:

**Option A: Client-side grouping** (simplest)
```javascript
const categoryMap = {
    'reflection': 'Reflection', 'self-reflection': 'Reflection',
    'analysis': 'Analysis', 'observation': 'Analysis',
    'planning': 'Planning', 'strategy': 'Planning',
    'creative': 'Creative', 'idea': 'Creative',
    // everything else → 'Other'
};
```

**Option B: Server-side aggregation** (cleaner)
Add `GET /thoughts/by-type` that returns pre-grouped counts:
```python
@router.get("/thoughts/by-type")
async def thoughts_by_type(db = Depends(get_db)):
    result = await db.execute(
        select(Thought.category, func.count(Thought.id))
        .group_by(Thought.category)
    )
    return [{"category": r[0], "count": r[1]} for r in result.all()]
```

## Files to Modify
| File | Change |
|------|--------|
| src/web/templates/dashboard.html | Group categories or use new endpoint |
| src/api/routers/thoughts.py (optional) | Add /thoughts/by-type aggregation |

## Dependencies
- None (independent, cosmetic improvement)
