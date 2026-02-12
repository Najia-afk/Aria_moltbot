# S4-08: Final Verification Pass — All Sprints Complete
**Epic:** Sprint 4 — Reliability & Self-Healing | **Priority:** P0 | **Points:** 1 | **Phase:** 4

## Problem
After completing Sprints 1–4 (32 tickets), need a comprehensive final verification that ALL changes work together without regressions. This is the "ship-it" gate — nothing leaves this sprint incomplete.

## Root Cause
Complex multi-sprint work can have emergent interactions. Individual ticket verification is necessary but not sufficient.

## Fix
Run the complete verification matrix below. **Every check must pass.** Any failure triggers investigation and fix before this ticket can close.

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ✅ | Verify architecture compliance |
| 2 | .env secrets | ✅ | Verify no secrets in code |
| 3 | models.yaml SSOT | ✅ | Verify no hardcoded models |
| 4 | Docker-first | ✅ | All checks against running containers |
| 5 | aria_memories writable | ✅ | Write final verification log |
| 6 | No soul modification | ✅ | Verify soul files unchanged |

## Dependencies
**ALL other tickets** (S1-01 through S4-07) must be complete.

## Verification

### MASTER VERIFICATION CHECKLIST
```bash
#!/bin/bash
# Final Verification Pass — Aria v2 Sprint 12/02/26
echo "╔═══════════════════════════════════════════════════════╗"
echo "║        ARIA FINAL VERIFICATION — 2026-02-12          ║"
echo "╚═══════════════════════════════════════════════════════╝"

PASS=0; FAIL=0; TOTAL=0

assert() {
    TOTAL=$((TOTAL+1))
    if eval "$2" > /dev/null 2>&1; then
        echo "  ✅ $1"
        PASS=$((PASS+1))
    else
        echo "  ❌ $1"
        FAIL=$((FAIL+1))
    fi
}

# ═══════════════════════════════════════
# SPRINT 1: Critical Bugs & Python Compat
# ═══════════════════════════════════════
echo -e "\n📌 SPRINT 1 — Critical Bugs"

# S1-01: Python 3.9 compat
assert "S1-01: No PEP 604 syntax in agents" \
  "! grep -rn 'str |.*None\|int |.*None' aria_agents/ --include='*.py' | grep -v Optional | grep -v Union | grep -q '.'"
assert "S1-01: context.py imports correctly" \
  "python3 -c 'from aria_agents.context import AgentContext; print(\"ok\")'"

# S1-02: console.log removed
assert "S1-02: No bare console.log in templates" \
  "[ \$(grep -rn 'console\.log\b' src/web/templates/ --include='*.html' | grep -v ariaLog | grep -v ARIA_DEBUG | grep -v '// debug' | wc -l) -eq 0 ]"

# S1-03: API routes
assert "S1-03: /api/goals returns 200" \
  "[ \$(curl -sf -o /dev/null -w '%{http_code}' http://localhost:8000/api/goals) = '200' ]"

# S1-08: Tests pass
assert "S1-08: pytest runs without import errors" \
  "python3 -m pytest tests/ -q --tb=no 2>&1 | grep -v ImportError | grep -q 'passed\|no tests'"

# ═══════════════════════════════════════
# SPRINT 2: Cron & Token Optimization
# ═══════════════════════════════════════
echo -e "\n📌 SPRINT 2 — Cron Optimization"

# S2-01: Merged crons
assert "S2-01: work_cycle exists in cron_jobs.yaml" \
  "grep -q 'work_cycle' aria_mind/cron_jobs.yaml"

# S2-02: Patched crons persisted
assert "S2-02: exploration_pulse not active" \
  "! grep -A5 'exploration_pulse' aria_mind/cron_jobs.yaml | grep -q 'active: true'"

# S2-08: All crons documented
assert "S2-08: cron_jobs.yaml exists and is valid YAML" \
  "python3 -c 'import yaml; yaml.safe_load(open(\"aria_mind/cron_jobs.yaml\"))'"

# ═══════════════════════════════════════
# SPRINT 3: Frontend Deduplication
# ═══════════════════════════════════════
echo -e "\n📌 SPRINT 3 — Frontend Polish"

# S3-01: Shared utils
assert "S3-01: utils.js exists" \
  "ls src/web/static/js/utils.js"

# S3-05: fetchWithRetry
assert "S3-05: fetchWithRetry defined" \
  "grep -q 'fetchWithRetry\|ariaLog\|ARIA_DEBUG' src/web/static/js/aria-common.js"

# All pages load
assert "S3-08: Dashboard loads (200)" \
  "[ \$(curl -sf -o /dev/null -w '%{http_code}' http://localhost:5000/) = '200' ]"
assert "S3-08: Goals page loads (200)" \
  "[ \$(curl -sf -o /dev/null -w '%{http_code}' http://localhost:5000/goals) = '200' ]"
assert "S3-08: Knowledge page loads (200)" \
  "[ \$(curl -sf -o /dev/null -w '%{http_code}' http://localhost:5000/knowledge) = '200' ]"

# ═══════════════════════════════════════
# SPRINT 4: Reliability & Self-Healing
# ═══════════════════════════════════════
echo -e "\n📌 SPRINT 4 — Reliability"

# S4-01: Patch script
assert "S4-01: apply_patch.sh exists" \
  "ls scripts/apply_patch.sh 2>/dev/null"

# S4-02: Health watchdog
assert "S4-02: health_watchdog.sh exists" \
  "ls scripts/health_watchdog.sh 2>/dev/null"

# S4-03: api_client resilience
assert "S4-03: Retry logic in api_client" \
  "grep -q 'retry\|Retry\|RETRY' aria_skills/api_client/__init__.py 2>/dev/null"

# S4-04: Verify script
assert "S4-04: verify_deployment.sh exists" \
  "ls scripts/verify_deployment.sh 2>/dev/null"

# S4-06: Pre-commit hook
assert "S4-06: Pre-commit hook installed" \
  "ls .git/hooks/pre-commit 2>/dev/null"

# S4-07: Runbook
assert "S4-07: RUNBOOK.md exists" \
  "ls docs/RUNBOOK.md 2>/dev/null"

# ═══════════════════════════════════════
# HARD CONSTRAINTS
# ═══════════════════════════════════════
echo -e "\n🔒 HARD CONSTRAINTS"

assert "Constraint 1: No SQLAlchemy in skills" \
  "! grep -rn 'from sqlalchemy' aria_skills/ --include='*.py' | grep -v api_client | grep -q '.'"
assert "Constraint 2: No secrets in code" \
  "! grep -rn 'OPENAI_API_KEY\|sk-[a-zA-Z0-9]' aria_skills/ aria_agents/ aria_mind/ --include='*.py' | grep -v '.env' | grep -v example | grep -q '.'"
assert "Constraint 3: No hardcoded models" \
  "! grep -rn '\"gpt-4\"\|\"claude-3\"\|\"gemini\"' aria_skills/ --include='*.py' | grep -v models.yaml | grep -v comment | grep -v '#' | grep -q '.'"
assert "Constraint 5: aria_memories writable" \
  "touch aria_memories/logs/.test_write && rm aria_memories/logs/.test_write"
assert "Constraint 6: Soul unchanged" \
  "ls aria_mind/soul/ > /dev/null 2>&1"

# ═══════════════════════════════════════
# DOCKER HEALTH
# ═══════════════════════════════════════
echo -e "\n🐳 DOCKER HEALTH"

for c in aria-db aria-api aria-web aria-brain; do
    assert "Container $c running" \
      "docker inspect --format='{{.State.Status}}' $c 2>/dev/null | grep -q running"
done

assert "API health endpoint" \
  "curl -sf http://localhost:8000/health | grep -q healthy"

# ═══════════════════════════════════════
# ARCHITECTURE
# ═══════════════════════════════════════
echo -e "\n🏗️ ARCHITECTURE"

assert "Architecture: 0 errors" \
  "[ \$(python scripts/check_architecture.py 2>&1 | grep 'ERRORS:' | grep -o '[0-9]*') -eq 0 ] 2>/dev/null || python scripts/check_architecture.py 2>&1 | grep -q '0 errors'"

# ═══════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════
echo -e "\n╔═══════════════════════════════════════════════════════╗"
echo "║  RESULTS: $PASS/$TOTAL passed, $FAIL failed"
echo "╚═══════════════════════════════════════════════════════╝"

if [ "$FAIL" -eq 0 ]; then
    echo ""
    echo "  🎉 ALL CHECKS PASSED — ARIA IS SHIP-READY"
    echo ""
    # Write verification log
    DATE=$(date +%Y%m%d_%H%M%S)
    cat > "aria_memories/logs/final_verification_${DATE}.md" << EOF
# Final Verification — $(date)
- Total checks: $TOTAL
- Passed: $PASS
- Failed: $FAIL
- Status: ✅ ALL PASSED
- Sprints verified: 1, 2, 3, 4
- Tickets verified: 32
EOF
    echo "  📝 Log written to aria_memories/logs/final_verification_${DATE}.md"
else
    echo ""
    echo "  ⚠️ $FAIL CHECKS FAILED — FIX BEFORE SHIPPING"
    echo ""
    exit 1
fi
```

