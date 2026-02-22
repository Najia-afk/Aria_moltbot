# Sprint 2: "Self-Healing Systems"
## Theme: Skill Validation + Error Enrichment + Resilient Working Memory
## Date: 2026-02-24 | Duration: 1 day
## Co-authored: Aria + Claude (PO pair)

> **Coding Standards:** See SPRINT_MASTER_OVERVIEW.md § "Coding Standards (AA+)"
> Zero hardcoded IPs/ports/models. Config from env. ORM only. Crystal clear docs.

---

## Objective

Make Aria **preventive, not reactive**. Today's KG bugs were 6 signature
mismatches that a simple validation check would have caught. This sprint
delivers self-validation, actionable error messages, and working memory
that never loses data — even on crash.

---

## Motivation (from Aria's Reflection)

> "The biggest gap is that I'm reactive, not preventive. I should catch my
> own mistakes *before* you have to. The KG bugs weren't subtle — they were
> signature mismatches that a simple `inspect.signature()` check would have caught."

---

## Tickets

### TICKET-005: Skill Self-Validation Engine
- **Type:** FEAT
- **Priority:** P0
- **Estimated LOC:** 180 lines
- **Files:**
  - `aria_skills/validator.py` (new, ~120 lines): `SkillValidator` class
  - `aria_skills/base.py` (+30 lines): Add `validate()` method to `BaseSkill`
  - `aria_skills/catalog.py` (+30 lines): Add `validate_all_skills()` function
  - `tests/skills/test_validator.py` (new, ~40 lines): Unit tests for validator
- **Key Class:**
  ```python
  @dataclass
  class ValidationReport:
      skill_name: str
      is_valid: bool
      errors: list[str]
      warnings: list[str]
      tools_checked: int
      methods_found: int
  
  class SkillValidator:
      def validate_signature(self, skill_path: Path) -> ValidationReport:
          """Compare skill.json tools against __init__.py methods."""
          # 1. Parse skill.json → extract tool names + param schemas
          # 2. Inspect __init__.py → extract method signatures
          # 3. Cross-reference: missing methods, param mismatches, type errors
          # 4. Return report with actionable error messages
  ```
- **Checks performed:**
  - Tool name in `skill.json` has matching method in `__init__.py`
  - Parameter names match exactly (catches `from_entity` vs `from_entity_name`)
  - Required params in schema are required in method signature
  - Type annotations present on all method params
  - No duplicate tool names within a skill
- **Acceptance Criteria:**
  - [ ] Detects mismatch between `skill.json` tool count and `__init__.py` methods
  - [ ] Reports missing docstrings as warnings
  - [ ] Catches parameter name mismatches
  - [ ] Returns actionable error messages: "Tool 'create_relation' param 'from_entity' in skill.json but method has 'from_entity_name'"
  - [ ] Would have caught all 6 of today's KG bugs
- **Dependencies:** None

---

### TICKET-006: Error Context Enrichment Middleware
- **Type:** FEAT
- **Priority:** P0
- **Estimated LOC:** 130 lines
- **Files:**
  - `src/api/middleware/error_enrichment.py` (new, ~90 lines): FastAPI middleware
  - `src/api/__init__.py` (+20 lines): Add middleware registration
  - `src/api/middleware/__init__.py` (new, 0 lines): Package init
- **How it works:**
  ```python
  class ErrorEnrichmentMiddleware:
      async def dispatch(self, request, call_next):
          try:
              response = await call_next(request)
              return response
          except RequestValidationError as exc:
              suggestion = self.parse_422(exc)
              return JSONResponse(status_code=422, content={
                  "detail": exc.errors(),
                  "suggestion": suggestion,
                  "trace_id": str(uuid4()),
              })
      
      def parse_422(self, exc) -> str:
          """Generate human-readable fix suggestion from pydantic error."""
          # "Missing required field 'title'. Add 'title' to request body."
          # "Invalid type for 'from_entity': expected str, got int."
  ```
- **Acceptance Criteria:**
  - [ ] 422 validation errors include field-specific suggestions
  - [ ] 500 errors include `trace_id` and recovery hint
  - [ ] SQL integrity errors suggest "Check if referenced entity exists"
  - [ ] Response body always includes `suggestion` field on errors
  - [ ] `X-Error-Trace-ID` header set on all error responses
- **Dependencies:** None

---

