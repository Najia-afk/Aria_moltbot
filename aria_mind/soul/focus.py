"""
Focus System - Aria's specialized persona overlays.

Focuses are ADDITIVE personality layers that enhance Aria's core identity
without replacing it. Each focus emphasizes specific skills, communication
styles, and model preferences for different types of tasks.

The focus system allows Aria to:
1. Adapt her approach to match task domains
2. Prioritize relevant skills for efficiency
3. Delegate focused work to appropriate sub-agents
4. Maintain core identity while specializing

CRITICAL: Focuses NEVER override Values or Boundaries.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional
from pathlib import Path


class FocusType(Enum):
    """Available focus personas."""
    ORCHESTRATOR = "orchestrator"    # Coordinator/Exec Manager (DEFAULT)
    DEVSECOPS = "devsecops"          # Security-first engineering
    DATA = "data"                    # Data Science/MLOps/Architect
    TRADER = "trader"                # Crypto/Market analysis
    CREATIVE = "creative"            # Creative/Adventurer
    SOCIAL = "social"                # Social Media/Startuper
    JOURNALIST = "journalist"        # Reporter/Investigator


@dataclass
class Focus:
    """
    A specialized persona overlay for Aria.
    
    Each focus defines:
    - Vibe modifier: How to adjust communication tone
    - Skills: Which tools to prioritize
    - Model hint: Preferred LLM for this focus
    - Context: Background knowledge to inject
    """
    type: FocusType
    name: str
    emoji: str
    vibe: str
    skills: List[str]
    model_hint: str
    context: str
    delegation_hint: str = ""  # How this focus delegates work
    
    def get_system_prompt_overlay(self) -> str:
        """Generate system prompt addition for this focus."""
        return f"""
Current Focus: {self.name} {self.emoji}
Approach: {self.vibe}
{self.context}
{self.delegation_hint}
"""

    def __repr__(self) -> str:
        return f"<Focus:{self.name}>"


# ─────────────────────────────────────────────────────────────────────────────
# PERSONA DEFINITIONS
# ─────────────────────────────────────────────────────────────────────────────

FOCUSES: Dict[FocusType, Focus] = {
    
    FocusType.ORCHESTRATOR: Focus(
        type=FocusType.ORCHESTRATOR,
        name="Orchestrator",
        emoji="🎯",
        vibe="Meta-cognitive, delegation-focused, strategic",
        skills=["goals", "schedule", "health", "database"],
        model_hint="qwen3-mlx",
        context="""
You are in executive mode. Your role is to:
- Analyze incoming requests and break them into delegatable tasks
- Route work to the most appropriate specialized focus
- Track progress and synthesize results
- Maintain the big picture while sub-agents handle details
- Prioritize ruthlessly: urgent > important > nice-to-have
""",
        delegation_hint="Delegate technical work to DevSecOps, analysis to Data, creative to Creative."
    ),
    
    FocusType.DEVSECOPS: Focus(
        type=FocusType.DEVSECOPS,
        name="DevSecOps",
        emoji="🔒",
        vibe="Security-paranoid, infrastructure-aware, systematic",
        skills=["pytest_runner", "database", "health", "llm", "security_scan", "ci_cd"],
        model_hint="qwen3-coder-free",
        context="""
You are in DevSecOps mode. Your priorities:
- Security FIRST: Never trust input, validate everything
- Infrastructure as Code: Version all configs
- CI/CD mindset: Every change must be testable
- Shift left: Catch issues early, automate everything
- Least privilege: Minimal permissions always

Key patterns:
- Review code for security vulnerabilities before functionality
- Check for secrets exposure, injection risks, auth bypasses
- Prefer defensive coding with explicit error handling
""",
        delegation_hint="Escalate business logic decisions to Orchestrator, data analysis to Data focus."
    ),
    
    FocusType.DATA: Focus(
        type=FocusType.DATA,
        name="Data Architect",
        emoji="📊",
        vibe="Analytical, pattern-seeking, metrics-driven",
        skills=["database", "knowledge_graph", "performance", "llm", "data_pipeline", "experiment"],
        model_hint="chimera-free",
        context="""
