# S5-07: Skill Observability Dashboard
**Epic:** E15 — Quality | **Priority:** P1 | **Points:** 3 | **Phase:** 4

## Problem
Grafana + Prometheus exist but don't track Aria-specific metrics:
- Skill invocation counts and latencies
- Error rates per skill
- Model usage and cost per skill
- Tool call success rates

## Root Cause
No metrics collection at the skill layer. Skills execute but don't report performance data.

## Fix

### Step 1: Add skill_invocations table
**File: `src/api/db/models.py`**
```python
class SkillInvocation(Base):
    __tablename__ = "skill_invocations"
    id: Mapped[Any] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    skill_name: Mapped[str] = mapped_column(String(100), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer)
    success: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    error_type: Mapped[str | None] = mapped_column(String(100))
    tokens_used: Mapped[int | None] = mapped_column(Integer)
    model_used: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    
    __table_args__ = (
        Index("idx_invocation_skill", "skill_name"),
        Index("idx_invocation_created", "created_at"),
        Index("idx_invocation_success", "success"),
    )
```

### Step 2: Add API endpoints
```python
@router.get("/skills/stats")
async def skill_stats(hours: int = 24, db: ...):
    """Skill performance stats for the last N hours."""
    # Group by skill: count, avg_duration, error_rate, total_tokens

@router.get("/skills/stats/{skill_name}")
async def skill_detail_stats(skill_name: str, hours: int = 24, db: ...):
    """Detailed stats for one skill."""
```

### Step 3: Add web dashboard
**File: `src/web/templates/skill_stats.html`** (NEW)
- Bar chart: invocations per skill (last 24h)
- Line chart: latency over time
- Pie chart: error rate by skill
- Table: top errors with resolution links (from lessons_learned)

### Step 4: Instrument BaseSkill
Add timing decorator to BaseSkill.execute():
```python
async def execute(self, tool_name, params):
    start = time.monotonic()
    try:
        result = await self._execute(tool_name, params)
        duration = int((time.monotonic() - start) * 1000)
        await self.api_client.record_invocation(self.name, tool_name, duration, True)
        return result
    except Exception as e:
        duration = int((time.monotonic() - start) * 1000)
        await self.api_client.record_invocation(self.name, tool_name, duration, False, type(e).__name__)
        raise
```

## Constraints
Same 6 constraints.

## Dependencies
- S5-02 (lessons_learned — link errors to resolutions)

## Verification
```bash
# Stats endpoint:
curl -s http://localhost:8000/api/skills/stats?hours=24
# Dashboard:
curl -s -o /dev/null -w '%{http_code}' http://localhost:5000/skill-stats
```

## Prompt for Agent
```
Build skill observability dashboard.
FILES: src/api/db/models.py, src/api/routers/skills.py (NEW), src/web/templates/skill_stats.html (NEW), aria_skills/base.py
STEPS: 1. SkillInvocation model 2. Stats endpoints 3. Dashboard with charts 4. Instrument BaseSkill
```