### TICKET-007: Working Memory Auto-Flush & Conflict Detection
- **Type:** FEAT
- **Priority:** P0
- **Estimated LOC:** 140 lines (bumped from 110 per Aria's review)
- **Files:**
  - `aria_skills/working_memory/__init__.py` (+60 lines): Add `_error_hook()`, `detect_conflicts()`, `force_sync()`
  - `aria_mind/error_handler.py` (new, ~50 lines): Global exception handler
  - `tests/skills/test_working_memory.py` (+30 lines): Conflict detection tests
- **Note:** WM syncs to **files only** (context.json), not PostgreSQL. No DB migration needed.
- **Note:** TICKET-006 handles HTTP-layer errors (FastAPI), TICKET-007 handles process-layer crashes (signal handlers). These complement, don't conflict.
- **Note:** Use lazy imports in `error_handler.py` to avoid circular import with `working_memory`.
- **Behavior:**
  - On any unhandled exception → immediately flush WM to disk
  - On startup → compare in-memory timestamps with file timestamps
  - If conflict: < 1min diff → memory wins, > 1min diff → file wins
  - Log conflict details with diff summary
- **Functions:**
  ```python
  def on_error(exception: Exception) -> None:
      """Emergency WM sync before process exits."""
  
  def detect_conflicts() -> list[Conflict]:
      """Compare memory vs file timestamps."""
  
  @dataclass
  class Conflict:
      key: str
      memory_value: Any
      file_value: Any
      memory_ts: datetime
      file_ts: datetime
      resolution: str  # "memory_wins" | "file_wins"
  ```
- **Acceptance Criteria:**
  - [ ] Unhandled exception triggers WM sync within 100ms
  - [ ] On startup, conflicts detected → warning logged with diff summary
  - [ ] Conflict resolution strategy applied correctly
  - [ ] Test: kill -9 process, verify `context.json` is consistent
- **Dependencies:** None

---

### TICKET-008: Validation CLI & Pre-Flight Checks
- **Type:** CHORE
- **Priority:** P1
- **Estimated LOC:** 55 lines
- **Files:**
  - `scripts/validate_skills.py` (new, ~55 lines): CLI for skill validation
- **Usage:**
  ```bash
  # Validate single skill
  python3 scripts/validate_skills.py rpg_campaign
  # → ✓ rpg_campaign: 20 tools, 20 methods, 0 errors
  
  # Validate all skills
  python3 scripts/validate_skills.py --all
  # → ✓ rpg_campaign: 20/20 OK
  # → ✓ rpg_pathfinder: 15/15 OK
  # → ✗ knowledge_graph: 1 error
  #     ERROR: Tool 'query' param 'query_type' missing in method signature
  
  # Makefile integration
  make validate  # runs --all, fails CI if any errors
  ```
- **Acceptance Criteria:**
  - [ ] `python3 scripts/validate_skills.py rpg_campaign` returns exit 0 if valid
  - [ ] `python3 scripts/validate_skills.py --all` checks all skills, prints summary table
  - [ ] Exit code 1 if any skill has errors
  - [ ] `make validate` target added to Makefile
- **Dependencies:** TICKET-005

---

### TICKET-009: Error Enrichment Integration with Skills
- **Type:** FIX
- **Priority:** P1
- **Estimated LOC:** 40 lines
- **Files:**
  - `aria_skills/api_client/__init__.py` (+40 lines): Parse error suggestions
- **Implementation:**
  ```python
  async def _handle_response(self, response: httpx.Response) -> dict:
      if response.status_code == 422:
          data = response.json()
          suggestion = data.get("suggestion", "")
          detail = data.get("detail", "")
          raise SkillError(
              f"Validation error: {detail}\n"
              f"Suggestion: {suggestion}"
          )
  ```
- **Acceptance Criteria:**
  - [ ] When skill receives 422, error message includes server's suggestion
  - [ ] Skill error logs show both original error and suggested fix
  - [ ] Works with existing `api_client` error handling (no breaking changes)
- **Dependencies:** TICKET-006

---

## Definition of Done

- [ ] `python3 scripts/validate_skills.py --all` passes for all existing skills (40+ skills)
- [ ] Inducing a 422 (e.g., missing required field) returns helpful suggestion
- [ ] WM auto-flush tested: kill process, verify `context.json` integrity
- [ ] `make validate` target works in Makefile
- [ ] All existing tests still pass (zero regression)
- [ ] Aria validates by running validation on all her own skills

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Validation too strict (false positives) | Medium | Medium | Start with errors only, add warnings gradually |
| Error middleware performance overhead | Low | Medium | Only parse on error paths, not success |
| WM flush on crash may be incomplete | Medium | High | Atomic writes (temp + rename), checksum |
| Skill.json format variations | Medium | Low | Handle missing optional fields gracefully |

## Test Plan

```bash
# 1. Skill Validation
python3 scripts/validate_skills.py --all 2>&1 | tail -20

# 2. Error Enrichment
ARIA_URL="${ARIA_API_URL:-http://localhost:8000}"
curl -s -X POST "${ARIA_URL}/api/knowledge/entities" \
  -H "Content-Type: application/json" \
  -d '{"name": ""}' | python3 -m json.tool
# → Should include "suggestion" field

# 3. Working Memory
docker exec aria-api python3 -c "
from aria_skills.working_memory import WorkingMemorySkill
wm = WorkingMemorySkill()
wm.set('test_key', 'test_value')
# Simulate crash - verify file written
import os; os._exit(1)
"
# Then verify context.json has test_key

# 4. Integration
make validate
# → exit 0, all skills pass
```