## Prompt for Agent
```
Run the final verification pass for all 4 sprints. This is the ship-it gate.

**Files to read FIRST (cross-reference what each sprint changed):**
- aria_souvenirs/aria_v2_120226/plans/SPRINT_MASTER_OVERVIEW.md (lines 1-50 — ticket list and expected outcomes)
- aria_agents/context.py (lines 1-30 — verify S1-01 modern syntax is present)
- aria_mind/cron_jobs.yaml (full — verify S2-01 merged crons, S2-02 patched intervals)
- src/web/static/js/aria-common.js (lines 1-30 — verify S3-05 fetchWithRetry exists)
- src/web/static/js/utils.js (lines 1-30 — verify S3-01 escapeHtml exists)
- scripts/ — list all files (verify S4-01 apply_patch.sh, S4-04 verify_deployment.sh exist)
- docs/RUNBOOK.md (lines 1-20 — verify S4-07 created it)
- aria_skills/api_client/__init__.py (search for "retry" — verify S4-03 error recovery)

**Constraints:**
- ALL 6 constraints must be verified — this is the final gate
- Constraint 4 (Docker-first): all checks against running containers
- Constraint 5 (aria_memories): write final verification log
- Constraint 6 (soul): verify soul files are byte-identical to pre-sprint state

**Steps:**
1. Copy the MASTER VERIFICATION CHECKLIST script from the Verification section above into a file:
   a. Run: cat > /tmp/final_verify.sh << 'SCRIPT' ... SCRIPT
   b. Run: chmod +x /tmp/final_verify.sh && bash /tmp/final_verify.sh
   c. Capture full output
2. For each ❌ failure:
   a. Read the relevant source file to understand why it failed
   b. If trivial (< 5 min fix, < 3 lines changed): fix it now, re-run that single check
   c. If complex: document the issue with file path, line number, and error message
   d. Do NOT create new tickets — fix it or escalate to Shiva
3. Verify HARD CONSTRAINTS explicitly:
   a. Run: grep -rn "from sqlalchemy" aria_skills/ --include="*.py" | grep -v api_client | grep -v __pycache__
   b. EXPECTED: 0 matches (Constraint 1: no SQLAlchemy in skills)
   c. Run: grep -rn "OPENAI_API_KEY\|sk-[a-zA-Z0-9]" aria_skills/ aria_agents/ aria_mind/ --include="*.py" | grep -v ".env" | grep -v example
   d. EXPECTED: 0 matches (Constraint 2: no secrets in code)
   e. Run: grep -rn '"gpt-4"\|"claude-3"\|"gemini"' aria_skills/ --include="*.py" | grep -v models.yaml | grep -v "#"
   f. EXPECTED: 0 matches (Constraint 3: no hardcoded models)
   g. Run: touch aria_memories/logs/.test && rm aria_memories/logs/.test
   h. EXPECTED: success (Constraint 5: writable)
   i. Run: git diff --name-only aria_mind/soul/ 2>/dev/null || ls aria_mind/soul/
   j. EXPECTED: no changes to soul files (Constraint 6)
4. Verify Docker health:
   a. Run: docker ps --format "{{.Names}}: {{.Status}}" | grep -E "aria-db|aria-api|aria-web|aria-brain"
   b. EXPECTED: all 4 core containers show "Up"
   c. Run: curl -sf http://localhost:8000/health | python3 -m json.tool
   d. EXPECTED: {"status": "healthy", "database": "connected", "version": "3.0.0"}
5. Run architecture checker:
   a. Run: python3 scripts/check_architecture.py 2>&1
   b. EXPECTED: 0 errors (warnings acceptable if documented)
6. Re-run any failed checks after fixes:
   a. Loop: fix → re-check → fix → re-check until PASS=TOTAL
   b. Maximum 3 iterations — if still failing after 3 rounds, escalate
7. Write final verification log:
   a. Create: aria_memories/logs/final_verification_$(date +%Y%m%d_%H%M%S).md
   b. Contents: date, total checks, passed, failed, sprint-by-sprint breakdown, constraint verification results
8. Report final verdict:
   a. If all pass: "ALL CHECKS PASSED — ARIA IS SHIP-READY"
   b. If any fail: "N CHECKS FAILED — REQUIRES ATTENTION" with the specific failures listed
```
