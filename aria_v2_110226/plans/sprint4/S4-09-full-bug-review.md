# S4-09: Production Bug Review — Full Codebase Scan
**Epic:** E10 — Code Quality | **Priority:** P1 | **Points:** 5 | **Phase:** 3

## Problem
Since Aria is running in production, a comprehensive bug review is needed covering:
1. Race conditions (beyond the upsert_memory fix in S2-05)
2. Missing error handling (500s that should be 400s)
3. Missing input validation (SQL injection via ILIKE, path traversal)
4. Memory leaks (unclosed httpx clients, DB sessions)
5. Concurrency issues (shared mutable state in singletons)
6. Missing CORS/CSP headers
7. Rate limiting gaps (GET requests not limited)

## Root Cause
No production security/reliability audit has been done on the v2 codebase.

## Fix

### Systematic review areas:

1. **All routers** — Check every endpoint for:
   - Input validation (is request.json() checked for required fields?)
   - Error handling (what if DB is down?)
   - Response consistency (some return dicts, some return lists)

2. **Middleware** — Check:
   - Rate limiting coverage (S2 found GET is not rate limited)
   - Security headers (Content-Security-Policy, X-Frame-Options)
   - Error responses (don't leak stack traces)

3. **Database sessions** — Check:
   - Are all sessions properly closed?
   - Are transactions committed/rolled back?
   - N+1 query patterns?

4. **API client singleton** — Check:
   - What happens if the API client is used after close()?
   - Thread safety of the global _client?
   - Timeout handling

5. **Frontend** — Check:
   - XSS in all templates (beyond S2-02)
   - CSRF tokens (none exist currently)
   - Clickjacking protection

Document all findings in this ticket and create follow-up tickets for each issue.

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ✅ | Review compliance |
| 2 | .env | ✅ | Check for leaks |
| 3 | models.yaml | ✅ | Check hardcoded |
| 4 | Docker-first | ✅ | Test locally |
| 5 | aria_memories | ❌ | Read-only review |
| 6 | No soul mod | ❌ | No soul files |

## Dependencies
None — can run any time.

## Verification
```bash
# 1. Run architecture checker:
python scripts/check_architecture.py
# EXPECTED: 0 issues

# 2. Check for common vulnerabilities:
grep -rn 'eval(\|exec(\|__import__' src/ aria_skills/ --include='*.py'
# EXPECTED: 0 results

# 3. Check for missing error handling:
grep -rn 'await request.json()' src/api/routers/ | grep -v 'try'
# EXPECTED: identify unprotected .json() calls

# 4. Document findings in this ticket's "Findings" section
```

## Prompt for Agent
```
Perform a comprehensive production bug review of the Aria codebase.

FILES TO READ: ALL files in src/api/, src/web/, aria_skills/
Focus on: race conditions, error handling, input validation, security, memory leaks

STEPS:
1. Read every router file and check input validation
2. Read middleware for security gaps
3. Check DB session management
4. Review frontend templates for XSS
5. Document ALL findings with file:line references
6. Create follow-up ticket list

CONSTRAINTS: Read-only review. Document findings. Don't modify code.
```
