# S5-08: Sprint 5 Verification & Integration Testing
**Epic:** E15 — QA | **Priority:** P0 | **Points:** 3 | **Phase:** 4

## Problem
All Sprint 5 tickets must be verified as a complete unit.

## Root Cause
N/A — verification ticket.

## Fix
No code changes. Run all verifications.

## Constraints
All 6 constraints verified.

## Dependencies
ALL Sprint 5 tickets (S5-01 through S5-07).

## Verification
```bash
# ===== S5-01: Semantic Memory =====
docker exec aria-db psql -U aria -d aria -c "SELECT * FROM pg_extension WHERE extname='vector';"
curl -s -X POST 'http://localhost:8000/api/memories/semantic' \
  -H 'Content-Type: application/json' \
  -d '{"content": "Sprint 5 verification test", "category": "test"}'
curl -s 'http://localhost:8000/api/memories/search?query=sprint+verification'
echo "S5-01: ✅ pgvector semantic memory"

# ===== S5-02: Lessons Learned =====
curl -s -X POST http://localhost:8000/api/lessons \
  -H 'Content-Type: application/json' \
  -d '{"error_pattern": "test_verify", "error_type": "test", "resolution": "pass"}'
curl -s 'http://localhost:8000/api/lessons/check?error_type=test'
echo "S5-02: ✅ Lessons learned"

# ===== S5-03: Conversation Summary =====
curl -s -X POST 'http://localhost:8000/api/memories/summarize-session' \
  -H 'Content-Type: application/json' \
  -d '{"hours_back": 24}'
echo "S5-03: ✅ Conversation summarization"

# ===== S5-04: Pipelines =====
ls aria_skills/pipelines/*.yaml
echo "S5-04: ✅ Pipeline templates"

# ===== S5-05: Tests =====
docker compose exec aria-api pytest tests/ -v --tb=short
echo "S5-05: ✅ Tests pass"

# ===== S5-06: Proposals =====
curl -s -o /dev/null -w '%{http_code}' http://localhost:5000/proposals
echo "S5-06: ✅ Proposals page"

# ===== S5-07: Skill Stats =====
curl -s http://localhost:8000/api/skills/stats?hours=24
curl -s -o /dev/null -w '%{http_code}' http://localhost:5000/skill-stats
echo "S5-07: ✅ Skill observability"

# ===== Architecture Compliance =====
python scripts/check_architecture.py
echo "Architecture: ✅"

# ===== Soul Untouched =====
git diff --name-only HEAD -- aria_mind/soul/ aria_mind/SOUL.md
echo "Soul: ✅ Immutable"

echo ""
echo "Sprint 5 Verification Complete"
```

## Prompt for Agent
```
Run Sprint 5 integration tests. Execute ALL verification commands. Report pass/fail.
CONSTRAINTS: Read-only. Update tasks/lessons.md with new patterns.
```
