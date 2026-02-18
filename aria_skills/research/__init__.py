# aria_skills/research.py
"""
📚 Research Skill - Journalist/Analyst Focus

Provides research capabilities for Aria's Journalist persona.
Handles source discovery, article synthesis, and research workflows.
Persists via REST API (TICKET-12: eliminate in-memory stubs).
"""
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from aria_skills.api_client import get_api_client
from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus, logged_method
from aria_skills.registry import SkillRegistry


@dataclass
class Source:
    """A research source."""
    id: str
    url: str
    title: str
    source_type: str  # article, paper, social, official
    credibility: float = 0.5
    accessed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    notes: str = ""


@dataclass
class ResearchProject:
    """A research project or investigation."""
    id: str
    topic: str
    thesis: str | None = None
    sources: list[Source] = field(default_factory=list)
    findings: list[str] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)
    status: str = "active"  # active, completed, archived
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@SkillRegistry.register
class ResearchSkill(BaseSkill):
    """
    Research and investigation capabilities.
    
    Capabilities:
    - Research project management
    - Source tracking and evaluation
    - Finding synthesis
    - Research question generation
    """
    
    # Source type credibility defaults
    SOURCE_CREDIBILITY = {
        "peer_reviewed": 0.95,
        "academic": 0.85,
        "official": 0.80,
        "major_news": 0.70,
        "industry": 0.65,
        "blog": 0.40,
        "social": 0.25,
        "unknown": 0.30,
    }
    
    @property
    def name(self) -> str:
        return "research"
    
    async def initialize(self) -> bool:
        """Initialize research skill."""
        self._projects: dict[str, ResearchProject] = {}  # fallback cache
        self._api = await get_api_client()
        self._status = SkillStatus.AVAILABLE
        self.logger.info("📚 Research skill initialized (API-backed)")
        return True
    
    async def close(self):
        """Cleanup (shared API client is managed by api_client module)."""
        self._api = None
    
    async def health_check(self) -> SkillStatus:
        """Check research skill availability."""
        return self._status
    
    @logged_method()
    async def start_project(
        self,
        topic: str,
        initial_questions: list[str] | None = None
    ) -> SkillResult:
        """
        Start a new research project.
        
        Args:
            topic: Research topic
            initial_questions: Starting research questions
            
        Returns:
            SkillResult with project details
        """
        try:
            project_hash = hashlib.md5(f"{topic}{datetime.now(timezone.utc).isoformat()}".encode()).hexdigest()[:8]
            project_id = f"research_{project_hash}"
            
            project = ResearchProject(
                id=project_id,
                topic=topic,
                questions=initial_questions or self._generate_research_questions(topic)
            )
            
            self._projects[project_id] = project
            
            # Persist to API
            await self._save_project_to_api(project)
            
            return SkillResult.ok({
                "project_id": project_id,
                "topic": topic,
                "questions": project.questions,
                "status": project.status,
                "started_at": project.started_at.isoformat(),
                "next_steps": [
                    "Add sources with add_source()",
                    "Record findings with add_finding()",
                    "Synthesize with synthesize()"
                ]
            })
            
        except Exception as e:
            return SkillResult.fail(f"Project creation failed: {str(e)}")
    
    async def add_source(
        self,
        project_id: str,
        url: str,
        title: str,
        source_type: str = "unknown",
        notes: str = ""
    ) -> SkillResult:
        """
        Add a source to a research project.
        
        Args:
            project_id: Target project
            url: Source URL
            title: Source title
            source_type: Type (peer_reviewed, academic, official, major_news, industry, blog, social)
            notes: Notes about the source
            
        Returns:
            SkillResult confirming source added
        """
        try:
            if project_id not in self._projects:
                return SkillResult.fail(f"Project not found: {project_id}")
            
            project = self._projects[project_id]
            source_hash = hashlib.md5(url.encode()).hexdigest()[:8]
            
            source = Source(
                id=f"src_{source_hash}",
                url=url,
                title=title,
                source_type=source_type,
                credibility=self.SOURCE_CREDIBILITY.get(source_type, 0.30),
                notes=notes
            )
            
            project.sources.append(source)
            
            # Persist to API
            await self._save_project_to_api(project)
            
            return SkillResult.ok({
                "source_id": source.id,
                "title": title,
                "credibility": source.credibility,
                "total_sources": len(project.sources),
                "credibility_assessment": self._assess_credibility_label(source.credibility)
            })
            
        except Exception as e:
            return SkillResult.fail(f"Source addition failed: {str(e)}")
    
    async def add_finding(
        self,
        project_id: str,
        finding: str,
        source_ids: list[str] | None = None
    ) -> SkillResult:
        """
        Add a finding to a research project.
        
        Args:
            project_id: Target project
            finding: The finding/insight
            source_ids: IDs of sources supporting this finding
            
        Returns:
            SkillResult confirming finding added
        """
        try:
            if project_id not in self._projects:
                return SkillResult.fail(f"Project not found: {project_id}")
            
            project = self._projects[project_id]
            
            # Format finding with source references if provided
            if source_ids:
                source_refs = ", ".join(source_ids)
                finding = f"{finding} [Sources: {source_refs}]"
            
            project.findings.append(finding)
            
            # Persist to API
            await self._save_project_to_api(project)
            
            return SkillResult.ok({
                "finding": finding,
                "total_findings": len(project.findings),
                "project_id": project_id
            })
            
        except Exception as e:
            return SkillResult.fail(f"Finding addition failed: {str(e)}")
    
    async def set_thesis(self, project_id: str, thesis: str) -> SkillResult:
        """
        Set or update the project thesis.
        
        Args:
            project_id: Target project
            thesis: Main thesis/hypothesis
            
        Returns:
            SkillResult confirming thesis set
        """
        try:
            if project_id not in self._projects:
                return SkillResult.fail(f"Project not found: {project_id}")
            
            project = self._projects[project_id]
            project.thesis = thesis
            
            # Persist to API
            await self._save_project_to_api(project)
            
            return SkillResult.ok({
                "project_id": project_id,
                "thesis": thesis,
                "tip": "Now gather sources and findings to support or challenge this thesis"
            })
            
        except Exception as e:
            return SkillResult.fail(f"Thesis setting failed: {str(e)}")
    
    async def evaluate_sources(self, project_id: str) -> SkillResult:
        """
        Evaluate source quality for a project.
        
        Args:
            project_id: Target project
            
        Returns:
            SkillResult with source evaluation
        """
        try:
            if project_id not in self._projects:
                return SkillResult.fail(f"Project not found: {project_id}")
            
            project = self._projects[project_id]
            
            if not project.sources:
                return SkillResult.fail("No sources to evaluate")
            
            # Analyze source distribution
            type_counts = {}
            for source in project.sources:
                type_counts[source.source_type] = type_counts.get(source.source_type, 0) + 1
            
            avg_credibility = sum(s.credibility for s in project.sources) / len(project.sources)
            
            # Generate recommendations
            recommendations = []
            
            if type_counts.get("peer_reviewed", 0) == 0:
                recommendations.append("Consider adding peer-reviewed sources")
            
            if type_counts.get("social", 0) > len(project.sources) * 0.3:
                recommendations.append("Reduce reliance on social media sources")
            
            if avg_credibility < 0.5:
                recommendations.append("Overall source quality is low - seek more credible sources")
            
            if len(project.sources) < 5:
                recommendations.append("Add more sources for comprehensive coverage")
            
            return SkillResult.ok({
                "project_id": project_id,
                "total_sources": len(project.sources),
                "source_types": type_counts,
                "average_credibility": round(avg_credibility, 2),
                "credibility_rating": self._assess_credibility_label(avg_credibility),
                "recommendations": recommendations,
                "sources": [
                    {
                        "id": s.id,
                        "title": s.title,
                        "type": s.source_type,
                        "credibility": round(s.credibility, 2)
                    }
                    for s in sorted(project.sources, key=lambda x: x.credibility, reverse=True)
                ]
            })
            
        except Exception as e:
            return SkillResult.fail(f"Source evaluation failed: {str(e)}")
    
    async def synthesize(self, project_id: str) -> SkillResult:
        """
        Synthesize findings into a summary.
        
        Args:
            project_id: Target project
            
        Returns:
            SkillResult with synthesis
        """
        try:
            if project_id not in self._projects:
                return SkillResult.fail(f"Project not found: {project_id}")
            
            project = self._projects[project_id]
            
            # Build synthesis
            synthesis = {
                "topic": project.topic,
                "thesis": project.thesis,
                "sources_reviewed": len(project.sources),
                "key_findings": project.findings,
                "open_questions": project.questions,
                "source_quality": {
                    "high": sum(1 for s in project.sources if s.credibility >= 0.7),
                    "medium": sum(1 for s in project.sources if 0.4 <= s.credibility < 0.7),
                    "low": sum(1 for s in project.sources if s.credibility < 0.4),
                },
                "gaps": self._identify_gaps(project),
                "conclusion_readiness": self._assess_conclusion_readiness(project)
            }
            
            return SkillResult.ok(synthesis)
            
        except Exception as e:
            return SkillResult.fail(f"Synthesis failed: {str(e)}")
    
    @logged_method()
    async def complete_project(
        self,
        project_id: str,
        summary: str | None = None
    ) -> SkillResult:
        """
        Mark a project as completed.
        
        Args:
            project_id: Target project
            summary: Final summary
            
        Returns:
            SkillResult with project summary
        """
        try:
            if project_id not in self._projects:
                return SkillResult.fail(f"Project not found: {project_id}")
            
            project = self._projects[project_id]
            project.status = "completed"
            
            # Persist to API
            await self._save_project_to_api(project)
            
            return SkillResult.ok({
                "project_id": project_id,
                "topic": project.topic,
                "thesis": project.thesis,
                "status": "completed",
                "summary": summary,
                "stats": {
                    "sources": len(project.sources),
                    "findings": len(project.findings),
                    "duration_hours": round((datetime.now(timezone.utc) - project.started_at).total_seconds() / 3600, 1)
                },
                "completed_at": datetime.now(timezone.utc).isoformat()
            })
            
        except Exception as e:
            return SkillResult.fail(f"Project completion failed: {str(e)}")
    
    async def list_projects(self, status: str | None = None) -> SkillResult:
        """
        List research projects.
        
        Args:
            status: Filter by status (active, completed, archived)
            
        Returns:
            SkillResult with project list
        """
        try:
            # Try API first
            params = {"type": "research"}
            if status:
                params["status"] = status
            resp = await self._api._client.get("/memories", params=params)
            resp.raise_for_status()
            api_data = resp.json()
            memories = api_data if isinstance(api_data, list) else api_data.get("memories", [])
            projects = []
            for mem in memories:
                data = mem.get("data", mem)
                projects.append({
                    "id": data.get("id", mem.get("id", "")),
                    "topic": data.get("topic", ""),
                    "thesis": data.get("thesis"),
                    "status": data.get("status", "active"),
                    "sources": len(data.get("sources", [])),
                    "findings": len(data.get("findings", [])),
                    "started_at": data.get("started_at", ""),
                })
            if status:
                projects = [p for p in projects if p["status"] == status]
            return SkillResult.ok({"projects": projects, "total": len(projects), "filter": status})
        except Exception as e:
            self.logger.warning(f"API list_projects failed, using fallback: {e}")
            # Fallback to in-memory
            try:
                projects = []
                for project in self._projects.values():
                    if status and project.status != status:
                        continue
                    projects.append({
                        "id": project.id,
                        "topic": project.topic,
                        "thesis": project.thesis,
                        "status": project.status,
                        "sources": len(project.sources),
                        "findings": len(project.findings),
                        "started_at": project.started_at.isoformat()
                    })
                return SkillResult.ok({"projects": projects, "total": len(projects), "filter": status})
            except Exception as e2:
                return SkillResult.fail(f"Project listing failed: {str(e2)}")
    
    # === Private Helper Methods ===
    
    async def _save_project_to_api(self, project: ResearchProject) -> None:
        """Persist a research project to the API as a memory entry."""
        try:
            memory_data = {
                "type": "research",
                "key": project.id,
                "data": self._serialize_project(project),
            }
            await self._api._client.post("/memories", json=memory_data)
        except Exception as e:
            self.logger.warning(f"API _save_project_to_api failed: {e}")
    
    def _serialize_project(self, project: ResearchProject) -> dict:
        """Serialize a ResearchProject to a JSON-safe dict."""
        return {
            "id": project.id,
            "topic": project.topic,
            "thesis": project.thesis,
            "status": project.status,
            "started_at": project.started_at.isoformat(),
            "questions": project.questions,
            "findings": project.findings,
            "sources": [
                {
                    "id": s.id,
                    "url": s.url,
                    "title": s.title,
                    "source_type": s.source_type,
                    "credibility": s.credibility,
                    "accessed_at": s.accessed_at.isoformat(),
                    "notes": s.notes,
                }
                for s in project.sources
            ],
        }
    
    def _generate_research_questions(self, topic: str) -> list[str]:
        """Generate initial research questions for a topic."""
        return [
            f"What is the current state of {topic}?",
            f"What are the key players/stakeholders in {topic}?",
            f"What are the main challenges in {topic}?",
            f"What are the emerging trends in {topic}?",
            f"What evidence exists about {topic}?",
        ]
    
    def _assess_credibility_label(self, score: float) -> str:
        """Get credibility label from score."""
        if score >= 0.8:
            return "Highly Credible ⭐"
        elif score >= 0.6:
            return "Credible ✅"
        elif score >= 0.4:
            return "Mixed Credibility ⚠️"
        else:
            return "Low Credibility ❌"
    
    def _identify_gaps(self, project: ResearchProject) -> list[str]:
        """Identify research gaps."""
        gaps = []
        
        if not project.thesis:
            gaps.append("No thesis defined")
        
        if len(project.sources) < 3:
            gaps.append("Insufficient sources")
        
        if not project.findings:
            gaps.append("No findings recorded")
        
        if len(project.questions) == len(self._generate_research_questions(project.topic)):
            gaps.append("Original questions not addressed")
        
        return gaps
    
    def _assess_conclusion_readiness(self, project: ResearchProject) -> dict:
        """Assess readiness to draw conclusions."""
        score = 0
        max_score = 100
        
        if project.thesis:
            score += 20
        
        if len(project.sources) >= 5:
            score += 20
        elif len(project.sources) >= 3:
            score += 10
        
        if len(project.findings) >= 5:
            score += 30
        elif len(project.findings) >= 3:
            score += 15
        
        high_quality_sources = sum(1 for s in project.sources if s.credibility >= 0.7)
        if high_quality_sources >= 3:
            score += 30
        elif high_quality_sources >= 1:
            score += 15
        
        return {
            "score": score,
            "max_score": max_score,
            "ready": score >= 70,
            "label": "Ready" if score >= 70 else "Needs More Research"
        }


# Skill instance factory
def create_skill(config: SkillConfig) -> ResearchSkill:
    """Create a research skill instance."""
    return ResearchSkill(config)
