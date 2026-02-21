# S3-01: Add Sprint Fields to Goal Model
**Epic:** E5 — Sprint Board | **Priority:** P0 | **Points:** 3 | **Phase:** 2

## Problem
The Goal model lacks fields needed for sprint board functionality:
- No `sprint` field to group goals by sprint
- No `board_column` field for explicit Kanban position
- No `position` field for ordering within a column (drag-and-drop)
- No `assigned_to` field for agent assignment
- No `category`/`tags` field for filtering
- Status values don't map cleanly to Kanban columns

## Root Cause
Goal model was designed for simple tracking, not sprint management.

## Fix

### File: `src/api/db/models.py`
Add fields to the Goal class:

BEFORE (Goal class ~L87-99):
```python
class Goal(Base):
    __tablename__ = "goals"
    id: Mapped[Any] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    goal_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), server_default=text("'pending'"))
    priority: Mapped[int] = mapped_column(Integer, server_default=text("2"))
    progress: Mapped[float] = mapped_column(Numeric(5, 2), server_default=text("0"))
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```
AFTER:
```python
class Goal(Base):
    __tablename__ = "goals"
    id: Mapped[Any] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    goal_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), server_default=text("'pending'"))
    priority: Mapped[int] = mapped_column(Integer, server_default=text("2"))
    progress: Mapped[float] = mapped_column(Numeric(5, 2), server_default=text("0"))
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Sprint Board fields (S3-01)
    sprint: Mapped[str | None] = mapped_column(String(100), server_default=text("'backlog'"))
    board_column: Mapped[str | None] = mapped_column(String(50), server_default=text("'backlog'"))
    position: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    assigned_to: Mapped[str | None] = mapped_column(String(100))
    tags: Mapped[dict | None] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"), onupdate=text("NOW()"))
```

Add indexes:
```python
    __table_args__ = (
        Index("idx_goals_status", "status"),
        Index("idx_goals_priority", "priority"),
        Index("idx_goals_created", "created_at"),
        Index("idx_goals_status_priority_created", "status", "priority", "created_at"),
        Index("idx_goals_sprint", "sprint"),
        Index("idx_goals_board_column", "board_column"),
        Index("idx_goals_sprint_column_position", "sprint", "board_column", "position"),
    )
```

### Alembic migration
```bash
cd src/api && alembic revision --autogenerate -m "add_goal_sprint_board_fields"
alembic upgrade head
```

### Update Goal.to_dict()
Ensure `to_dict()` includes the new fields: sprint, board_column, position, assigned_to, tags, updated_at.

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | DB layer change (correct) |
| 2 | .env for secrets (zero in code) | ❌ | No secrets |
| 3 | models.yaml single source of truth | ❌ | No model name refs |
| 4 | Docker-first testing | ✅ | Run migration in Docker |
| 5 | aria_memories only writable path | ❌ | DB schema change |
| 6 | No soul modification | ❌ | No soul files |

## Dependencies
- Sprint 2 should complete first (pagination on goals endpoint).

## Verification
```bash
# 1. Verify new fields in model:
grep -E 'sprint|board_column|position|assigned_to|tags|updated_at' src/api/db/models.py | head -10
# EXPECTED: 6+ lines with new fields

# 2. Run migration:
cd src/api && alembic upgrade head

# 3. Verify columns in DB:
docker compose exec aria-db psql -U aria -d aria_brain -c "\d goals" | grep -E 'sprint|board_column|position|assigned_to|tags|updated_at'
# EXPECTED: All 6 columns visible

# 4. Test API still works:
curl -s http://localhost:8000/api/goals?limit=1 | python3 -c "
import sys,json; d=json.load(sys.stdin)
items = d.get('items', d) if isinstance(d, dict) else d
if items: print(f'Has sprint field: {\"sprint\" in items[0]}')
"
# EXPECTED: Has sprint field: True
```

## Prompt for Agent
```
You are adding sprint board fields to the Aria Goal database model.

FILES TO READ FIRST:
- src/api/db/models.py (Goal class, ~line 87-99, and existing indexes)
- src/api/alembic/ (migration setup)

STEPS:
1. Read the Goal class in models.py
2. Add 6 new fields: sprint, board_column, position, assigned_to, tags, updated_at
3. Add 3 new indexes for sprint queries
4. Update to_dict() to include new fields
5. Create alembic migration
6. Run verification commands

CONSTRAINTS: DB layer only. Use nullable fields with defaults for backward compatibility.
IMPORTANT: New fields MUST have server_default or be nullable to avoid breaking existing data.
```
