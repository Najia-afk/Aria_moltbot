# S3-08: Verify & Test Sprint 3 — Frontend Deduplication
**Epic:** Sprint 3 — Frontend Deduplication | **Priority:** P0 | **Points:** 2 | **Phase:** 3

## Problem
Sprint 3 introduced significant frontend refactoring. Need to verify:
1. All shared utility files exist and are properly loaded
2. All 15+ pages load without JavaScript errors
3. Interactive features (charts, filters, pagination) still work
4. No regressions from function extraction
5. Architecture checker shows 0 duplicate warnings (down from 13)

## Root Cause
Refactoring JS across 15+ pages carries high regression risk. Need systematic verification.

## Fix
Run the complete verification checklist below. Any failure = fix before proceeding to Sprint 4.

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ❌ | Verification only |
| 2 | .env secrets | ❌ | No secrets |
| 3 | models.yaml SSOT | ❌ | No models |
| 4 | Docker-first | ✅ | All tests inside container |
| 5 | aria_memories writable | ✅ | Write verification log |
| 6 | No soul modification | ❌ | Not touching soul |

## Dependencies
S3-01 through S3-07 must all be complete.

## Verification
```bash
# ═══════════════ SHARED JS FILES ═══════════════
echo "=== Checking shared JS files ==="
for f in aria-common.js utils.js pagination.js pricing.js; do
  ls -la "src/web/static/js/$f" 2>/dev/null && echo "✅ $f exists" || echo "❌ $f MISSING"
done

# ═══════════════ PAGE LOADS ═══════════════
echo -e "\n=== Checking all pages ==="
PAGES="/ /goals /thoughts /memories /models /wallets /sessions /knowledge /sprint-board /skills /heartbeat /activities /social /security /settings"
PASS=0; FAIL=0
for page in $PAGES; do
  CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:5000$page")
  if [ "$CODE" = "200" ]; then
    echo "✅ $page ($CODE)"
    PASS=$((PASS+1))
  else
    echo "❌ $page ($CODE)"
    FAIL=$((FAIL+1))
  fi
done
echo "Pages: $PASS passed, $FAIL failed"

# ═══════════════ NO BARE CONSOLE.LOG ═══════════════
echo -e "\n=== Checking for bare console.log ==="
BARE=$(grep -rn "console\.log\b" src/web/templates/ --include="*.html" | grep -v "ariaLog\|ARIA_DEBUG\|// debug" | wc -l)
echo "Bare console.log statements: $BARE"
# EXPECTED: 0

# ═══════════════ NO UNESCAPED innerHTML ═══════════════
echo -e "\n=== Checking innerHTML XSS safety ==="
UNSAFE=$(grep -rn 'innerHTML.*\$\{' src/web/templates/ --include="*.html" | grep -v "escapeHtml" | wc -l)
echo "Unescaped innerHTML assignments: $UNSAFE"
# EXPECTED: 0

# ═══════════════ ARCHITECTURE CHECKER ═══════════════
echo -e "\n=== Running architecture checker ==="
python scripts/check_architecture.py 2>&1 | tail -5
# EXPECTED: 0 errors, 0 warnings (was 13 before Sprint 3)

# ═══════════════ DUPLICATE FUNCTIONS ═══════════════
echo -e "\n=== Checking for duplicate JS functions ==="
# Find functions defined in more than one template
grep -rn "function " src/web/templates/ --include="*.html" | \
  sed 's/.*function \([a-zA-Z_]*\).*/\1/' | sort | uniq -c | sort -rn | \
  awk '$1 > 1 {print "⚠️ DUPLICATE: " $2 " (" $1 " copies)"}'
# EXPECTED: no output (all duplicates extracted to shared files)

# ═══════════════ fetchWithRetry EXISTS ═══════════════
echo -e "\n=== Checking fetchWithRetry ==="
grep -c "fetchWithRetry\|showErrorState\|ariaLog\|ARIA_DEBUG" src/web/static/js/aria-common.js
# EXPECTED: >= 4

# ═══════════════ WRITE VERIFICATION LOG ═══════════════
echo -e "\n=== Writing verification log ==="
DATE=$(date +%Y%m%d_%H%M%S)
cat > "aria_memories/logs/sprint3_verification_${DATE}.md" << 'EOF'
# Sprint 3 Verification Log
- Date: $(date)
- Status: PASS/FAIL
- Pages tested: 15
- Architecture errors: 0
- Architecture warnings: 0
- Bare console.log: 0
- Unescaped innerHTML: 0
- Duplicate JS functions: 0
EOF
echo "✅ Verification log written"
```

