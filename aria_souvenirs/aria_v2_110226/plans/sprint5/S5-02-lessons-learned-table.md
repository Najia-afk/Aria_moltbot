# S5-02: Create Lessons Learned Error Recovery System
**Epic:** E13 — Error Recovery | **Priority:** P0 | **Points:** 5 | **Phase:** 4

## Problem
When Aria hits an error (API 429, model timeout, tool failure), she logs it and sometimes retries. But she doesn't learn from it. The same error can happen repeatedly without Aria applying the solution she discovered before.

## Root Cause
No structured storage for error patterns and their resolutions. No pre-call check against known failure patterns.

## Fix

### Step 1: Add lessons_learned table
**File: `src/api/db/models.py`**
```python
class LessonLearned(Base):
    __tablename__ = "lessons_learned"
    id: Mapped[Any] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    error_pattern: Mapped[str] = mapped_column(String(200), nullable=False)  # e.g., "api_429_openrouter"
    error_type: Mapped[str] = mapped_column(String(100), nullable=False)  # timeout, rate_limit, auth, validation, etc.
    skill_name: Mapped[str | None] = mapped_column(String(100))  # which skill triggered it
    context: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))  # what was happening
    resolution: Mapped[str] = mapped_column(Text, nullable=False)  # what fixed it
    resolution_code: Mapped[str | None] = mapped_column(Text)  # code snippet if applicable
    occurrences: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    last_occurred: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    effectiveness: Mapped[float] = mapped_column(Float, server_default=text("1.0"))  # 0-1, how often resolution works
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    
    __table_args__ = (
        Index("idx_lesson_pattern", "error_pattern"),
        Index("idx_lesson_type", "error_type"),
        Index("idx_lesson_skill", "skill_name"),
        UniqueConstraint("error_pattern", name="uq_lesson_pattern"),
    )
```

### Step 2: Add API endpoints
**File: `src/api/routers/lessons.py`** (NEW)
```python
@router.post("/lessons")
async def record_lesson(lesson: LessonCreate, db: AsyncSession = Depends(get_db)):
    """Record a new lesson or increment occurrence of existing one."""
    existing = await db.execute(
        select(LessonLearned).where(LessonLearned.error_pattern == lesson.error_pattern)
    )
    found = existing.scalar_one_or_none()
    if found:
        found.occurrences += 1
        found.last_occurred = func.now()
        if lesson.resolution:
            found.resolution = lesson.resolution
        await db.commit()
        return {"updated": True, "occurrences": found.occurrences}
    
    new_lesson = LessonLearned(**lesson.dict())
    db.add(new_lesson)
    await db.commit()
    return {"created": True, "id": str(new_lesson.id)}


@router.get("/lessons/check")
async def check_known_errors(
    error_type: str = None,
    skill_name: str = None,
    error_message: str = None,
    db: AsyncSession = Depends(get_db),
):
    """Check if there's a known resolution for this error type."""
    stmt = select(LessonLearned)
    if error_type:
        stmt = stmt.where(LessonLearned.error_type == error_type)
    if skill_name:
        stmt = stmt.where(LessonLearned.skill_name == skill_name)
    stmt = stmt.order_by(LessonLearned.effectiveness.desc()).limit(5)
    
    result = await db.execute(stmt)
    lessons = result.scalars().all()
    return {"lessons": [l.to_dict() for l in lessons], "has_resolution": len(lessons) > 0}


@router.get("/lessons")
async def list_lessons(
    page: int = 1, per_page: int = 25,
    db: AsyncSession = Depends(get_db),
):
    """List all lessons learned, most recent first."""
    offset = (page - 1) * per_page
    stmt = select(LessonLearned).order_by(LessonLearned.last_occurred.desc()).offset(offset).limit(per_page)
    total = await db.scalar(select(func.count(LessonLearned.id)))
    result = await db.execute(stmt)
    return {
        "lessons": [l.to_dict() for l in result.scalars().all()],
        "total": total,
        "page": page,
        "per_page": per_page,
    }
```

