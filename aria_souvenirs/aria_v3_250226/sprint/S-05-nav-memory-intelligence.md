# S-05: Regroup Navigation — Memory & Intelligence
**Epic:** E3 — Nav Regrouping | **Priority:** P0 | **Points:** 5 | **Phase:** 1

## Problem
The current navigation in `src/web/templates/base.html` L131-L280 has **overlapping** Memory and Intelligence sections:
- **Overview** (6 items): dashboard, sessions, memories, knowledge, analytics, creative-pulse
- **Intelligence** (11 items): sentiment, thinking, cognitive, goals, metacognition, context-analysis, semantic-connections, cognitive-patterns, temporal-analysis, behavioral-patterns, metrics

"Overview" mixes dashboard (nav item) with memory pages (memories, knowledge). "Intelligence" has 11 items — too many for a single dropdown. Some pages show the same data differently (cognitive vs cognitive-patterns). The user said: "for overview + intelligence a lot can be under memory header menu and regroup."

## Root Cause
Pages were added organically. No information architecture review was done since initial build.

## Fix

### Fix 1: Create "Memory" nav group
**File:** `src/web/templates/base.html` L131-L280

**New "Memory" dropdown contains:**
| Label | Route | Source |
|-------|-------|--------|
| Memories | `/memories` | was in Overview |
| Knowledge | `/knowledge` | was in Overview |
| Semantic Connections | `/semantic-connections` | was in Intelligence |
| Context Analysis | `/context-analysis` | was in Intelligence |
| Temporal Analysis | `/temporal-analysis` | was in Intelligence |
| Analytics | `/analytics` | was in Overview |

### Fix 2: Slim down "Intelligence" to analysis/metrics only
**Renamed to "Intelligence" (6 items):**
| Label | Route | Source |
|-------|-------|--------|
| Sentiment | `/sentiment` | was in Intelligence |
| Thinking | `/thinking` | was in Intelligence |
| Cognitive Patterns | `/cognitive-patterns` | was in Intelligence |
| Behavioral Patterns | `/behavioral-patterns` | was in Intelligence |
| Metacognition | `/metacognition` | was in Intelligence |
| Metrics | `/metrics` | was in Intelligence |

### Fix 3: Keep "Overview" as a dashboard-only section
**"Overview" reduced to 3 items:**
| Label | Route |
|-------|-------|
| Dashboard | `/dashboard` |
| Sessions | `/sessions` |
| Creative Pulse | `/creative-pulse` |

### Fix 4: Move `/cognitive` and `/goals`
- `/cognitive` → check if it's a duplicate of `/cognitive-patterns`. If so, redirect 301 → `/cognitive-patterns`
- `/goals` → move to Operations (it's operational, not intelligence)

### Fix 5: Update base.html nav HTML
**File:** `src/web/templates/base.html` L131-L280
Rewrite the `<li class="nav-item dropdown">` blocks for Overview, Intelligence and add new Memory block.

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer architecture | ❌ | Frontend nav only |
| 2 | .env for secrets | ❌ | No secrets |
| 3 | models.yaml truth | ❌ | No models |
| 4 | Docker-first testing | ✅ | Test via Docker |
| 5 | aria_memories writable | ❌ | No file writes |
| 6 | No soul modification | ❌ | No soul changes |

## Dependencies
- S-13 (dead code cleanup) should ideally come first to remove dead routes, but not blocking

## Verification
```bash
# 1. Verify Memory dropdown exists in nav:
grep -c 'Memory' src/web/templates/base.html
# EXPECTED: ≥ 1 (the dropdown label)

# 2. Verify Overview has ≤ 3 items:
# Manual: Open http://localhost:5050 and check Overview dropdown

# 3. Verify Intelligence has ≤ 6 items:
# Manual: Check Intelligence dropdown

# 4. Verify all routes still resolve:
for route in /memories /knowledge /semantic-connections /context-analysis /temporal-analysis /analytics /sentiment /thinking /cognitive-patterns /behavioral-patterns /metacognition /metrics /dashboard /sessions /creative-pulse; do
  code=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5050$route)
  echo "$route: $code"
done
# EXPECTED: All 200

# 5. Verify /cognitive redirects:
curl -s -o /dev/null -w "%{http_code}" http://localhost:5050/cognitive
# EXPECTED: 301
```

## Prompt for Agent
```
Read these files FIRST:
- src/web/templates/base.html (L100-L300 — full nav section)
- src/web/app.py (full — all route definitions)
- src/web/templates/ — list all template files

CONSTRAINTS: No backend changes needed. Frontend nav restructuring only.

STEPS:
1. Read the current nav structure in base.html completely
2. Identify which pages belong to Memory vs Intelligence vs Overview
3. Compare /cognitive and /cognitive-patterns routes — if same template, add 301 redirect
4. Move /goals to Operations dropdown
5. Create new "Memory" nav dropdown with: Memories, Knowledge, Semantic Connections, Context Analysis, Temporal Analysis, Analytics
6. Reduce "Intelligence" to: Sentiment, Thinking, Cognitive Patterns, Behavioral Patterns, Metacognition, Metrics
7. Reduce "Overview" to: Dashboard, Sessions, Creative Pulse
8. Ensure the dropdown HTML follows the same pattern as existing dropdowns (Bootstrap classes, icons)
9. Add appropriate Font Awesome icons for Memory section (fa-brain, fa-database, etc.)
10. Verify all routes still work by checking app.py
11. Run verification commands
```
