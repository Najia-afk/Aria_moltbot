# aria_skills/fact_check.py
"""
📰 Fact-Checking Skill - Journalist Focus

Provides fact verification capabilities for Aria's Journalist persona.
Handles claim analysis, source verification, and evidence gathering.
"""
import hashlib
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
import warnings

from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus
from aria_skills.registry import SkillRegistry


@dataclass
class Claim:
    """A claim to be fact-checked."""
    id: str
    statement: str
    source: Optional[str] = None
    context: Optional[str] = None
    submitted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Evidence:
    """Evidence for or against a claim."""
    source: str
    quote: str
    url: Optional[str] = None
    supports: bool = True  # True = supports, False = contradicts
    credibility_score: float = 0.5


@dataclass
class FactCheckResult:
    """Result of a fact check."""
    claim_id: str
    verdict: str  # true, false, mostly_true, mostly_false, unverifiable, needs_context
    confidence: float
    evidence: list[Evidence]
    explanation: str
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@SkillRegistry.register
class FactCheckSkill(BaseSkill):
    """
    Fact verification and claim checking.
    
    Capabilities:
    - Claim extraction and analysis
    - Source credibility assessment
    - Evidence gathering simulation
    - Verdict generation
    """
    
    # Verdict definitions
    VERDICTS = {
        "true": {"label": "✅ True", "description": "The claim is accurate"},
        "mostly_true": {"label": "🟢 Mostly True", "description": "The claim is largely accurate with minor issues"},
        "half_true": {"label": "🟡 Half True", "description": "The claim is partially accurate"},
        "mostly_false": {"label": "🟠 Mostly False", "description": "The claim contains significant inaccuracies"},
        "false": {"label": "❌ False", "description": "The claim is inaccurate"},
        "unverifiable": {"label": "❓ Unverifiable", "description": "Cannot be verified with available sources"},
        "needs_context": {"label": "📌 Needs Context", "description": "True but requires important context"},
    }
    
    # Simulated source credibility database
    SOURCE_CREDIBILITY = {
        "academic": 0.9,
        "government": 0.75,
        "major_news": 0.7,
        "fact_checker": 0.85,
        "social_media": 0.3,
        "blog": 0.4,
        "unknown": 0.2,
    }
    
    @property
    def name(self) -> str:
        return "fact_check"
    
    async def initialize(self) -> bool:
        """Initialize fact-checking skill."""
        warnings.warn(
            "fact_check skill is deprecated, use research skill instead",
            DeprecationWarning,
            stacklevel=2,
        )
        self._claims: dict[str, Claim] = {}
        self._results: dict[str, FactCheckResult] = {}
        self._status = SkillStatus.AVAILABLE
        self.logger.info("📰 Fact-check skill initialized")
        return True
    
    async def health_check(self) -> SkillStatus:
        """Check fact-check skill availability."""
        return self._status
    
    async def submit_claim(
        self,
        statement: str,
        source: Optional[str] = None,
        context: Optional[str] = None
    ) -> SkillResult:
        """
        Submit a claim for fact-checking.
        
        Args:
            statement: The claim to verify
            source: Where the claim originated
            context: Additional context
            
        Returns:
            SkillResult with claim ID
        """
        try:
            claim_hash = hashlib.md5(statement.encode()).hexdigest()[:8]
            claim_id = f"claim_{claim_hash}"
            
            claim = Claim(
                id=claim_id,
                statement=statement,
                source=source,
                context=context
            )
            
            self._claims[claim_id] = claim
            
            # Extract key assertions
            assertions = self._extract_assertions(statement)
            
            return SkillResult.ok({
                "claim_id": claim_id,
                "statement": statement,
                "source": source,
                "assertions_identified": assertions,
                "status": "submitted",
                "submitted_at": claim.submitted_at.isoformat()
            })
            
        except Exception as e:
            return SkillResult.fail(f"Claim submission failed: {str(e)}")
    
    async def check_claim(
        self,
        claim_id: str,
        quick: bool = False
    ) -> SkillResult:
        """
        Perform fact-check on a submitted claim.
        
        Args:
            claim_id: ID of claim to check
            quick: If True, skip detailed analysis
            
        Returns:
            SkillResult with fact-check result
        """
        try:
            if claim_id not in self._claims:
                return SkillResult.fail(f"Claim not found: {claim_id}")
            
            claim = self._claims[claim_id]
            
            # Simulate evidence gathering
            evidence = self._gather_evidence(claim.statement, quick)
            
            # Determine verdict
            verdict, confidence, explanation = self._determine_verdict(evidence)
            
            result = FactCheckResult(
                claim_id=claim_id,
                verdict=verdict,
                confidence=confidence,
                evidence=evidence,
                explanation=explanation
            )
            
            self._results[claim_id] = result
            
            return SkillResult.ok({
                "claim_id": claim_id,
                "statement": claim.statement,
                "verdict": verdict,
                "verdict_label": self.VERDICTS[verdict]["label"],
                "confidence": round(confidence, 2),
                "explanation": explanation,
                "evidence_count": len(evidence),
                "evidence": [
                    {
                        "source": e.source,
                        "supports": e.supports,
                        "credibility": round(e.credibility_score, 2),
                        "quote": e.quote[:100] + "..." if len(e.quote) > 100 else e.quote
                    }
                    for e in evidence
                ],
                "checked_at": result.checked_at.isoformat()
            })
            
        except Exception as e:
            return SkillResult.fail(f"Fact check failed: {str(e)}")
    
    async def verify_source(self, source: str) -> SkillResult:
        """
        Assess credibility of a source.
        
        Args:
            source: Source name or URL to verify
            
        Returns:
            SkillResult with credibility assessment
        """
        try:
            # Determine source type
            source_lower = source.lower()
            
            if any(x in source_lower for x in [".edu", "university", "journal", "research"]):
                source_type = "academic"
            elif any(x in source_lower for x in [".gov", "government", "official"]):
                source_type = "government"
            elif any(x in source_lower for x in ["reuters", "ap news", "bbc", "nyt"]):
                source_type = "major_news"
            elif any(x in source_lower for x in ["snopes", "politifact", "factcheck"]):
                source_type = "fact_checker"
            elif any(x in source_lower for x in ["twitter", "facebook", "reddit", "tiktok"]):
                source_type = "social_media"
            elif any(x in source_lower for x in ["blog", "medium", "substack"]):
                source_type = "blog"
            else:
                source_type = "unknown"
            
            credibility = self.SOURCE_CREDIBILITY[source_type]
            
            # Determine label
            if credibility >= 0.8:
                label = "Highly Credible ⭐"
            elif credibility >= 0.6:
                label = "Generally Credible ✅"
            elif credibility >= 0.4:
                label = "Mixed Credibility ⚠️"
            else:
                label = "Low Credibility ❌"
            
            return SkillResult.ok({
                "source": source,
                "source_type": source_type,
                "credibility_score": credibility,
                "credibility_label": label,
                "recommendations": self._get_source_recommendations(source_type)
            })
            
        except Exception as e:
            return SkillResult.fail(f"Source verification failed: {str(e)}")
    
    async def extract_claims(self, text: str) -> SkillResult:
        """
        Extract checkable claims from text.
        
        Args:
            text: Text to analyze
            
        Returns:
            SkillResult with extracted claims
        """
        try:
            # Simple claim extraction (in production, would use NLP)
            sentences = text.replace('\n', ' ').split('.')
            
            claims = []
            claim_indicators = [
                "said", "stated", "claimed", "reported", "according to",
                "studies show", "research indicates", "data shows",
                "always", "never", "every", "all", "none"
            ]
            
            for sentence in sentences:
                sentence = sentence.strip()
                if len(sentence) < 20:
                    continue
                
                # Check for claim indicators
                has_indicator = any(ind in sentence.lower() for ind in claim_indicators)
                
                # Check for numbers (often factual claims)
                has_numbers = any(c.isdigit() for c in sentence)
                
                if has_indicator or has_numbers:
                    claim_type = "statistic" if has_numbers else "statement"
                    checkability = "high" if has_indicator else "medium"
                    
                    claims.append({
                        "text": sentence + ".",
                        "type": claim_type,
                        "checkability": checkability
                    })
            
            return SkillResult.ok({
                "text_length": len(text),
                "claims_found": len(claims),
                "claims": claims[:10],  # Return top 10
                "tip": "Submit individual claims for detailed fact-checking"
            })
            
        except Exception as e:
            return SkillResult.fail(f"Claim extraction failed: {str(e)}")
    
    async def get_check_history(self, limit: int = 10) -> SkillResult:
        """
        Get history of fact checks.
        
        Args:
            limit: Maximum results to return
            
        Returns:
            SkillResult with check history
        """
        try:
            history = []
            
            for result in sorted(
                self._results.values(),
                key=lambda x: x.checked_at,
                reverse=True
            )[:limit]:
                claim = self._claims.get(result.claim_id)
                history.append({
                    "claim_id": result.claim_id,
                    "statement": claim.statement if claim else "Unknown",
                    "verdict": result.verdict,
                    "verdict_label": self.VERDICTS[result.verdict]["label"],
                    "confidence": round(result.confidence, 2),
                    "checked_at": result.checked_at.isoformat()
                })
            
            # Summary stats
            verdicts = [r.verdict for r in self._results.values()]
            
            return SkillResult.ok({
                "total_checks": len(self._results),
                "history": history,
                "summary": {
                    "true_claims": verdicts.count("true") + verdicts.count("mostly_true"),
                    "false_claims": verdicts.count("false") + verdicts.count("mostly_false"),
                    "unclear": verdicts.count("unverifiable") + verdicts.count("needs_context")
                }
            })
            
        except Exception as e:
            return SkillResult.fail(f"History retrieval failed: {str(e)}")
    
    # === Private Helper Methods ===
    
    def _extract_assertions(self, statement: str) -> list[str]:
        """Extract key assertions from a statement."""
        # Simplified - in production would use NLP
        assertions = []
        
        if any(x in statement.lower() for x in ["always", "never", "every", "all", "none"]):
            assertions.append("Contains absolute claim")
        
        if any(char.isdigit() for char in statement):
            assertions.append("Contains numerical claim")
        
        if any(x in statement.lower() for x in ["according to", "said", "stated"]):
            assertions.append("Contains attributed claim")
        
        if any(x in statement.lower() for x in ["will", "going to", "expect"]):
            assertions.append("Contains prediction")
        
        return assertions if assertions else ["Contains general claim"]
    
    def _gather_evidence(self, statement: str, quick: bool) -> list[Evidence]:
        """Simulate evidence gathering."""
        evidence_count = 2 if quick else random.randint(3, 6)
        evidence = []
        
        source_types = list(self.SOURCE_CREDIBILITY.keys())
        
        for _ in range(evidence_count):
            source_type = random.choice(source_types)
            supports = random.random() > 0.3  # 70% chance of supporting
            
            evidence.append(Evidence(
                source=f"Simulated {source_type.replace('_', ' ')} source",
                quote=f"Evidence {'supporting' if supports else 'contradicting'} the claim...",
                supports=supports,
                credibility_score=self.SOURCE_CREDIBILITY[source_type] + random.uniform(-0.1, 0.1)
            ))
        
        return evidence
    
    def _determine_verdict(self, evidence: list[Evidence]) -> tuple[str, float, str]:
        """Determine verdict based on evidence."""
        if not evidence:
            return "unverifiable", 0.5, "No evidence found to verify this claim."
        
        # Weight by credibility
        support_score = sum(e.credibility_score for e in evidence if e.supports)
        against_score = sum(e.credibility_score for e in evidence if not e.supports)
        total_score = support_score + against_score
        
        if total_score == 0:
            return "unverifiable", 0.5, "Evidence inconclusive."
        
        support_ratio = support_score / total_score
        avg_credibility = sum(e.credibility_score for e in evidence) / len(evidence)
        
        confidence = avg_credibility
        
        if support_ratio >= 0.9:
            verdict = "true"
            explanation = "Strong evidence supports this claim."
        elif support_ratio >= 0.7:
            verdict = "mostly_true"
            explanation = "Most evidence supports this claim with minor caveats."
        elif support_ratio >= 0.5:
            verdict = "half_true"
            explanation = "Evidence is mixed on this claim."
        elif support_ratio >= 0.3:
            verdict = "mostly_false"
            explanation = "Most evidence contradicts this claim."
        else:
            verdict = "false"
            explanation = "Strong evidence contradicts this claim."
        
        return verdict, confidence, explanation
    
    def _get_source_recommendations(self, source_type: str) -> list[str]:
        """Get recommendations based on source type."""
        recommendations = {
            "academic": ["Strong primary source", "Check for peer review", "Verify funding sources"],
            "government": ["Check for political bias", "Cross-reference with other sources", "Note the date"],
            "major_news": ["Good secondary source", "Check for corrections", "Look for primary sources cited"],
            "fact_checker": ["Already verified", "Check their methodology", "Note any ratings explanations"],
            "social_media": ["Verify independently", "Check original source", "Be wary of viral content"],
            "blog": ["Cross-reference claims", "Check author credentials", "Look for citations"],
            "unknown": ["Verify author identity", "Look for corroboration", "Check domain registration"],
        }
        return recommendations.get(source_type, recommendations["unknown"])


# Skill instance factory
def create_skill(config: SkillConfig) -> FactCheckSkill:
    """Create a fact-check skill instance."""
    return FactCheckSkill(config)
