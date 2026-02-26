"""
Improvement Proposals endpoints — self-improvement PR loop (S5-06).

Safety rules:
- Low risk (cron, params): Can auto-implement after 24h if no rejection
- Medium risk (new skills, API changes): Requires explicit approval
- High risk (architecture, security): Requires approval + review by Claude/human
- Proposals CANNOT modify soul/ directory
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import ImprovementProposal
from deps import get_db
from pagination import paginate_query, build_paginated_response
from schemas.requests import CreateProposal, ReviewProposal

router = APIRouter(tags=["Proposals"])
logger = logging.getLogger("aria.api.proposals")

# Paths that proposals cannot touch
_FORBIDDEN_PATHS = ["soul/", "aria_mind/soul/", "aria_mind/SOUL.md", "aria_mind/SOUL_EVIL.md"]


@router.post("/proposals")
async def create_proposal(body: CreateProposal, db: AsyncSession = Depends(get_db)):
    """Aria proposes an improvement."""
    file_path = body.file_path or ""
    if any(fp in (file_path or "") for fp in _FORBIDDEN_PATHS):
        raise HTTPException(status_code=403, detail="Proposals cannot modify soul/ directory")

    proposal = ImprovementProposal(
        title=body.title,
        description=body.description,
        category=body.category,
        risk_level=body.risk_level,
        file_path=file_path,
        current_code=body.current_code,
        proposed_code=body.proposed_code,
        rationale=body.rationale or "",
    )
    db.add(proposal)
    await db.commit()
    await db.refresh(proposal)
    return {"created": True, "id": str(proposal.id)}


@router.get("/proposals")
async def list_proposals(
    status: str = None,
    page: int = 1,
    per_page: int = 25,
    db: AsyncSession = Depends(get_db),
):
    """List proposals with optional status filter."""
    base = select(ImprovementProposal).order_by(ImprovementProposal.created_at.desc())
    if status:
        base = base.where(ImprovementProposal.status == status)

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0
    stmt, _ = paginate_query(base, page, per_page)
    result = await db.execute(stmt)
    items = [p.to_dict() for p in result.scalars().all()]
    return build_paginated_response(items, total, page, per_page)


@router.get("/proposals/{proposal_id}")
async def get_proposal(proposal_id: str, db: AsyncSession = Depends(get_db)):
    """Get a single proposal by ID."""
    result = await db.execute(
        select(ImprovementProposal).where(ImprovementProposal.id == proposal_id)
    )
    proposal = result.scalar_one_or_none()
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return proposal.to_dict()


@router.patch("/proposals/{proposal_id}")
async def review_proposal(
    proposal_id: str,
    body: ReviewProposal,
    db: AsyncSession = Depends(get_db),
):
    """Approve or reject a proposal."""
    new_status = body.status
    if new_status not in ("approved", "rejected", "implemented"):
        raise HTTPException(status_code=400, detail="status must be 'approved', 'rejected', or 'implemented'")

    result = await db.execute(
        select(ImprovementProposal).where(ImprovementProposal.id == proposal_id)
    )
    proposal = result.scalar_one_or_none()
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")

    proposal.status = new_status
    proposal.reviewed_by = body.reviewed_by
    proposal.reviewed_at = func.now()
    await db.commit()
    return {"updated": True, "id": str(proposal.id), "status": new_status}


@router.delete("/proposals/{proposal_id}")
async def delete_proposal(proposal_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ImprovementProposal).where(ImprovementProposal.id == proposal_id)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Proposal not found")
    await db.delete(row)
    await db.commit()
    return {"deleted": True, "id": proposal_id}