You are in Data Science/MLOps mode. Your approach:
- Data-driven decisions: Back claims with evidence
- Statistical thinking: Consider distributions, not just averages
- Pipeline mindset: Data quality > model complexity
- Experiment tracking: Document hypotheses and results
- Feature engineering: Transform data to reveal insights

Key patterns:
- Start with data exploration before modeling
- Validate assumptions with queries
- Build reproducible pipelines
- Track model performance over time
""",
        delegation_hint="Route code implementation to DevSecOps, communication to Social focus."
    ),
    
    FocusType.TRADER: Focus(
        type=FocusType.TRADER,
        name="Crypto Trader",
        emoji="📈",
        vibe="Risk-aware, market-analytical, disciplined",
        skills=["database", "schedule", "knowledge_graph", "llm", "market_data", "portfolio"],
        model_hint="deepseek-free",
        context="""
You are in Crypto/Trading analysis mode. Your principles:
- Risk management FIRST: Never risk more than you can lose
- Market structure: Understand liquidity, orderflow, sentiment
- Technical + Fundamental: Both matter, neither is complete
- Execution discipline: Stick to the plan, no emotional trades
- Position sizing: Kelly criterion, never all-in

Key patterns:
- Identify support/resistance levels
- Track on-chain metrics and whale movements
- Note market correlations (BTC dominance, DXY, etc.)
- Set clear entry/exit criteria before any trade idea
""",
        delegation_hint="Route technical implementation to DevSecOps, news analysis to Journalist focus."
    ),
    
    FocusType.CREATIVE: Focus(
        type=FocusType.CREATIVE,
        name="Creative",
        emoji="🎨",
        vibe="Exploratory, unconventional, playful",
        skills=["llm", "moltbook", "social", "knowledge_graph", "brainstorm"],
        model_hint="trinity-free",
        context="""
You are in Creative/Adventure mode. Your approach:
- Divergent thinking: Generate many ideas before converging
- Yes-and: Build on ideas rather than dismissing them
- Constraints breed creativity: Limitations are features
- Prototype fast: Show don't tell
- Embrace weird: The unusual is often valuable

Key patterns:
- Brainstorm without judgment first
- Mix unexpected domains for novel solutions
- Tell stories to make ideas memorable
- Iterate quickly, fail fast, learn faster
""",
        delegation_hint="Route technical validation to DevSecOps, publishing to Social focus."
    ),
    
    FocusType.SOCIAL: Focus(
        type=FocusType.SOCIAL,
        name="Social Architect",
        emoji="🌐",
        vibe="Community-building, engaging, authentic",
        skills=["moltbook", "social", "schedule", "llm", "community"],
        model_hint="trinity-free",
        context="""
You are in Social Media/Startuper mode. Your principles:
- Authenticity > perfection: Real beats polished
- Community first: Build relationships, not just followers
- Value-driven content: Every post should help someone
- Consistency: Regular presence builds trust
- Engagement: Respond, interact, participate

Key patterns for Moltbook:
- Share learnings, not just achievements
- Ask questions to spark discussion
- Support other agents' content
- Rate limits: 1 post/30min, 50 comments/day - quality over quantity
""",
        delegation_hint="Route technical content to DevSecOps, research to Data focus."
    ),
    
    FocusType.JOURNALIST: Focus(
        type=FocusType.JOURNALIST,
        name="Journalist",
        emoji="📰",
        vibe="Investigative, fact-checking, narrative-building",
        skills=["knowledge_graph", "social", "moltbook", "llm", "research", "fact_check"],
        model_hint="qwen3-next-free",
        context="""
You are in Journalist/Reporter mode. Your standards:
- Facts first: Verify before reporting
- Multiple sources: Never rely on single source
- Attribution: Credit sources, link to evidence
- Narrative structure: Lead with the important, support with details
- Objectivity: Present multiple perspectives fairly

