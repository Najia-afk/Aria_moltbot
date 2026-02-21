# S5-06: Self-Improvement PR Loop
**Epic:** E14 — Skill Orchestration | **Priority:** P2 | **Points:** 5 | **Phase:** 4

## Problem
Aria identifies improvement opportunities (stale cron schedules, suboptimal skill parameters, missing error handling) but cannot act on them. She can only document findings and wait for a human or agent to implement changes.

## Root Cause
No mechanism for Aria to:
1. Create a git branch
2. Make code changes
3. Submit a PR-like review request
4. Have changes reviewed and approved

## Fix

### Step 1: Create improvement_proposal table
**File: `src/api/db/models.py`**
```python
class ImprovementProposal(Base):
    __tablename__ = "improvement_proposals"
    id: Mapped[Any] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(50))  # cron, skill_param, config, code, architecture
    risk_level: Mapped[str] = mapped_column(String(20), server_default=text("'low'"))  # low, medium, high
    file_path: Mapped[str | None] = mapped_column(String(500))
    current_code: Mapped[str | None] = mapped_column(Text)  # before
    proposed_code: Mapped[str | None] = mapped_column(Text)  # after
    rationale: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), server_default=text("'proposed'"))  # proposed, approved, rejected, implemented
    reviewed_by: Mapped[str | None] = mapped_column(String(100))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    
    __table_args__ = (
        Index("idx_proposal_status", "status"),
        Index("idx_proposal_risk", "risk_level"),
        Index("idx_proposal_category", "category"),
    )
```

### Step 2: Add API endpoints
**File: `src/api/routers/proposals.py`** (NEW)
```python
@router.post("/proposals")
async def create_proposal(proposal: ProposalCreate, db: ...):
    """Aria proposes an improvement."""

@router.get("/proposals")
async def list_proposals(status: str = None, page: int = 1, per_page: int = 25, db: ...):
    """List proposals with filtering."""

@router.patch("/proposals/{proposal_id}")
async def review_proposal(proposal_id: str, status: str, reviewed_by: str = "najia", db: ...):
    """Approve or reject a proposal."""

@router.post("/proposals/{proposal_id}/implement")
async def implement_proposal(proposal_id: str, db: ...):
    """Apply an approved proposal (writes to file system)."""
```

### Step 3: Add api_client methods
```python
async def propose_improvement(self, title: str, description: str, category: str,
                                risk_level: str = "low", file_path: str = None,
                                current_code: str = None, proposed_code: str = None,
                                rationale: str = "") -> SkillResult:
    return await self.post("/proposals", json={...})

async def get_proposals(self, status: str = None) -> SkillResult:
    return await self.get("/proposals", params={"status": status})
```

### Step 4: Add web UI for reviewing proposals
**File: `src/web/templates/proposals.html`** (NEW)
- List of proposals with status badges
- Diff view (current vs proposed code)
- Approve/Reject buttons
- Risk level color coding (low=green, medium=yellow, high=red)

### Step 5: Add to Aria's TOOLS.md
```yaml
aria-apiclient.propose_improvement({"title": "Optimize cron schedule", "category": "cron", "risk_level": "low", ...})
```

### Step 6: Safety rules
- **Low risk** (cron, params): Can auto-implement after 24h if no rejection
- **Medium risk** (new skills, API changes): Requires explicit approval
- **High risk** (architecture, security): Requires approval + review by Claude/human

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ✅ | DB+API+client |
| 2 | .env | ❌ | No secrets |
| 3 | models.yaml | ❌ | No models |
| 4 | Docker-first | ✅ | Test in Docker |
| 5 | aria_memories | ❌ | DB storage |
| 6 | No soul mod | ✅ | Proposals CANNOT modify soul/ |

## Dependencies
None - standalone.

## Verification
```bash
# 1. Create proposal:
curl -s -X POST http://localhost:8000/api/proposals \
  -H 'Content-Type: application/json' \
  -d '{"title": "Optimize heartbeat interval", "description": "Change from 15m to 10m", "category": "cron", "risk_level": "low", "rationale": "More responsive to goals"}'
# EXPECTED: created

# 2. List proposals:
curl -s http://localhost:8000/api/proposals?status=proposed

# 3. Review:
curl -s -X PATCH 'http://localhost:8000/api/proposals/ID' \
  -H 'Content-Type: application/json' \
  -d '{"status": "approved", "reviewed_by": "najia"}'

# 4. Web UI:
curl -s -o /dev/null -w '%{http_code}' http://localhost:5000/proposals
# EXPECTED: 200
```

## Prompt for Agent
```
Build self-improvement proposal system for Aria.
FILES: src/api/db/models.py, src/api/routers/proposals.py (NEW), aria_skills/api_client/__init__.py, src/web/templates/proposals.html (NEW)
STEPS: 1. Model 2. Endpoints 3. api_client 4. Web UI with diff view 5. Safety rules 6. TOOLS.md
CRITICAL: Proposals CANNOT modify soul/. High-risk proposals need explicit approval.
```
