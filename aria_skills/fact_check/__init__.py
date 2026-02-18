"""Fact-check skill — lightweight claim extraction and verdict scaffolding."""


import re
import uuid
from datetime import datetime, timezone

from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus
from aria_skills.registry import SkillRegistry


@SkillRegistry.register
class FactCheckSkill(BaseSkill):
    def __init__(self, config: SkillConfig):
        super().__init__(config)
        self._claims: dict[str, dict] = {}

    @property
    def name(self) -> str:
        return "fact_check"

    async def initialize(self) -> bool:
        self._status = SkillStatus.AVAILABLE
        return True

    async def health_check(self) -> SkillStatus:
        return self._status

    async def extract_claims(self, text: str) -> SkillResult:
        parts = [p.strip() for p in re.split(r"[\.!?]\s+", text) if p.strip()]
        extracted = []
        for part in parts:
            if any(ch.isdigit() for ch in part) or len(part.split()) > 5:
                claim_id = f"claim-{uuid.uuid4().hex[:8]}"
                claim = {
                    "claim_id": claim_id,
                    "claim_text": part,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "status": "unverified",
                }
                self._claims[claim_id] = claim
                extracted.append(claim)
        return SkillResult.ok({"claims": extracted, "count": len(extracted)})

    async def assess_claim(self, claim_id: str, evidence: list[dict] | None = None) -> SkillResult:
        claim = self._claims.get(claim_id)
        if not claim:
            return SkillResult.fail(f"Claim not found: {claim_id}")
        evidence = evidence or []
        verdict = "needs_more_evidence" if not evidence else "partially_supported"
        result = {
            "claim_id": claim_id,
            "verdict": verdict,
            "confidence": 0.35 if not evidence else 0.62,
            "evidence_count": len(evidence),
        }
        claim.update(result)
        return SkillResult.ok(result)

    async def quick_check(self, claim_text: str) -> SkillResult:
        has_number = any(ch.isdigit() for ch in claim_text)
        risk = "high" if has_number else "medium"
        return SkillResult.ok({
            "claim_text": claim_text,
            "checkability": "high" if has_number else "moderate",
            "risk_of_misinformation": risk,
        })

    async def compare_sources(self, claim_text: str, sources: list[str]) -> SkillResult:
        return SkillResult.ok({
            "claim_text": claim_text,
            "sources": [{"source": src, "stance": "unknown", "notes": "manual verification needed"} for src in sources],
        })

    async def get_verdict_summary(self, claim_ids: list[str] | None = None) -> SkillResult:
        selected = [self._claims[cid] for cid in (claim_ids or list(self._claims.keys())) if cid in self._claims]
        return SkillResult.ok({
            "total": len(selected),
            "verdicts": [
                {"claim_id": c.get("claim_id"), "verdict": c.get("verdict", "unverified"), "confidence": c.get("confidence", 0.0)}
                for c in selected
            ],
        })
