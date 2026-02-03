# aria_skills/fact_check.py
"""
📰 Fact-Checking Skill - Journalist Focus

Provides fact-checking and claim verification for Aria's Journalist persona.
Handles claim extraction, source verification, and accuracy assessment.
"""
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from .base import BaseSkill, SkillConfig, SkillResult, SkillStatus


@dataclass
class Claim:
    """A claim to be fact-checked."""
    id: str
    text: str
    source: Optional[str] = None
    category: str = "general"  # statistics, quote, event, scientific, legal
    checkworthy_score: float = 0.5


@dataclass
class Verdict:
    """Fact-check verdict for a claim."""
    claim_id: str
    rating: str  # true, mostly_true, half_true, mostly_false, false, unverifiable
    confidence: float
    explanation: str
    supporting_sources: list[str] = field(default_factory=list)
    contradicting_sources: list[str] = field(default_factory=list)
    checked_at: datetime = field(default_factory=datetime.utcnow)


class FactCheckSkill(BaseSkill):
    """
    Fact-checking and claim verification.
    
    Capabilities:
    - Claim extraction from text
    - Check-worthiness assessment
    - Verdict generation
    - Source credibility analysis
    """
    
    # Patterns that indicate checkable claims
    CLAIM_PATTERNS = [
        (r'\d+%', "statistics"),
        (r'\$[\d,]+', "statistics"),
        (r'according to', "quote"),
        (r'"[^"]{20,}"', "quote"),
        (r'studies show|research shows|data shows', "scientific"),
        (r'always|never|every|none|all', "absolute"),
        (r'first|largest|smallest|most|least', "superlative"),
        (r'will|would|could|should', "prediction"),
    ]
    
    # Rating definitions
    RATINGS = {
        "true": {"score": 1.0, "emoji": "✅", "description": "Accurate, supported by evidence"},
        "mostly_true": {"score": 0.75, "emoji": "🟢", "description": "Accurate but needs context"},
        "half_true": {"score": 0.5, "emoji": "🟡", "description": "Partially accurate"},
        "mostly_false": {"score": 0.25, "emoji": "🟠", "description": "Contains significant errors"},
        "false": {"score": 0.0, "emoji": "❌", "description": "Not supported by evidence"},
        "unverifiable": {"score": -1, "emoji": "❓", "description": "Cannot be verified"}
    }
    
    @property
    def name(self) -> str:
        return "fact_check"
    
    async def initialize(self) -> bool:
        """Initialize fact-check skill."""
        self._claims: dict[str, Claim] = {}
        self._verdicts: dict[str, Verdict] = {}
        self._claim_counter = 0
        self._status = SkillStatus.AVAILABLE
        self.logger.info("🔍 Fact-check skill initialized")
        return True
    
    async def health_check(self) -> SkillStatus:
        """Check fact-check skill availability."""
        return self._status
    
    async def extract_claims(self, text: str) -> SkillResult:
        """
        Extract checkable claims from text.
        
        Args:
            text: Text to analyze
            
        Returns:
            SkillResult with extracted claims
        """
        try:
            sentences = re.split(r'[.!?]+', text)
            claims = []
            
            for sentence in sentences:
                sentence = sentence.strip()
                if len(sentence) < 20:
                    continue
                
                # Check for claim patterns
                category = "general"
                checkworthy = 0.3  # Base score
                
                for pattern, cat in self.CLAIM_PATTERNS:
                    if re.search(pattern, sentence, re.IGNORECASE):
                        category = cat
                        checkworthy += 0.15
                
                # Boost for specific claim indicators
                if any(word in sentence.lower() for word in ["claim", "state", "assert", "declare"]):
                    checkworthy += 0.2
                
                checkworthy = min(checkworthy, 1.0)
                
                if checkworthy > 0.4:  # Only include likely claims
                    self._claim_counter += 1
                    claim = Claim(
                        id=f"claim_{self._claim_counter}",
                        text=sentence,
                        category=category,
                        checkworthy_score=checkworthy
                    )
                    self._claims[claim.id] = claim
                    
                    claims.append({
                        "id": claim.id,
                        "text": claim.text,
                        "category": category,
                        "checkworthy_score": round(checkworthy, 2)
                    })
            
            # Sort by checkworthy score
            claims.sort(key=lambda x: x["checkworthy_score"], reverse=True)
            
            return SkillResult.ok({
                "claims": claims,
                "total_claims": len(claims),
                "most_checkworthy": claims[0] if claims else None,
                "by_category": self._group_by_category(claims)
            })
            
        except Exception as e:
            return SkillResult.fail(f"Claim extraction failed: {str(e)}")
    
    async def assess_claim(
        self,
        claim_id: str,
        evidence: Optional[list[dict]] = None
    ) -> SkillResult:
        """
        Assess a claim and generate verdict.
        
        Args:
            claim_id: Claim ID to assess
            evidence: Optional evidence list with {source, supports: bool, content}
            
        Returns:
            SkillResult with verdict
        """
        try:
            if claim_id not in self._claims:
                return SkillResult.fail(f"Claim not found: {claim_id}")
            
            claim = self._claims[claim_id]
            evidence = evidence or []
            
            # Analyze evidence
            supporting = [e for e in evidence if e.get("supports", False)]
            contradicting = [e for e in evidence if not e.get("supports", True)]
            
            # Calculate verdict
            if not evidence:
                rating = "unverifiable"
                confidence = 0.0
                explanation = "No evidence provided to verify this claim"
            else:
                support_ratio = len(supporting) / len(evidence) if evidence else 0
                
                if support_ratio >= 0.9:
                    rating = "true"
                elif support_ratio >= 0.7:
                    rating = "mostly_true"
                elif support_ratio >= 0.4:
                    rating = "half_true"
                elif support_ratio >= 0.2:
                    rating = "mostly_false"
                else:
                    rating = "false"
                
                confidence = min(len(evidence) * 0.2, 1.0)  # More evidence = higher confidence
                explanation = self._generate_explanation(claim, supporting, contradicting)
            
            verdict = Verdict(
                claim_id=claim_id,
                rating=rating,
                confidence=confidence,
                explanation=explanation,
                supporting_sources=[e.get("source", "Unknown") for e in supporting],
                contradicting_sources=[e.get("source", "Unknown") for e in contradicting]
            )
            
            self._verdicts[claim_id] = verdict
            rating_info = self.RATINGS[rating]
            
            return SkillResult.ok({
                "claim_id": claim_id,
                "claim_text": claim.text,
                "verdict": {
                    "rating": rating,
                    "emoji": rating_info["emoji"],
                    "description": rating_info["description"],
                    "confidence": round(confidence, 2),
                    "explanation": explanation
                },
                "evidence_summary": {
                    "total": len(evidence),
                    "supporting": len(supporting),
                    "contradicting": len(contradicting)
                },
                "checked_at": verdict.checked_at.isoformat()
            })
            
        except Exception as e:
            return SkillResult.fail(f"Assessment failed: {str(e)}")
    
    async def quick_check(self, claim_text: str) -> SkillResult:
        """
        Quick assessment of a claim's characteristics.
        
        Args:
            claim_text: Claim text to analyze
            
        Returns:
            SkillResult with quick analysis
        """
        try:
            analysis = {
                "claim": claim_text,
                "red_flags": [],
                "needs_verification": [],
                "claim_type": "general"
            }
            
            claim_lower = claim_text.lower()
            
            # Check for red flags
            if any(word in claim_lower for word in ["always", "never", "everyone", "no one"]):
                analysis["red_flags"].append("Contains absolute language")
            
            if re.search(r'\d+%', claim_text):
                analysis["needs_verification"].append("Contains specific statistics")
                analysis["claim_type"] = "statistics"
            
            if "according to" in claim_lower or '"' in claim_text:
                analysis["needs_verification"].append("Contains attributed quote")
                analysis["claim_type"] = "quote"
            
            if any(word in claim_lower for word in ["first", "largest", "only", "most"]):
                analysis["red_flags"].append("Contains superlative claim")
                analysis["claim_type"] = "superlative"
            
            if "study" in claim_lower or "research" in claim_lower:
                analysis["needs_verification"].append("References research - verify source")
                analysis["claim_type"] = "scientific"
            
            if not any(char.isdigit() for char in claim_text):
                if len(analysis["needs_verification"]) == 0:
                    analysis["needs_verification"].append("Vague claim - look for specifics")
            
            # Checkworthiness score
            checkworthy = 0.3 + len(analysis["red_flags"]) * 0.15 + len(analysis["needs_verification"]) * 0.1
            
            return SkillResult.ok({
                "analysis": analysis,
                "checkworthy_score": round(min(checkworthy, 1.0), 2),
                "recommendation": self._get_recommendation(analysis)
            })
            
        except Exception as e:
            return SkillResult.fail(f"Quick check failed: {str(e)}")
    
    async def compare_sources(
        self,
        claim_text: str,
        sources: list[dict]
    ) -> SkillResult:
        """
        Compare how different sources report a claim.
        
        Args:
            claim_text: The claim being checked
            sources: List of {name, content, date?} dicts
            
        Returns:
            SkillResult with source comparison
        """
        try:
            if len(sources) < 2:
                return SkillResult.fail("Need at least 2 sources to compare")
            
            comparisons = []
            
            # Analyze each source
            for source in sources:
                stance = self._detect_stance(source.get("content", ""), claim_text)
                comparisons.append({
                    "source": source.get("name", "Unknown"),
                    "stance": stance,
                    "date": source.get("date"),
                    "key_language": self._extract_key_language(source.get("content", ""))
                })
            
            # Calculate agreement
            stances = [c["stance"] for c in comparisons]
            agreement_score = stances.count(stances[0]) / len(stances) if stances else 0
            
            # Identify consensus or disagreement
            stance_counts = {}
            for stance in stances:
                stance_counts[stance] = stance_counts.get(stance, 0) + 1
            
            dominant_stance = max(stance_counts.keys(), key=lambda k: stance_counts[k])
            
            return SkillResult.ok({
                "claim": claim_text,
                "sources_analyzed": len(sources),
                "comparisons": comparisons,
                "agreement_score": round(agreement_score, 2),
                "dominant_stance": dominant_stance,
                "consensus": agreement_score > 0.7,
                "recommendation": "High agreement - claim likely accurate" if agreement_score > 0.7 
                                  else "Sources disagree - investigate further"
            })
            
        except Exception as e:
            return SkillResult.fail(f"Comparison failed: {str(e)}")
    
    async def get_verdict_summary(self, claim_ids: Optional[list[str]] = None) -> SkillResult:
        """
        Get summary of verdicts.
        
        Args:
            claim_ids: Optional specific claims (or all)
            
        Returns:
            SkillResult with verdict summary
        """
        try:
            verdicts = self._verdicts
            if claim_ids:
                verdicts = {k: v for k, v in verdicts.items() if k in claim_ids}
            
            if not verdicts:
                return SkillResult.ok({
                    "message": "No verdicts to summarize",
                    "total_verdicts": 0
                })
            
            # Count by rating
            rating_counts = {}
            for verdict in verdicts.values():
                rating_counts[verdict.rating] = rating_counts.get(verdict.rating, 0) + 1
            
            # Average confidence
            avg_confidence = sum(v.confidence for v in verdicts.values()) / len(verdicts)
            
            return SkillResult.ok({
                "total_verdicts": len(verdicts),
                "by_rating": {
                    rating: {
                        "count": count,
                        "emoji": self.RATINGS[rating]["emoji"]
                    }
                    for rating, count in rating_counts.items()
                },
                "average_confidence": round(avg_confidence, 2),
                "verdicts": [
                    {
                        "claim_id": v.claim_id,
                        "claim_text": self._claims[v.claim_id].text if v.claim_id in self._claims else "Unknown",
                        "rating": v.rating,
                        "emoji": self.RATINGS[v.rating]["emoji"]
                    }
                    for v in verdicts.values()
                ]
            })
            
        except Exception as e:
            return SkillResult.fail(f"Summary failed: {str(e)}")
    
    # === Private Helper Methods ===
    
    def _group_by_category(self, claims: list[dict]) -> dict:
        """Group claims by category."""
        groups = {}
        for claim in claims:
            cat = claim["category"]
            if cat not in groups:
                groups[cat] = []
            groups[cat].append(claim["id"])
        return groups
    
    def _generate_explanation(
        self, 
        claim: Claim, 
        supporting: list, 
        contradicting: list
    ) -> str:
        """Generate verdict explanation."""
        parts = []
        
        if supporting:
            parts.append(f"{len(supporting)} source(s) support this claim")
        if contradicting:
            parts.append(f"{len(contradicting)} source(s) contradict this claim")
        
        if len(supporting) > len(contradicting):
            parts.append("The weight of evidence supports the claim")
        elif len(contradicting) > len(supporting):
            parts.append("The weight of evidence contradicts the claim")
        else:
            parts.append("Evidence is mixed")
        
        return ". ".join(parts) + "."
    
    def _get_recommendation(self, analysis: dict) -> str:
        """Get verification recommendation."""
        if analysis["red_flags"]:
            return "⚠️ Claim contains red flags - verify carefully"
        elif analysis["needs_verification"]:
            return "🔍 Claim needs verification - check sources"
        else:
            return "ℹ️ Standard claim - basic verification recommended"
    
    def _detect_stance(self, content: str, claim: str) -> str:
        """Detect source stance on claim."""
        content_lower = content.lower()
        
        # Simple heuristic
        positive_indicators = ["confirms", "supports", "agrees", "verified", "true", "correct"]
        negative_indicators = ["denies", "disputes", "false", "incorrect", "misleading", "debunked"]
        
        pos_count = sum(1 for ind in positive_indicators if ind in content_lower)
        neg_count = sum(1 for ind in negative_indicators if ind in content_lower)
        
        if pos_count > neg_count:
            return "supports"
        elif neg_count > pos_count:
            return "contradicts"
        else:
            return "neutral"
    
    def _extract_key_language(self, content: str) -> list[str]:
        """Extract key phrases from content."""
        # Simple extraction of quoted phrases and key terms
        quotes = re.findall(r'"([^"]{10,50})"', content)
        return quotes[:3] if quotes else []


# Skill instance factory
def create_skill(config: SkillConfig) -> FactCheckSkill:
    """Create a fact-check skill instance."""
    return FactCheckSkill(config)