### Step 3: Add api_client methods
```python
async def record_lesson(self, error_pattern: str, error_type: str,
                         resolution: str, skill_name: str = None) -> SkillResult:
    return await self.post("/lessons", json={
        "error_pattern": error_pattern, "error_type": error_type,
        "resolution": resolution, "skill_name": skill_name,
    })

async def check_known_errors(self, error_type: str = None,
                               skill_name: str = None) -> SkillResult:
    params = {}
    if error_type: params["error_type"] = error_type
    if skill_name: params["skill_name"] = skill_name
    return await self.get("/lessons/check", params=params)
```

### Step 4: Integrate into BaseSkill error handler
**File: `aria_skills/base.py`**
Add to the base error handling:
```python
async def handle_error(self, error: Exception, context: dict):
    """Check lessons_learned before generic retry."""
    error_type = type(error).__name__
    lessons = await self.api_client.check_known_errors(
        error_type=error_type, skill_name=self.name
    )
    if lessons.success and lessons.data.get("has_resolution"):
        resolution = lessons.data["lessons"][0]["resolution"]
        self.logger.info(f"Known error pattern. Resolution: {resolution}")
        # Apply resolution strategy
        return await self.apply_resolution(resolution, context)
    else:
        # Record new error for future learning
        await self.api_client.record_lesson(
            error_pattern=f"{self.name}_{error_type}",
            error_type=error_type,
            resolution="unresolved — needs investigation",
            skill_name=self.name,
        )
        raise error
```

### Step 5: Seed with known patterns
```python
KNOWN_PATTERNS = [
    {"error_pattern": "api_429_rate_limit", "error_type": "rate_limit",
     "resolution": "Wait 60s, retry with different model via model_switcher"},
    {"error_pattern": "litellm_timeout", "error_type": "timeout",
     "resolution": "Downgrade to faster model (qwen3-mlx), reduce max_tokens"},
    {"error_pattern": "tool_hallucinated_function", "error_type": "validation",
     "resolution": "Re-read TOOLS.md, use only documented tool names"},
    {"error_pattern": "db_connection_refused", "error_type": "connection",
     "resolution": "Check aria-db container health, wait 10s and retry"},
    {"error_pattern": "embedding_model_unavailable", "error_type": "model",
     "resolution": "Fallback to keyword search instead of semantic search"},
]
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ✅ | DB + API + api_client + BaseSkill |
| 2 | .env | ❌ | No secrets |
| 3 | models.yaml | ❌ | No model names |
| 4 | Docker-first | ✅ | Migration in Docker |
| 5 | aria_memories | ❌ | DB storage |
| 6 | No soul mod | ❌ | No soul files |

## Dependencies
None — standalone.

## Verification
```bash
# 1. Table exists:
docker exec aria-db psql -U aria -d aria -c "\d lessons_learned"

# 2. Record a lesson:
curl -s -X POST http://localhost:8000/api/lessons \
  -H 'Content-Type: application/json' \
  -d '{"error_pattern": "test_error", "error_type": "test", "resolution": "Do X"}'
# EXPECTED: {"created": true}

# 3. Check known errors:
curl -s 'http://localhost:8000/api/lessons/check?error_type=test'
# EXPECTED: {"lessons": [...], "has_resolution": true}

# 4. BaseSkill uses it:
grep 'check_known_errors\|record_lesson' aria_skills/base.py
# EXPECTED: integration found
```

## Prompt for Agent
```
Create a lessons_learned error recovery system for Aria.

FILES: src/api/db/models.py, src/api/routers/lessons.py (NEW), aria_skills/api_client/__init__.py, aria_skills/base.py
STEPS: 1. Model 2. Endpoints 3. api_client 4. BaseSkill integration 5. Seed known patterns
```
