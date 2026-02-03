# aria_skills/research.py
"""
📰 Research Skill - Journalist Focus

Provides research and information gathering for Aria's Journalist persona.
Handles source collection, information synthesis, and citation management.
"""
import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from urllib.parse import urlparse

from .base import BaseSkill, SkillConfig, SkillResult, SkillStatus


@dataclass
class Source:
    """A research source."""
    id: str
    title: str
    url: Optional[str] = None
    author: Optional[str] = None
    date: Optional[datetime] = None
    content_summary: Optional[str] = None
    credibility_score: float = 0.5
    source_type: str = "unknown"  # article, paper, social, official, wiki


@dataclass
class ResearchProject:
    """A research project."""
    id: str
    topic: str
    sources: list[Source] = field(default_factory=list)
    notes: list[dict] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)


class ResearchSkill(BaseSkill):
    """
    Research and information gathering.
    
    Capabilities:
    - Source collection and organization
    - Credibility assessment
    - Information synthesis
    - Citation management
    - Research question generation
    """
    
    # Source type indicators
    SOURCE_INDICATORS = {
        "paper": [".edu", "arxiv", "doi.org", "pubmed", "scholar.google", "jstor"],
        "official": [".gov", ".mil", "official", "whitehouse", "europa.eu"],
        "news": ["nytimes", "bbc", "reuters", "apnews", "guardian", "wsj"],
        "social": ["twitter", "x.com", "reddit", "linkedin", "facebook"],
        "wiki": ["wikipedia", "wiki"],
        "tech": ["github", "stackoverflow", "medium", "dev.to"],
    }
    
    @property
    def name(self) -> str:
        return "research"
    
    async def initialize(self) -> bool:
        """Initialize research skill."""
        self._projects: dict[str, ResearchProject] = {}
        self._source_counter = 0
        self._status = SkillStatus.AVAILABLE
        self.logger.info("📰 Research skill initialized")
        return True
    
    async def health_check(self) -> SkillStatus:
        """Check research skill availability."""
        return self._status
    
    async def create_project(
        self,
        topic: str,
        initial_questions: Optional[list[str]] = None
    ) -> SkillResult:
        """
        Create a new research project.
        
        Args:
            topic: Research topic
            initial_questions: Starting research questions
            
        Returns:
            SkillResult with project ID
        """
        try:
            project_id = f"rp_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            
            project = ResearchProject(
                id=project_id,
                topic=topic,
                questions=initial_questions or []
            )
            
            self._projects[project_id] = project
            
            # Generate suggested questions
            suggested_questions = self._generate_research_questions(topic)
            
            return SkillResult.ok({
                "project_id": project_id,
                "topic": topic,
                "initial_questions": initial_questions or [],
                "suggested_questions": suggested_questions,
                "created_at": project.created_at.isoformat()
            })
            
        except Exception as e:
            return SkillResult.fail(f"Project creation failed: {str(e)}")
    
    async def add_source(
        self,
        project_id: str,
        title: str,
        url: Optional[str] = None,
        author: Optional[str] = None,
        date: Optional[str] = None,
        summary: Optional[str] = None
    ) -> SkillResult:
        """
        Add a source to a research project.
        
        Args:
            project_id: Research project ID
            title: Source title
            url: Source URL
            author: Author name
            date: Publication date (ISO format)
            summary: Content summary
            
        Returns:
            SkillResult with source details
        """
        try:
            if project_id not in self._projects:
                return SkillResult.fail(f"Project not found: {project_id}")
            
            project = self._projects[project_id]
            self._source_counter += 1
            
            # Detect source type
            source_type = self._detect_source_type(url) if url else "unknown"
            
            # Calculate credibility score
            credibility = self._assess_credibility(url, source_type)
            
            source = Source(
                id=f"src_{self._source_counter}",
                title=title,
                url=url,
                author=author,
                date=datetime.fromisoformat(date) if date else None,
                content_summary=summary,
                source_type=source_type,
                credibility_score=credibility
            )
            
            project.sources.append(source)
            
            return SkillResult.ok({
                "source_id": source.id,
                "title": title,
                "source_type": source_type,
                "credibility_score": round(credibility, 2),
                "credibility_label": self._credibility_label(credibility),
                "project_sources_count": len(project.sources),
                "citation": self._generate_citation(source)
            })
            
        except Exception as e:
            return SkillResult.fail(f"Add source failed: {str(e)}")
    
    async def add_note(
        self,
        project_id: str,
        content: str,
        source_ids: Optional[list[str]] = None,
        tags: Optional[list[str]] = None
    ) -> SkillResult:
        """
        Add a research note.
        
        Args:
            project_id: Research project ID
            content: Note content
            source_ids: Related source IDs
            tags: Note tags
            
        Returns:
            SkillResult confirming note added
        """
        try:
            if project_id not in self._projects:
                return SkillResult.fail(f"Project not found: {project_id}")
            
            project = self._projects[project_id]
            
            note = {
                "id": f"note_{len(project.notes) + 1}",
                "content": content,
                "source_ids": source_ids or [],
                "tags": tags or [],
                "created_at": datetime.utcnow().isoformat()
            }
            
            project.notes.append(note)
            
            return SkillResult.ok({
                "note_id": note["id"],
                "content_preview": content[:100] + "..." if len(content) > 100 else content,
                "linked_sources": len(source_ids) if source_ids else 0,
                "project_notes_count": len(project.notes)
            })
            
        except Exception as e:
            return SkillResult.fail(f"Add note failed: {str(e)}")
    
    async def generate_questions(
        self,
        project_id: str,
        depth: str = "medium"
    ) -> SkillResult:
        """
        Generate research questions for a project.
        
        Args:
            project_id: Research project ID
            depth: Question depth (surface, medium, deep)
            
        Returns:
            SkillResult with generated questions
        """
        try:
            if project_id not in self._projects:
                return SkillResult.fail(f"Project not found: {project_id}")
            
            project = self._projects[project_id]
            
            questions = self._generate_research_questions(project.topic, depth)
            
            # Add to project
            project.questions.extend(questions)
            
            return SkillResult.ok({
                "project_id": project_id,
                "topic": project.topic,
                "depth": depth,
                "questions": questions,
                "total_questions": len(project.questions)
            })
            
        except Exception as e:
            return SkillResult.fail(f"Question generation failed: {str(e)}")
    
    async def assess_sources(self, project_id: str) -> SkillResult:
        """
        Assess the quality and coverage of sources.
        
        Args:
            project_id: Research project ID
            
        Returns:
            SkillResult with source assessment
        """
        try:
            if project_id not in self._projects:
                return SkillResult.fail(f"Project not found: {project_id}")
            
            project = self._projects[project_id]
            
            if not project.sources:
                return SkillResult.ok({
                    "message": "No sources to assess",
                    "recommendation": "Add sources to begin assessment"
                })
            
            # Analyze source distribution
            type_counts = {}
            total_credibility = 0
            
            for source in project.sources:
                type_counts[source.source_type] = type_counts.get(source.source_type, 0) + 1
                total_credibility += source.credibility_score
            
            avg_credibility = total_credibility / len(project.sources)
            
            # Generate recommendations
            recommendations = []
            
            if "paper" not in type_counts and "official" not in type_counts:
                recommendations.append("Consider adding academic or official sources for credibility")
            
            if len(project.sources) < 3:
                recommendations.append("Add more sources for comprehensive coverage")
            
            if avg_credibility < 0.6:
                recommendations.append("Overall source credibility is low - verify claims carefully")
            
            if len(type_counts) < 3:
                recommendations.append("Diversify source types for balanced perspective")
            
            # Check for recency
            old_sources = [s for s in project.sources if s.date and (datetime.utcnow() - s.date).days > 365]
            if len(old_sources) > len(project.sources) / 2:
                recommendations.append("Many sources are over a year old - check for recent developments")
            
            return SkillResult.ok({
                "project_id": project_id,
                "source_count": len(project.sources),
                "by_type": type_counts,
                "average_credibility": round(avg_credibility, 2),
                "credibility_label": self._credibility_label(avg_credibility),
                "recommendations": recommendations,
                "coverage_score": min(len(project.sources) * 10, 100)
            })
            
        except Exception as e:
            return SkillResult.fail(f"Assessment failed: {str(e)}")
    
    async def synthesize(self, project_id: str) -> SkillResult:
        """
        Synthesize research into a summary.
        
        Args:
            project_id: Research project ID
            
        Returns:
            SkillResult with synthesis
        """
        try:
            if project_id not in self._projects:
                return SkillResult.fail(f"Project not found: {project_id}")
            
            project = self._projects[project_id]
            
            # Collect all information
            source_summaries = [s.content_summary for s in project.sources if s.content_summary]
            note_contents = [n["content"] for n in project.notes]
            
            # Create synthesis structure
            synthesis = {
                "topic": project.topic,
                "key_questions": project.questions[:5],
                "source_count": len(project.sources),
                "notes_count": len(project.notes),
                "key_findings": [
                    f"Based on {len(project.sources)} sources",
                    f"Collected {len(project.notes)} research notes",
                    f"Explored {len(project.questions)} research questions"
                ],
                "source_types_used": list(set(s.source_type for s in project.sources)),
                "citations": [self._generate_citation(s) for s in project.sources[:10]],
                "gaps_identified": self._identify_gaps(project),
                "next_steps": [
                    "Verify key claims with additional sources",
                    "Interview subject matter experts",
                    "Draft initial findings"
                ]
            }
            
            return SkillResult.ok({
                "project_id": project_id,
                "synthesis": synthesis,
                "generated_at": datetime.utcnow().isoformat()
            })
            
        except Exception as e:
            return SkillResult.fail(f"Synthesis failed: {str(e)}")
    
    async def get_bibliography(
        self,
        project_id: str,
        style: str = "apa"
    ) -> SkillResult:
        """
        Generate bibliography for a project.
        
        Args:
            project_id: Research project ID
            style: Citation style (apa, mla, chicago)
            
        Returns:
            SkillResult with formatted bibliography
        """
        try:
            if project_id not in self._projects:
                return SkillResult.fail(f"Project not found: {project_id}")
            
            project = self._projects[project_id]
            
            citations = []
            for source in project.sources:
                citation = self._generate_citation(source, style)
                citations.append(citation)
            
            # Sort alphabetically
            citations.sort()
            
            return SkillResult.ok({
                "project_id": project_id,
                "style": style.upper(),
                "source_count": len(citations),
                "bibliography": citations
            })
            
        except Exception as e:
            return SkillResult.fail(f"Bibliography generation failed: {str(e)}")
    
    # === Private Helper Methods ===
    
    def _detect_source_type(self, url: str) -> str:
        """Detect source type from URL."""
        if not url:
            return "unknown"
        
        url_lower = url.lower()
        
        for source_type, indicators in self.SOURCE_INDICATORS.items():
            if any(ind in url_lower for ind in indicators):
                return source_type
        
        return "article"  # Default
    
    def _assess_credibility(self, url: Optional[str], source_type: str) -> float:
        """Assess source credibility."""
        base_scores = {
            "paper": 0.85,
            "official": 0.90,
            "news": 0.70,
            "tech": 0.65,
            "wiki": 0.60,
            "social": 0.40,
            "unknown": 0.50,
            "article": 0.55,
        }
        
        score = base_scores.get(source_type, 0.50)
        
        # Adjust based on URL features
        if url:
            if "https" in url:
                score += 0.05
            if ".edu" in url or ".gov" in url:
                score += 0.10
        
        return min(score, 1.0)
    
    def _credibility_label(self, score: float) -> str:
        """Get credibility label from score."""
        if score >= 0.8:
            return "High"
        elif score >= 0.6:
            return "Medium"
        elif score >= 0.4:
            return "Low"
        else:
            return "Very Low"
    
    def _generate_citation(self, source: Source, style: str = "apa") -> str:
        """Generate citation for a source."""
        author = source.author or "Unknown Author"
        year = source.date.year if source.date else "n.d."
        title = source.title
        
        if style == "apa":
            if source.url:
                return f"{author} ({year}). {title}. Retrieved from {source.url}"
            return f"{author} ({year}). {title}."
        
        elif style == "mla":
            if source.url:
                return f'{author}. "{title}." Web. {source.url}'
            return f'{author}. "{title}."'
        
        else:  # Chicago
            if source.url:
                return f'{author}. "{title}." Accessed {datetime.utcnow().strftime("%B %d, %Y")}. {source.url}'
            return f'{author}. "{title}."'
    
    def _generate_research_questions(self, topic: str, depth: str = "medium") -> list[str]:
        """Generate research questions for a topic."""
        base_questions = [
            f"What is the current state of {topic}?",
            f"Who are the key players in {topic}?",
            f"What are the main challenges in {topic}?",
        ]
        
        medium_questions = [
            f"How has {topic} evolved over time?",
            f"What are the competing perspectives on {topic}?",
            f"What evidence supports or contradicts claims about {topic}?",
        ]
        
        deep_questions = [
            f"What underlying assumptions exist about {topic}?",
            f"What are the second-order effects of {topic}?",
            f"How might {topic} be different in alternative contexts?",
            f"What would it take to disprove the common narrative about {topic}?",
        ]
        
        if depth == "surface":
            return base_questions
        elif depth == "medium":
            return base_questions + medium_questions
        else:  # deep
            return base_questions + medium_questions + deep_questions
    
    def _identify_gaps(self, project: ResearchProject) -> list[str]:
        """Identify research gaps."""
        gaps = []
        
        type_counts = {}
        for source in project.sources:
            type_counts[source.source_type] = type_counts.get(source.source_type, 0) + 1
        
        if "paper" not in type_counts:
            gaps.append("No academic/research sources")
        if "official" not in type_counts:
            gaps.append("No official/government sources")
        if len(project.notes) < len(project.sources):
            gaps.append("Not all sources have been analyzed with notes")
        
        return gaps


# Skill instance factory
def create_skill(config: SkillConfig) -> ResearchSkill:
    """Create a research skill instance."""
    return ResearchSkill(config)
