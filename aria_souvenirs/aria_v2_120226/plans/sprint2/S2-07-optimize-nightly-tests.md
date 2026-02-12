# S2-07: Optimize nightly_tests Cron to Direct Execution
**Epic:** Sprint 2 — Cron & Token Optimization | **Priority:** P2 | **Points:** 2 | **Phase:** 2

## Problem
The `nightly_tests` cron job runs pytest through Aria's LLM context:

```yaml
  - name: nightly_tests
    cron: "0 0 3 * * *"
    text: "Run pytest: exec python3 -m pytest tests/ -q --tb=short. Log results to activity_log via api_client."
    agent: main
```

This means every night, Aria:
1. Reads her full system prompt (~5000 tokens)
2. Reads the cron instruction (~100 tokens)
3. Executes `python3 -m pytest tests/` via tool call
4. Parses the output through the LLM
5. Logs results via another tool call

**The LLM overhead for a simple `pytest` run is ~90% of the token cost.** The actual value is just "run pytest and log results."

## Root Cause
Using an LLM agent to run a shell command is like using a crane to pick up a pencil. Pytest can be run directly via a shell script triggered by cron (system cron, not OpenClaw).

## Fix

**Option A (keep in OpenClaw, optimize text):**
Simplify the cron text to reduce context:
```yaml
  - name: nightly_tests
    cron: "0 0 3 * * *"
    text: "exec python3 -m pytest tests/ -q --tb=short 2>&1 | tail -5. Log summary line to api_client activity_log with action='nightly_tests'."
    agent: main
    session: isolated
    delivery: none  # Changed from announce — don't waste tokens on test result announcement
```

**Option B (move to system cron — more efficient):**
Create `scripts/run_nightly_tests.sh` that runs inside the container:
```bash
#!/bin/bash
RESULT=$(python3 -m pytest tests/ -q --tb=short 2>&1 | tail -3)
curl -s -X POST http://aria-api:8000/activities \
  -H "Content-Type: application/json" \
  -d "{\"action\":\"nightly_tests\",\"details\":{\"result\":\"$RESULT\",\"timestamp\":\"$(date -u +%FT%TZ)\"}}"
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ❌ | Script/cron config only |
| 2 | .env secrets | ❌ | No secrets |
| 3 | models.yaml SSOT | ❌ | No model references |
| 4 | Docker-first | ✅ | Tests run inside container |
| 5 | aria_memories writable | ❌ | Activity logging via API |
| 6 | No soul modification | ❌ | Not touching soul |

## Dependencies
S1-08 must complete first — tests must pass before nightly test automation makes sense.

## Verification
```bash
# 1. Verify cron text is optimized:
grep -A5 "nightly_tests" aria_mind/cron_jobs.yaml
# EXPECTED: simplified text, delivery: none

# 2. If Option B, verify script exists:
ls -la scripts/run_nightly_tests.sh 2>/dev/null
# EXPECTED: script file exists (if Option B chosen)

# 3. Quick test that pytest works:
python3 -m pytest tests/ -q --tb=short 2>&1 | tail -5
# EXPECTED: "N passed" summary
```

## Prompt for Agent
```
Optimize the nightly_tests cron job to reduce token waste.

**Files to read FIRST:**
- aria_mind/cron_jobs.yaml — search for `nightly_tests`, read full entry (text, schedule, delivery, session)
- aria_mind/heartbeat.py (lines 1-50 — understand how cron jobs are dispatched to Aria)
- aria_mind/HEARTBEAT.md — search for `nightly_tests` or `testing` section
- scripts/ — list all files to check if a test runner script already exists
- tests/ — list all files to understand test scope (how many test files, what they cover)

**Constraints:**
- Constraint 4 (Docker-first): tests run inside aria-brain or aria-api container
- S1-08 must be complete first — tests must actually pass before nightly automation matters

**Decision: Option A (simplify cron text) is recommended** — it's lower risk and keeps test execution visible in Aria's activity log. Option B (shell script) is better for CI but loses Aria's self-awareness of test results.

**Steps:**
1. Read current nightly_tests cron entry:
   a. Run: grep -A10 "nightly_tests" aria_mind/cron_jobs.yaml
   b. Note: current text, delivery mode, session type
2. Analyze token waste:
   a. Current flow: Aria receives full system prompt (~5000 tok) + cron text (~100 tok) + tool call overhead (~500 tok) just to run `pytest`
   b. Estimated waste: ~5600 tokens/night for a command that needs ~100 tokens
3. Apply Option A — simplify cron text:
   a. Edit aria_mind/cron_jobs.yaml — replace nightly_tests entry with:
   ```yaml
     - name: nightly_tests
       cron: "0 0 3 * * *"
       text: "exec python3 -m pytest tests/ -q --tb=short 2>&1 | tail -5. Log the summary line to api_client activity_log with action='nightly_tests'."
       agent: main
       session: isolated
       delivery: none
       best_effort_deliver: true
   ```
   b. Key changes: delivery → none (saves announcement tokens), text simplified, best_effort_deliver added
4. Validate YAML:
   a. Run: python3 -c "import yaml; yaml.safe_load(open('aria_mind/cron_jobs.yaml')); print('YAML valid')"
   b. EXPECTED: "YAML valid"
5. (Optional) Create shell script for Option B:
   a. Only if Shiva prefers direct execution over Aria-mediated testing
   b. Create scripts/run_nightly_tests.sh with pytest + curl to log results
   c. Run: chmod +x scripts/run_nightly_tests.sh
6. Verify the optimization:
   a. Run: grep -A8 "nightly_tests" aria_mind/cron_jobs.yaml
   b. EXPECTED: delivery: none, simplified text, session: isolated
   c. Run: python3 -m pytest tests/ -q --tb=short 2>&1 | tail -5
   d. EXPECTED: test summary line (confirms tests actually run)
```
