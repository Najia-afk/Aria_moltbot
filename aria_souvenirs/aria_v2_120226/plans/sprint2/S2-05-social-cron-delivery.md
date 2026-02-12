# S2-05: Fix social_post Cron Delivery & Platform Routing
**Epic:** Sprint 2 — Cron & Token Optimization | **Priority:** P1 | **Points:** 2 | **Phase:** 2

## Problem
The `social_post` cron job instructs Aria to "Save drafts to aria_memories/moltbook/drafts/ instead of auto-posting." This was a safety measure during development, but for production the social posting pipeline should be verified end-to-end:

1. Does the social skill exist and work?
2. Can Aria actually post to platforms (Moltbook)?
3. Is the draft-only mode intentional or a leftover safety measure?

## Root Cause
The cron text explicitly says "Save drafts instead of auto-posting" — this was likely added during initial deployment to prevent spam. Now that the system is stable, we should:
- Verify the social posting pipeline works
- Either enable auto-posting with quality checks, or formalize the draft-review-post workflow

## Fix
**Verification + decision ticket.** Steps:

1. Test the social endpoint: `GET /api/social`
2. Verify Moltbook skill connectivity
3. Check if draft directory has accumulated drafts
4. Make a decision with Shiva: auto-post or keep draft-first workflow
5. Update cron text accordingly

**If auto-posting enabled:**
```yaml
  - name: social_post
    cron: "0 0 18 * * *"
    text: "Delegate to aria-talk: Post a social update to available social platforms. Read HEARTBEAT.md social_post section. Use the social skill to route content to registered platforms. Quality over quantity. Only post if something genuinely valuable to share."
    agent: main
    session: isolated
    delivery: announce
    best_effort_deliver: true
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ✅ | Social skill → api_client → API → DB |
| 2 | .env secrets | ✅ | Moltbook credentials in .env |
| 3 | models.yaml SSOT | ❌ | No model references |
| 4 | Docker-first | ✅ | Skill runs inside container |
| 5 | aria_memories writable | ✅ | Drafts go to aria_memories/moltbook/drafts/ |
| 6 | No soul modification | ❌ | Not touching soul |

## Dependencies
None — standalone.

## Verification
```bash
# 1. Social endpoint works:
curl -s "http://localhost:8000/api/social" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Social posts: {len(d) if isinstance(d,list) else d}')"
# EXPECTED: Social posts: N (list)

# 2. Check for accumulated drafts:
ls -la aria_memories/moltbook/drafts/ 2>/dev/null || echo "No drafts directory"
# EXPECTED: directory listing or "No drafts directory"

# 3. Moltbook skill exists:
ls aria_skills/moltbook/ 2>/dev/null && echo "Moltbook skill exists"
# EXPECTED: Moltbook skill exists

# 4. Social skill exists:
ls aria_skills/social/ 2>/dev/null && echo "Social skill exists"
# EXPECTED: Social skill exists
```

## Prompt for Agent
```
Verify the social posting pipeline end-to-end and recommend auto-post vs draft workflow.

**Files to read FIRST:**
- aria_mind/cron_jobs.yaml — search for `social_post`, read the full cron entry (text, schedule, delivery)
- aria_skills/social/__init__.py (full — understand the skill interface)
- aria_skills/social/ — list all files, read the main execution file
- aria_skills/moltbook/__init__.py (full — understand moltbook skill)
- aria_skills/moltbook/ — list all files
- aria_mind/HEARTBEAT.md — search for `social_post` section, read the instructions Aria follows
- src/api/routers/social.py (full — understand the API endpoint shape)

**Constraints:**
- Constraint 1 (5-layer): social skill → api_client → API → DB
- Constraint 2 (secrets): Moltbook API credentials must be in .env only. Do NOT log or print credentials.

**Steps:**
1. Verify skill existence and structure:
   a. Run: ls -la aria_skills/social/ aria_skills/moltbook/
   b. Read __init__.py of each skill — check `is_available` property logic
   c. EXPECTED: both directories exist with __init__.py
2. Test social API endpoint:
   a. Run: curl -s "http://localhost:8000/api/social" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Type: {type(d).__name__}, Count: {len(d) if isinstance(d,list) else \"obj\"}')" 
   b. EXPECTED: valid JSON response (list or object — note the expected shape)
3. Check the draft pipeline:
   a. Run: ls -la aria_memories/moltbook/drafts/ 2>/dev/null | head -10
   b. Run: find aria_memories/moltbook/ -name "*.md" -mtime -7 | wc -l
   c. EXPECTED: shows accumulated drafts (if any from recent days)
4. Trace the full delivery path:
   a. Read the cron text — does it say "Save drafts" or "Post to platforms"?
   b. Check if social skill has a `post()` or `publish()` method vs only `draft()`
   c. Check if HEARTBEAT.md social_post section says draft-only or auto-post
   d. Document: is draft-only intentional safety measure or leftover?
5. Test social skill availability inside container:
   a. Run: docker exec aria-brain python3 -c "from aria_skills.social import SocialSkill; s=SocialSkill(); print(f'available: {s.is_available}')" 2>&1 || echo "Import failed"
   b. EXPECTED: available: True/False (document which and why)
6. Write recommendation:
   a. If skill works end-to-end → recommend enabling auto-post with the updated cron text from the Fix section
   b. If skill is broken → document what's broken, recommend keeping draft-only until fixed
   c. If platform credentials missing → note which .env vars are needed

**Verification after decision:**
Run: grep -A8 "social_post" aria_mind/cron_jobs.yaml
EXPECTED: delivery field matches the chosen strategy ("announce" for auto-post, "none" for draft-only)
```
