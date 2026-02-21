# S7-02: Fix Working Memory JSONB Display

## Summary
Working Memory page shows "Failed to load" because the `value` column is JSONB (objects/arrays), but the template calls `.substring()` and `.replace()` on it — which throws `TypeError: item.value.substring is not a function`. Fix: use `JSON.stringify()` for non-string values before string operations.

**Data exists:** 5 rows in working_memory table, but page shows error.

## Priority / Points
- **Priority**: P0-Critical
- **Story Points**: 2
- **Sprint**: 7 — Dashboard Data Fixes

## Acceptance Criteria
- [ ] Working memory page loads without "Failed to load" error
- [ ] All 5 working memory items display correctly
- [ ] JSONB objects render as formatted JSON (pretty-printed or truncated preview)
- [ ] String values still display normally

## Technical Details
In `src/web/templates/working_memory.html` around lines 264-273, the code does:
```javascript
const preview = item.value.substring(0, 100);  // FAILS: .substring() not on objects
const cleaned = item.value.replace(/"/g, '&quot;');  // FAILS: .replace() not on objects
```

Fix: Convert JSONB to string first:
```javascript
const valueStr = typeof item.value === 'string' ? item.value : JSON.stringify(item.value, null, 2);
const preview = valueStr.substring(0, 100);
const cleaned = valueStr.replace(/"/g, '&quot;');
```

## Files to Modify
| File | Change |
|------|--------|
| src/web/templates/working_memory.html | Add type check + JSON.stringify before .substring()/.replace() |

## Verification
```bash
curl -s 'http://localhost:8000/working-memory' | python3 -m json.tool | head -20
# Then load /working-memory page and confirm items display
```

## Dependencies
- None (independent fix)
