# S1-11: DB Cleanup (Garbage Goals, Duplicates)

**Priority:** Medium | **Estimate:** 1 pt | **Status:** TODO

---

## Problem

The PostgreSQL `goals` table contains garbage test data, stale entries, and duplicates that pollute dashboards, inflate goal counts, and confuse the goal-tracking system.

### Garbage Data Inventory

| Name | ID | Progress | Created | Verdict |
|------|----|----------|---------|---------|
| "Test Goal" | `44a6cef0` | 0% | Test data | **DELETE** |
| "Test Goal" | `11c7b585` | 0% | Test data | **DELETE** |
| "Test Goal" | `8438cbda` | 0% | Test data | **DELETE** |
| "Live test goal" | `f271bb78` | 0% | Test data | **DELETE** |
| "Live test goal" | `46dc2a25` | 0% | Test data | **DELETE** |
| "Learn Python" | `9fae36ae` | 0% | Duplicate | **DELETE** |
| "Learn Python" | `5dca3dbe` | 5% | Original | **KEEP** (higher progress) |
| "Patchable" | `364320b9` | 0% | Test data | **DELETE** |
| "Patchable" | `c6851d67` | 0% | Test data | **DELETE** |
| "📊 Build Token Dashboard" | — | 0% | Stale | **REVIEW** (delete if confirmed stale) |
| "[Hourly] Learn: Research Crypto Market Trends" | — | 0% pending | Auto-created | **KEEP** |

**Total deletions: 9 rows** (3× "Test Goal", 2× "Live test goal", 1× "Learn Python" dup, 2× "Patchable")

---

## Root Cause

1. Test/development goals were created during feature testing and never cleaned up
2. No deduplication logic in the goal creation flow
3. No automated garbage collection for 0%-progress goals older than N days

---

## Fix

### SQL DELETE statements

Execute via: `docker exec aria-db psql -U aria_admin -d aria_warehouse`

```sql
-- ============================================================
-- S1-11: Goal table cleanup
-- Date: 2026-02-11
-- ============================================================

BEGIN;

-- 1. Delete "Test Goal" entries (3 rows)
DELETE FROM goals WHERE id IN (
    '44a6cef0',
    '11c7b585',
    '8438cbda'
) AND title = 'Test Goal';

-- 2. Delete "Live test goal" entries (2 rows)  
DELETE FROM goals WHERE id IN (
    'f271bb78',
    '46dc2a25'
) AND title = 'Live test goal';

-- 3. Delete duplicate "Learn Python" (keep 5dca3dbe which has 5% progress)
DELETE FROM goals WHERE id = '9fae36ae'
    AND title = 'Learn Python';

-- 4. Delete "Patchable" entries (2 rows)
DELETE FROM goals WHERE id IN (
    '364320b9',
    'c6851d67'
) AND title = 'Patchable';

-- 5. Review: "Build Token Dashboard" — uncomment to delete if confirmed stale
-- DELETE FROM goals WHERE title LIKE '%Build Token Dashboard%' AND progress = 0;

-- Verify deletions
SELECT COUNT(*) AS remaining_goals FROM goals;
SELECT title, progress, status FROM goals ORDER BY created_at DESC LIMIT 20;

COMMIT;
```

### Pre-flight audit query (run first to verify targets)

```sql
-- Run this BEFORE the DELETE to confirm targets
SELECT id, title, progress, status, created_at
FROM goals
WHERE title IN ('Test Goal', 'Live test goal', 'Learn Python', 'Patchable')
   OR title LIKE '%Build Token Dashboard%'
ORDER BY title, progress DESC;
```

---

## Constraints

| # | Constraint | Status |
|---|-----------|--------|
| 1 | Use transaction (BEGIN/COMMIT) for safety | ✅ Wrapped in transaction |
| 2 | Verify IDs match titles before deletion | ✅ WHERE includes both id AND title |
| 3 | Keep the higher-progress duplicate | ✅ Keeping 5dca3dbe (5%) |
| 4 | Don't delete auto-created hourly goals | ✅ "[Hourly] Learn..." excluded |
| 5 | No schema changes | ✅ DML only (DELETE) |
| 6 | Backup before destructive operations | ⚠️ Run pre-flight audit first |

---

## Dependencies

| Dependency | Type | Notes |
|-----------|------|-------|
| `aria-db` container | Runtime | Must be running: `docker ps \| grep aria-db` |
| PostgreSQL access | Runtime | User `aria_admin`, database `aria_warehouse` |
| No active goal processing | Timing | Run during low-activity period to avoid conflicts |

---

## Verification

```bash
# 1. Connect to database
docker exec aria-db psql -U aria_admin -d aria_warehouse -c "SELECT COUNT(*) FROM goals;"
# Expected: Total count reduced by 8-9

# 2. Verify "Test Goal" entries are gone
docker exec aria-db psql -U aria_admin -d aria_warehouse -c \
  "SELECT COUNT(*) FROM goals WHERE title = 'Test Goal';"
# Expected: 0

# 3. Verify "Live test goal" entries are gone
docker exec aria-db psql -U aria_admin -d aria_warehouse -c \
  "SELECT COUNT(*) FROM goals WHERE title = 'Live test goal';"
# Expected: 0

# 4. Verify only one "Learn Python" remains (the 5% one)
docker exec aria-db psql -U aria_admin -d aria_warehouse -c \
  "SELECT id, title, progress FROM goals WHERE title = 'Learn Python';"
# Expected: 1 row, id starts with 5dca3dbe, progress = 5

# 5. Verify "Patchable" entries are gone
docker exec aria-db psql -U aria_admin -d aria_warehouse -c \
  "SELECT COUNT(*) FROM goals WHERE title = 'Patchable';"
# Expected: 0

# 6. Verify hourly goal is still present
docker exec aria-db psql -U aria_admin -d aria_warehouse -c \
  "SELECT COUNT(*) FROM goals WHERE title LIKE '%Hourly%Research Crypto%';"
# Expected: 1
```

---

## Prompt for Agent

```
Connect to the Aria database:
  docker exec aria-db psql -U aria_admin -d aria_warehouse

First, run the pre-flight audit to verify targets:
  SELECT id, title, progress, status, created_at
  FROM goals
  WHERE title IN ('Test Goal', 'Live test goal', 'Learn Python', 'Patchable')
     OR title LIKE '%Build Token Dashboard%'
  ORDER BY title, progress DESC;

Confirm the IDs match the expected garbage entries. Then execute the cleanup in a transaction:

BEGIN;

DELETE FROM goals WHERE id IN ('44a6cef0', '11c7b585', '8438cbda') AND title = 'Test Goal';
DELETE FROM goals WHERE id IN ('f271bb78', '46dc2a25') AND title = 'Live test goal';
DELETE FROM goals WHERE id = '9fae36ae' AND title = 'Learn Python';
DELETE FROM goals WHERE id IN ('364320b9', 'c6851d67') AND title = 'Patchable';

SELECT COUNT(*) AS remaining_goals FROM goals;

COMMIT;

Keep the "Learn Python" with id 5dca3dbe (5% progress).
Keep the "[Hourly] Learn: Research Crypto Market Trends" entry.
For "📊 Build Token Dashboard" — review and delete only if confirmed stale (0% progress, no recent activity).

Verify: "SELECT COUNT(*) FROM goals WHERE title IN ('Test Goal', 'Live test goal', 'Patchable');" should return 0.
```