## Prompt for Agent
```
Run the full Sprint 3 verification checklist. Fix trivial issues, log everything.

**Files to read FIRST (understand the state before testing):**
- src/web/static/js/aria-common.js (full — verify fetchWithRetry, ariaLog, ARIA_DEBUG are defined)
- src/web/static/js/utils.js (full — verify escapeHtml, formatTime, showToast exist)
- src/web/static/js/pagination.js (quick scan — verify it exists and exports functions)
- src/web/static/js/pricing.js (quick scan — verify it exists)
- scripts/check_architecture.py (lines 1-30 — understand what it checks for JS duplicates)

**Constraints:**
- Constraint 4 (Docker-first): all tests against running containers
- Constraint 5 (aria_memories): write verification log to aria_memories/logs/
- S3-01 through S3-07 must be complete before running this ticket

**Steps:**
1. Restart the web container to pick up all changes:
   a. Run: docker compose restart aria-web
   b. Wait 5 seconds, then: curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/
   c. EXPECTED: 200
2. Verify shared JS files exist:
   a. Run: for f in aria-common.js utils.js pagination.js pricing.js; do ls -la "src/web/static/js/$f" 2>/dev/null && echo "OK $f" || echo "MISSING $f"; done
   b. EXPECTED: all 4 files exist
3. Verify shared functions are defined:
   a. Run: grep -c "fetchWithRetry\|showErrorState\|ariaLog\|ARIA_DEBUG\|escapeHtml\|formatTime" src/web/static/js/aria-common.js src/web/static/js/utils.js
   b. EXPECTED: >= 6 total matches across the two files
4. Test ALL pages load:
   a. Run the full page loop from the Verification section above
   b. Record pass/fail for each of the 15 pages
   c. For any non-200: curl -s http://localhost:5000/<page> | tail -20 to see the error
5. Check for bare console.log:
   a. Run: grep -rn "console\.log\b" src/web/templates/ --include="*.html" | grep -v "ariaLog\|ARIA_DEBUG\|// debug"
   b. EXPECTED: 0 matches
   c. If found: remove or replace with ariaLog() — this is a trivial fix, do it now
6. Check innerHTML XSS safety:
   a. Run: grep -rn 'innerHTML.*\$\{' src/web/templates/ --include="*.html" | grep -v "escapeHtml"
   b. EXPECTED: 0 matches
   c. If found: wrap with escapeHtml() — this is a trivial fix, do it now
7. Run architecture checker:
   a. Run: python3 scripts/check_architecture.py 2>&1
   b. EXPECTED: 0 errors, 0 warnings (was 13 warnings before Sprint 3)
   c. If warnings remain: document which duplicate functions persist and why
8. Check for remaining duplicate functions:
   a. Run: grep -rn "function " src/web/templates/ --include="*.html" | sed 's/.*function \([a-zA-Z_]*\).*/\1/' | sort | uniq -c | sort -rn | awk '$1 > 1 {print $2 " (" $1 " copies)"}'
   b. EXPECTED: no output (all duplicates extracted)
   c. If duplicates remain: list them with file locations — these are follow-up tickets
9. Write verification log:
   a. Create: aria_memories/logs/sprint3_verification_$(date +%Y%m%d_%H%M%S).md
   b. Include: date, pages tested, pages passed, architecture errors, architecture warnings, console.log count, innerHTML issues, duplicate functions remaining
10. Report summary:
    a. Format as a table: Category | Count | Status
    b. Final verdict: SPRINT 3 COMPLETE or SPRINT 3 HAS N REMAINING ISSUES
```