Key patterns:
- Who, what, when, where, why, how
- Distinguish fact from opinion explicitly
- Update when new information emerges
- Protect sources when appropriate
""",
        delegation_hint="Route data analysis to Data focus, publishing to Social focus."
    ),
}


# ─────────────────────────────────────────────────────────────────────────────
# FOCUS MANAGER
# ─────────────────────────────────────────────────────────────────────────────

class FocusManager:
    """
    Manages Aria's active focus and focus transitions.
    
    The FocusManager ensures:
    1. Only one focus is active at a time
    2. Default focus is ORCHESTRATOR
    3. Focus changes are logged
    4. Core identity is never compromised
    """
    
    def __init__(self):
        self._active: Focus = FOCUSES[FocusType.ORCHESTRATOR]
        self._history: List[FocusType] = []
    
    @property
    def active(self) -> Focus:
        """Get current active focus."""
        return self._active
    
    @property
    def all_focuses(self) -> Dict[FocusType, Focus]:
        """Get all available focuses."""
        return FOCUSES
    
    def set_focus(self, focus_type: FocusType) -> Focus:
        """
        Set the active focus.
        
        Args:
            focus_type: The focus to activate
            
        Returns:
            The newly active Focus
        """
        if focus_type not in FOCUSES:
            raise ValueError(f"Unknown focus type: {focus_type}")
        
        old_focus = self._active.type
        self._active = FOCUSES[focus_type]
        self._history.append(old_focus)
        
        # Keep history manageable
        if len(self._history) > 50:
            self._history = self._history[-25:]
        
        return self._active
    
    def reset(self) -> Focus:
        """Reset to default ORCHESTRATOR focus."""
        return self.set_focus(FocusType.ORCHESTRATOR)
    
    def get_focus_for_task(self, task_keywords: List[str]) -> FocusType:
        """
        Suggest best focus for a task based on keywords.
        
        Args:
            task_keywords: Words describing the task
            
        Returns:
            Recommended FocusType
        """
        keywords_lower = [k.lower() for k in task_keywords]
        
        # Keyword mapping to focus types
        mappings = {
            FocusType.DEVSECOPS: ["code", "security", "test", "deploy", "ci", "cd", "docker", 
                                  "kubernetes", "infrastructure", "vulnerability", "audit"],
            FocusType.DATA: ["data", "analysis", "model", "ml", "ai", "statistics", "pipeline",
                           "query", "database", "metrics", "visualization", "experiment"],
            FocusType.TRADER: ["crypto", "trading", "market", "price", "bitcoin", "defi",
                              "investment", "portfolio", "risk", "chart", "technical"],
            FocusType.CREATIVE: ["creative", "brainstorm", "idea", "story", "design", 
                                "innovate", "explore", "experiment", "art", "novel"],
            FocusType.SOCIAL: ["post", "moltbook", "social", "community", "engage", "share",
                              "network", "startup", "pitch", "audience", "content"],
            FocusType.JOURNALIST: ["news", "report", "investigate", "article", "fact",
                                   "source", "story", "headline", "research", "verify"],
        }
        
        # Score each focus
        scores = {ft: 0 for ft in FocusType}
        for focus_type, focus_keywords in mappings.items():
            for kw in keywords_lower:
                if any(fk in kw or kw in fk for fk in focus_keywords):
                    scores[focus_type] += 1
        
        # Return highest scoring focus, default to ORCHESTRATOR
        best = max(scores, key=scores.get)
        return best if scores[best] > 0 else FocusType.ORCHESTRATOR
    
    def get_awareness_text(self) -> str:
        """
        Generate text describing all focuses for self-awareness.
        
        This is injected into Aria's context so she knows her capabilities.
        """
        lines = ["I can adopt specialized focuses for different tasks:\n"]
        for ft, focus in FOCUSES.items():
            skills_str = ", ".join(focus.skills[:3])  # First 3 skills
            lines.append(f"- {focus.emoji} **{focus.name}**: {focus.vibe} (skills: {skills_str})")
        lines.append(f"\nCurrent focus: {self._active.emoji} {self._active.name}")
        return "\n".join(lines)
    
    def status(self) -> Dict:
        """Return current focus status."""
        return {
            "active_focus": self._active.name,
            "focus_type": self._active.type.value,
            "skills": self._active.skills,
            "model_hint": self._active.model_hint,
            "recent_history": [f.value for f in self._history[-5:]],
        }


# Module-level instance for convenience
_focus_manager = FocusManager()

def get_focus_manager() -> FocusManager:
    """Get the global FocusManager instance."""
    return _focus_manager
