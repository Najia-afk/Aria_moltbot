# aria_skills/brainstorm.py
"""
🎨 Brainstorming Skill - Creative Focus

Provides creative ideation and brainstorming for Aria's Creative persona.
Handles idea generation, concept exploration, and creative problem-solving.
"""
import random
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from .base import BaseSkill, SkillConfig, SkillResult, SkillStatus


@dataclass
class Idea:
    """A brainstormed idea."""
    id: str
    title: str
    description: str
    category: str
    tags: list[str] = field(default_factory=list)
    score: float = 0.0  # Relevance/quality score
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class BrainstormSession:
    """A brainstorming session."""
    id: str
    topic: str
    ideas: list[Idea] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.utcnow)


class BrainstormSkill(BaseSkill):
    """
    Creative brainstorming and ideation.
    
    Capabilities:
    - Idea generation with different techniques
    - Concept mapping and connections
    - Creative constraints and prompts
    - Idea evaluation and ranking
    """
    
    # Creative prompts by category
    CREATIVE_PROMPTS = {
        "tech": [
            "What if we combined {A} with {B}?",
            "How would a 5-year-old solve this?",
            "What's the opposite approach?",
            "What would this look like in 10 years?",
            "What can we remove instead of add?",
        ],
        "content": [
            "What story hasn't been told?",
            "What's the contrarian view?",
            "How can we make this visual?",
            "What emotion should this evoke?",
            "Who is the unexpected audience?",
        ],
        "business": [
            "What's the 10x version?",
            "How can we make it free?",
            "What would the competitor never do?",
            "What's the minimum viable experiment?",
            "Who else has solved a similar problem?",
        ],
        "design": [
            "What if it had to fit in a tweet?",
            "How would nature solve this?",
            "What's the brutalist approach?",
            "What would make someone smile?",
            "What can we borrow from another domain?",
        ]
    }
    
    # Brainstorming techniques
    TECHNIQUES = {
        "scamper": {
            "name": "SCAMPER",
            "description": "Substitute, Combine, Adapt, Modify, Put to other uses, Eliminate, Reverse",
            "prompts": [
                "What can we substitute?",
                "What can we combine?",
                "What can we adapt from elsewhere?",
                "What can we modify or magnify?",
                "What else can this be used for?",
                "What can we eliminate?",
                "What if we reversed it?"
            ]
        },
        "six_hats": {
            "name": "Six Thinking Hats",
            "description": "Explore from different perspectives",
            "prompts": [
                "🎩 White Hat: What are the facts?",
                "🎩 Red Hat: What's your gut feeling?",
                "🎩 Black Hat: What could go wrong?",
                "🎩 Yellow Hat: What are the benefits?",
                "🎩 Green Hat: What are creative alternatives?",
                "🎩 Blue Hat: What's the process/summary?"
            ]
        },
        "random_word": {
            "name": "Random Word Association",
            "description": "Use random words to spark connections",
            "words": ["tree", "ocean", "lightning", "bridge", "mirror", "spiral", 
                     "garden", "compass", "flame", "cloud", "puzzle", "rhythm"]
        },
        "worst_idea": {
            "name": "Worst Idea First",
            "description": "Start with intentionally bad ideas, then flip them",
            "prompts": [
                "What's the worst way to solve this?",
                "How can we make it fail spectacularly?",
                "What would guarantee user complaints?",
                "Now... what's the opposite of each bad idea?"
            ]
        }
    }
    
    @property
    def name(self) -> str:
        return "brainstorm"
    
    async def initialize(self) -> bool:
        """Initialize brainstorming skill."""
        self._sessions: dict[str, BrainstormSession] = {}
        self._idea_counter = 0
        self._status = SkillStatus.AVAILABLE
        self.logger.info("🎨 Brainstorm skill initialized")
        return True
    
    async def health_check(self) -> SkillStatus:
        """Check brainstorm skill availability."""
        return self._status
    
    async def start_session(
        self,
        topic: str,
        constraints: Optional[list[str]] = None
    ) -> SkillResult:
        """
        Start a new brainstorming session.
        
        Args:
            topic: Topic or problem to brainstorm
            constraints: Optional constraints to work within
            
        Returns:
            SkillResult with session ID and initial prompts
        """
        try:
            session_id = f"bs_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            
            session = BrainstormSession(
                id=session_id,
                topic=topic,
                constraints=constraints or []
            )
            
            self._sessions[session_id] = session
            
            # Generate initial prompts based on topic
            category = self._detect_category(topic)
            initial_prompts = random.sample(self.CREATIVE_PROMPTS.get(category, self.CREATIVE_PROMPTS["tech"]), 3)
            
            return SkillResult.ok({
                "session_id": session_id,
                "topic": topic,
                "constraints": constraints or [],
                "category_detected": category,
                "initial_prompts": initial_prompts,
                "tip": "Use add_idea() to capture ideas, or try a technique like 'scamper'",
                "started_at": session.started_at.isoformat()
            })
            
        except Exception as e:
            return SkillResult.fail(f"Session start failed: {str(e)}")
    
    async def add_idea(
        self,
        session_id: str,
        title: str,
        description: str,
        tags: Optional[list[str]] = None
    ) -> SkillResult:
        """
        Add an idea to a session.
        
        Args:
            session_id: Brainstorming session ID
            title: Idea title
            description: Idea description
            tags: Optional tags
            
        Returns:
            SkillResult confirming idea added
        """
        try:
            if session_id not in self._sessions:
                return SkillResult.fail(f"Session not found: {session_id}")
            
            session = self._sessions[session_id]
            self._idea_counter += 1
            
            idea = Idea(
                id=f"idea_{self._idea_counter}",
                title=title,
                description=description,
                category=self._detect_category(title + " " + description),
                tags=tags or []
            )
            
            session.ideas.append(idea)
            
            return SkillResult.ok({
                "idea_id": idea.id,
                "title": title,
                "session_ideas_count": len(session.ideas),
                "follow_up_prompt": self._generate_follow_up(idea)
            })
            
        except Exception as e:
            return SkillResult.fail(f"Add idea failed: {str(e)}")
    
    async def apply_technique(
        self,
        session_id: str,
        technique: str
    ) -> SkillResult:
        """
        Apply a brainstorming technique to the session.
        
        Args:
            session_id: Brainstorming session ID
            technique: Technique name (scamper, six_hats, random_word, worst_idea)
            
        Returns:
            SkillResult with technique prompts
        """
        try:
            if session_id not in self._sessions:
                return SkillResult.fail(f"Session not found: {session_id}")
            
            technique = technique.lower()
            if technique not in self.TECHNIQUES:
                return SkillResult.fail(f"Unknown technique. Available: {list(self.TECHNIQUES.keys())}")
            
            session = self._sessions[session_id]
            tech = self.TECHNIQUES[technique]
            
            if technique == "random_word":
                words = random.sample(tech["words"], 3)
                prompts = [f"How does '{word}' connect to {session.topic}?" for word in words]
            else:
                prompts = tech.get("prompts", [])
            
            return SkillResult.ok({
                "technique": tech["name"],
                "description": tech["description"],
                "prompts": prompts,
                "topic": session.topic,
                "tip": "Answer each prompt and add the ideas to your session"
            })
            
        except Exception as e:
            return SkillResult.fail(f"Technique application failed: {str(e)}")
    
    async def get_random_prompt(self, category: Optional[str] = None) -> SkillResult:
        """
        Get a random creative prompt.
        
        Args:
            category: Optional category (tech, content, business, design)
            
        Returns:
            SkillResult with random prompt
        """
        try:
            if category and category in self.CREATIVE_PROMPTS:
                prompts = self.CREATIVE_PROMPTS[category]
            else:
                prompts = [p for cat_prompts in self.CREATIVE_PROMPTS.values() for p in cat_prompts]
            
            prompt = random.choice(prompts)
            
            return SkillResult.ok({
                "prompt": prompt,
                "category": category or "mixed",
                "tip": "Replace {A} and {B} with concepts from your problem space"
            })
            
        except Exception as e:
            return SkillResult.fail(f"Prompt generation failed: {str(e)}")
    
    async def connect_ideas(
        self,
        session_id: str,
        idea_ids: Optional[list[str]] = None
    ) -> SkillResult:
        """
        Find connections between ideas in a session.
        
        Args:
            session_id: Brainstorming session ID
            idea_ids: Optional specific ideas to connect (or all)
            
        Returns:
            SkillResult with connection suggestions
        """
        try:
            if session_id not in self._sessions:
                return SkillResult.fail(f"Session not found: {session_id}")
            
            session = self._sessions[session_id]
            
            if len(session.ideas) < 2:
                return SkillResult.fail("Need at least 2 ideas to find connections")
            
            ideas = session.ideas
            if idea_ids:
                ideas = [i for i in ideas if i.id in idea_ids]
            
            connections = []
            
            # Find potential connections (simplified - based on shared tags/categories)
            for i, idea1 in enumerate(ideas):
                for idea2 in ideas[i+1:]:
                    # Check for shared tags
                    shared_tags = set(idea1.tags) & set(idea2.tags)
                    if shared_tags:
                        connections.append({
                            "idea_1": idea1.title,
                            "idea_2": idea2.title,
                            "connection_type": "shared_tags",
                            "shared": list(shared_tags),
                            "synthesis_prompt": f"How can we combine '{idea1.title}' and '{idea2.title}'?"
                        })
                    
                    # Same category
                    if idea1.category == idea2.category:
                        connections.append({
                            "idea_1": idea1.title,
                            "idea_2": idea2.title,
                            "connection_type": "same_category",
                            "category": idea1.category,
                            "synthesis_prompt": f"Both relate to {idea1.category}. What's a meta-solution?"
                        })
            
            # Add random connection suggestion
            if len(ideas) >= 2:
                random_pair = random.sample(ideas, 2)
                connections.append({
                    "idea_1": random_pair[0].title,
                    "idea_2": random_pair[1].title,
                    "connection_type": "random_pairing",
                    "synthesis_prompt": f"Force a connection: '{random_pair[0].title}' + '{random_pair[1].title}' = ?"
                })
            
            return SkillResult.ok({
                "session_id": session_id,
                "ideas_analyzed": len(ideas),
                "connections": connections,
                "tip": "The most creative ideas often come from unexpected connections"
            })
            
        except Exception as e:
            return SkillResult.fail(f"Connection analysis failed: {str(e)}")
    
    async def evaluate_ideas(
        self,
        session_id: str,
        criteria: Optional[list[str]] = None
    ) -> SkillResult:
        """
        Evaluate and rank ideas in a session.
        
        Args:
            session_id: Brainstorming session ID
            criteria: Evaluation criteria (default: feasibility, impact, novelty)
            
        Returns:
            SkillResult with ranked ideas
        """
        try:
            if session_id not in self._sessions:
                return SkillResult.fail(f"Session not found: {session_id}")
            
            session = self._sessions[session_id]
            criteria = criteria or ["feasibility", "impact", "novelty"]
            
            if not session.ideas:
                return SkillResult.fail("No ideas to evaluate")
            
            evaluations = []
            
            for idea in session.ideas:
                # Simplified scoring (in production, could use LLM)
                scores = {}
                for criterion in criteria:
                    # Random score for demo (0-10)
                    scores[criterion] = round(random.uniform(3, 10), 1)
                
                avg_score = sum(scores.values()) / len(scores)
                idea.score = avg_score
                
                evaluations.append({
                    "idea_id": idea.id,
                    "title": idea.title,
                    "scores": scores,
                    "average_score": round(avg_score, 2)
                })
            
            # Sort by average score
            evaluations.sort(key=lambda x: x["average_score"], reverse=True)
            
            return SkillResult.ok({
                "session_id": session_id,
                "criteria": criteria,
                "evaluations": evaluations,
                "top_idea": evaluations[0] if evaluations else None,
                "recommendation": f"Focus on '{evaluations[0]['title']}' for highest potential" if evaluations else None
            })
            
        except Exception as e:
            return SkillResult.fail(f"Evaluation failed: {str(e)}")
    
    async def summarize_session(self, session_id: str) -> SkillResult:
        """
        Get a summary of a brainstorming session.
        
        Args:
            session_id: Brainstorming session ID
            
        Returns:
            SkillResult with session summary
        """
        try:
            if session_id not in self._sessions:
                return SkillResult.fail(f"Session not found: {session_id}")
            
            session = self._sessions[session_id]
            
            # Categorize ideas
            categories = {}
            for idea in session.ideas:
                if idea.category not in categories:
                    categories[idea.category] = []
                categories[idea.category].append(idea.title)
            
            # Collect all tags
            all_tags = set()
            for idea in session.ideas:
                all_tags.update(idea.tags)
            
            return SkillResult.ok({
                "session_id": session_id,
                "topic": session.topic,
                "constraints": session.constraints,
                "total_ideas": len(session.ideas),
                "ideas_by_category": categories,
                "all_tags": list(all_tags),
                "ideas": [
                    {
                        "id": i.id,
                        "title": i.title,
                        "description": i.description,
                        "score": i.score
                    }
                    for i in session.ideas
                ],
                "duration_minutes": round((datetime.utcnow() - session.started_at).total_seconds() / 60, 1),
                "next_steps": [
                    "Evaluate ideas if not done",
                    "Find connections between top ideas",
                    "Prototype the most promising concept"
                ]
            })
            
        except Exception as e:
            return SkillResult.fail(f"Summary failed: {str(e)}")
    
    # === Private Helper Methods ===
    
    def _detect_category(self, text: str) -> str:
        """Detect category from text."""
        text = text.lower()
        
        tech_keywords = ["code", "api", "system", "software", "algorithm", "data", "platform"]
        content_keywords = ["story", "article", "video", "post", "blog", "tweet", "content"]
        business_keywords = ["product", "market", "customer", "revenue", "growth", "startup"]
        design_keywords = ["ui", "ux", "interface", "visual", "layout", "experience"]
        
        scores = {
            "tech": sum(1 for kw in tech_keywords if kw in text),
            "content": sum(1 for kw in content_keywords if kw in text),
            "business": sum(1 for kw in business_keywords if kw in text),
            "design": sum(1 for kw in design_keywords if kw in text),
        }
        
        return max(scores.keys(), key=lambda k: scores[k]) if max(scores.values()) > 0 else "tech"
    
    def _generate_follow_up(self, idea: Idea) -> str:
        """Generate a follow-up prompt for an idea."""
        prompts = [
            f"What's the MVP version of '{idea.title}'?",
            f"Who would benefit most from '{idea.title}'?",
            f"What's the biggest risk with '{idea.title}'?",
            f"How could '{idea.title}' fail? How to prevent it?",
            f"What's missing from '{idea.title}'?",
        ]
        return random.choice(prompts)


# Skill instance factory
def create_skill(config: SkillConfig) -> BrainstormSkill:
    """Create a brainstorm skill instance."""
    return BrainstormSkill(config)
