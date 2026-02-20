"""
Dual-Graph Memory System - Souvenir Manager

Implements the "souvenir" memory layer: long-term, immutable,
strongly-linked episodic memories that complement the working memory graph.

Architecture:
- Working Memory Graph: Fast, mutable, short-term (PostgreSQL + in-memory)
- Souvenir Memory Graph: Slow, immutable, long-term (PostgreSQL + archived)
- Cross-graph links connect related memories across layers
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, AsyncIterator
from enum import Enum, auto
import json
import hashlib


class MemoryTier(Enum):
    """Memory storage tiers - working vs souvenir."""
    WORKING = "working"      # Fast, mutable, short-term
    SOUVENIR = "souvenir"    # Slow, immutable, long-term


class CompressionStatus(Enum):
    """Status of memory compression pipeline."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class SouvenirMemory:
    """
    Immutable episodic memory stored in the souvenir layer.
    
    Once created, these memories never change - they form the
    permanent record of Aria's experiences and learnings.
    """
    id: str
    content_hash: str        # SHA256 of canonical content for integrity
    content: str             # The actual memory content
    category: str            # e.g., "learning", "interaction", "decision"
    created_at: datetime
    source_working_id: Optional[str] = None  # Original working memory ID
    importance_score: float = 0.5
    compression_ratio: Optional[float] = None  # If compressed from larger content
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Graph relationships
    related_souvenirs: List[str] = field(default_factory=list)  # IDs of related memories
    cross_graph_links: List[str] = field(default_factory=list)  # Links to working memories
    
    def verify_integrity(self) -> bool:
        """Verify content hash matches stored content."""
        computed = hashlib.sha256(self.content.encode()).hexdigest()[:32]
        return computed == self.content_hash


@dataclass
class CrossGraphLink:
    """
    Bidirectional link between working and souvenir memory.
    
    Enables traversal between memory layers while maintaining
    clear separation of concerns.
    """
    id: str
    working_memory_id: str
    souvenir_memory_id: str
    link_type: str          # e.g., "compressed_from", "summarizes", "references"
    strength: float         # 0.0-1.0 link strength
    created_at: datetime
    bidirectional: bool = True


@dataclass  
class CompressionJob:
    """
    Job for compressing working memories into souvenirs.
    
    The compression pipeline processes high-importance working
    memories and creates immutable souvenir versions.
    """
    id: str
    working_memory_ids: List[str]
    status: CompressionStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result_souvenir_id: Optional[str] = None
    compression_strategy: str = "semantic"  # semantic, extractive, abstractive
    error_message: Optional[str] = None


class SouvenirManager:
    """
    Manager for the souvenir memory layer.
    
    Responsibilities:
    - Create and store immutable souvenir memories
    - Manage cross-graph links to working memory
    - Queue compression jobs for working → souvenir transformation
    - Archive old souvenirs to cold storage
    """
    
    def __init__(self, db_pool=None, config: Optional[Dict] = None):
        self.db_pool = db_pool
        self.config = config or {}
        self.compression_queue: List[CompressionJob] = []
        
        # Configurable thresholds
        self.compression_threshold = self.config.get("compression_threshold", 0.7)
        self.auto_compress_age = self.config.get("auto_compress_age_hours", 24)
        self.max_working_age = self.config.get("max_working_age_hours", 168)  # 1 week
    
    async def create_souvenir(
        self,
        content: str,
        category: str,
        source_working_id: Optional[str] = None,
        importance_score: float = 0.5,
        metadata: Optional[Dict] = None
    ) -> SouvenirMemory:
        """
        Create a new immutable souvenir memory.
        
        Args:
            content: The memory content (will be hashed for integrity)
            category: Memory category (learning, interaction, decision, etc.)
            source_working_id: Original working memory ID if migrating
            importance_score: 0.0-1.0 importance ranking
            metadata: Additional structured data
            
        Returns:
            The created SouvenirMemory object
        """
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:32]
        memory_id = f"souv_{content_hash}"
        
        souvenir = SouvenirMemory(
            id=memory_id,
            content_hash=content_hash,
            content=content,
            category=category,
            created_at=datetime.utcnow(),
            source_working_id=source_working_id,
            importance_score=importance_score,
            metadata=metadata or {}
        )
        
        # Persist to database
        await self._persist_souvenir(souvenir)
        
        # If sourced from working memory, create cross-graph link
        if source_working_id:
            await self._create_cross_graph_link(
                working_id=source_working_id,
                souvenir_id=memory_id,
                link_type="compressed_from"
            )
        
        return souvenir
    
    async def _persist_souvenir(self, souvenir: SouvenirMemory) -> None:
        """Persist souvenir to database."""
        if not self.db_pool:
            return  # No-op if no database
            
        query = """
        INSERT INTO souvenir_memories (
            id, content_hash, content, category, created_at,
            source_working_id, importance_score, compression_ratio, metadata
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        ON CONFLICT (id) DO NOTHING
        """
        
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                query,
                souvenir.id,
                souvenir.content_hash,
                souvenir.content,
                souvenir.category,
                souvenir.created_at,
                souvenir.source_working_id,
                souvenir.importance_score,
                souvenir.compression_ratio,
                json.dumps(souvenir.metadata)
            )
    
    async def _create_cross_graph_link(
        self,
        working_id: str,
        souvenir_id: str,
        link_type: str,
        strength: float = 1.0
    ) -> CrossGraphLink:
        """Create a bidirectional link between working and souvenir memory."""
        link_id = hashlib.sha256(
            f"{working_id}:{souvenir_id}".encode()
        ).hexdigest()[:16]
        
        link = CrossGraphLink(
            id=link_id,
            working_memory_id=working_id,
            souvenir_memory_id=souvenir_id,
            link_type=link_type,
            strength=strength,
            created_at=datetime.utcnow()
        )
        
        if self.db_pool:
            query = """
            INSERT INTO cross_graph_links (
                id, working_memory_id, souvenir_memory_id,
                link_type, strength, created_at
            ) VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (id) DO UPDATE SET strength = $4
            """
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    query,
                    link.id, link.working_memory_id,
                    link.souvenir_memory_id, link.link_type,
                    link.strength, link.created_at
                )
        
        return link
    
    async def queue_compression(
        self,
        working_memory_ids: List[str],
        strategy: str = "semantic"
    ) -> CompressionJob:
        """
        Queue working memories for compression into a souvenir.
        
        Args:
            working_memory_ids: List of working memory IDs to compress
            strategy: Compression strategy (semantic, extractive, abstractive)
            
        Returns:
            The queued CompressionJob
        """
        job_id = f"comp_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{len(working_memory_ids)}"
        
        job = CompressionJob(
            id=job_id,
            working_memory_ids=working_memory_ids,
            status=CompressionStatus.PENDING,
            created_at=datetime.utcnow(),
            compression_strategy=strategy
        )
        
        self.compression_queue.append(job)
        
        # Persist to compression queue table
        if self.db_pool:
            query = """
            INSERT INTO compression_queue (
                id, working_memory_ids, status, created_at, compression_strategy
            ) VALUES ($1, $2, $3, $4, $5)
            """
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    query,
                    job.id,
                    json.dumps(working_memory_ids),
                    job.status.value,
                    job.created_at,
                    strategy
                )
        
        return job
    
    async def process_compression_job(self, job_id: str) -> Optional[SouvenirMemory]:
        """
        Process a compression job, creating a souvenir from working memories.
        
        This implements the working → souvenir memory transformation
        using the configured compression strategy.
        """
        job = next((j for j in self.compression_queue if j.id == job_id), None)
        if not job:
            return None
        
        job.status = CompressionStatus.IN_PROGRESS
        job.started_at = datetime.utcnow()
        
        try:
            # Fetch working memories to compress
            working_memories = await self._fetch_working_memories(job.working_memory_ids)
            
            # Apply compression strategy
            if job.compression_strategy == "semantic":
                content = await self._semantic_compression(working_memories)
            elif job.compression_strategy == "extractive":
                content = await self._extractive_compression(working_memories)
            else:
                content = await self._abstractive_compression(working_memories)
            
            # Create souvenir from compressed content
            souvenir = await self.create_souvenir(
                content=content,
                category="compressed_episode",
                importance_score=max(m.get("importance", 0.5) for m in working_memories),
                metadata={
                    "compression_strategy": job.compression_strategy,
                    "source_count": len(working_memories),
                    "source_ids": job.working_memory_ids
                }
            )
            
            # Update job status
            job.status = CompressionStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            job.result_souvenir_id = souvenir.id
            
            # Create cross-graph links for all source memories
            for wm_id in job.working_memory_ids:
                await self._create_cross_graph_link(
                    working_id=wm_id,
                    souvenir_id=souvenir.id,
                    link_type="summarized_in",
                    strength=0.8
                )
            
            return souvenir
            
        except Exception as e:
            job.status = CompressionStatus.FAILED
            job.error_message = str(e)
            raise
    
    async def _fetch_working_memories(self, ids: List[str]) -> List[Dict]:
        """Fetch working memories by IDs."""
        if not self.db_pool or not ids:
            return []
        
        query = """
        SELECT id, content, category, importance_score, created_at, metadata
        FROM working_memories WHERE id = ANY($1)
        """
        
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(query, ids)
            return [dict(row) for row in rows]
    
    async def _semantic_compression(self, memories: List[Dict]) -> str:
        """
        Semantic compression: cluster by meaning, remove redundancy.
        
        Groups similar memories and synthesizes them into a coherent summary.
        """
        if not memories:
            return ""
        
        # Simple implementation: concatenate with deduplication
        # Production would use embeddings + clustering
        contents = [m.get("content", "") for m in memories]
        
        # Remove near-duplicates (simplified)
        unique_contents = []
        for content in contents:
            is_duplicate = any(
                self._similarity(content, existing) > 0.9
                for existing in unique_contents
            )
            if not is_duplicate:
                unique_contents.append(content)
        
        # Generate summary header
        summary = f"[Compressed {len(memories)} memories into {len(unique_contents)} unique insights]\n\n"
        summary += "\n---\n".join(unique_contents)
        
        return summary
    
    async def _extractive_compression(self, memories: List[Dict]) -> str:
        """
        Extractive compression: select most important sentences.
        
        Keeps verbatim content but selects only the most salient parts.
        """
        if not memories:
            return ""
        
        # Sort by importance and take top content
        sorted_memories = sorted(
            memories,
            key=lambda m: m.get("importance_score", 0),
            reverse=True
        )
        
        # Take top 60% by importance
        cutoff = max(1, int(len(sorted_memories) * 0.6))
        selected = sorted_memories[:cutoff]
        
        contents = [m.get("content", "") for m in selected]
        return "\n\n".join(contents)
    
    async def _abstractive_compression(self, memories: List[Dict]) -> str:
        """
        Abstractive compression: generate new summary text.
        
        Would use LLM to generate novel summary not present in originals.
        """
        # Placeholder - would integrate with LLM for true abstractive summarization
        contents = [m.get("content", "") for m in memories]
        combined = "\n".join(contents)
        
        summary = f"[Abstractive summary of {len(memories)} related memories]:\n\n"
        # In production, this would call an LLM to generate a novel summary
        summary += combined[:500] + ("..." if len(combined) > 500 else "")
        
        return summary
    
    def _similarity(self, text1: str, text2: str) -> float:
        """Simple similarity metric (placeholder for embedding-based similarity)."""
        # Simplified Jaccard similarity on words
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1 & words2
        union = words1 | words2
        
        return len(intersection) / len(union)
    
    async def traverse_to_working(
        self,
        souvenir_id: str
    ) -> AsyncIterator[Dict]:
        """
        Traverse from a souvenir memory to related working memories.
        
        Yields working memory records linked via cross-graph links.
        """
        if not self.db_pool:
            return
        
        query = """
        SELECT wm.* FROM working_memories wm
        JOIN cross_graph_links cgl ON wm.id = cgl.working_memory_id
        WHERE cgl.souvenir_memory_id = $1
        ORDER BY cgl.strength DESC
        """
        
        async with self.db_pool.acquire() as conn:
            async with conn.transaction():
                async for row in conn.cursor(query, souvenir_id):
                    yield dict(row)
    
    async def get_souvenir_lineage(
        self,
        souvenir_id: str
    ) -> Dict[str, Any]:
        """
        Get full lineage of a souvenir - its origins and descendants.
        
        Returns:
            Dict with "ancestors" (working memories), "related" (souvenirs),
            and "descendants" (later souvenirs that reference this one)
        """
        if not self.db_pool:
            return {"ancestors": [], "related": [], "descendants": []}
        
        # Get ancestors (working memories this was compressed from)
        ancestor_query = """
        SELECT wm.* FROM working_memories wm
        JOIN cross_graph_links cgl ON wm.id = cgl.working_memory_id
        WHERE cgl.souvenir_memory_id = $1 AND cgl.link_type = 'compressed_from'
        """
        
        # Get related souvenirs
        related_query = """
        SELECT sr.* FROM souvenir_relations sr2
        JOIN souvenir_memories sr ON 
            (sr2.source_id = $1 AND sr2.target_id = sr.id) OR
            (sr2.target_id = $1 AND sr2.source_id = sr.id)
        WHERE sr.id != $1
        """
        
        async with self.db_pool.acquire() as conn:
            ancestors = await conn.fetch(ancestor_query, souvenir_id)
            related = await conn.fetch(related_query, souvenir_id)
            
            return {
                "ancestors": [dict(row) for row in ancestors],
                "related": [dict(row) for row in related],
                "descendants": []  # Would need recursive query for true descendants
            }
    
    async def get_archiving_candidates(
        self,
        min_age_days: int = 30,
        min_importance: float = 0.0
    ) -> List[SouvenirMemory]:
        """
        Get souvenirs eligible for cold storage archiving.
        
        Args:
            min_age_days: Minimum age to be considered for archiving
            min_importance: Importance floor (higher = keep hot)
            
        Returns:
            List of SouvenirMemory objects ready to archive
        """
        if not self.db_pool:
            return []
        
        cutoff = datetime.utcnow() - timedelta(days=min_age_days)
        
        query = """
        SELECT * FROM souvenir_memories
        WHERE created_at < $1
        AND importance_score <= $2
        AND id NOT IN (SELECT souvenir_id FROM archived_souvenirs)
        ORDER BY importance_score ASC, created_at ASC
        LIMIT 1000
        """
        
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(query, cutoff, min_importance)
            return [
                SouvenirMemory(
                    id=row["id"],
                    content_hash=row["content_hash"],
                    content=row["content"],
                    category=row["category"],
                    created_at=row["created_at"],
                    source_working_id=row["source_working_id"],
                    importance_score=row["importance_score"],
                    compression_ratio=row["compression_ratio"],
                    metadata=json.loads(row["metadata"]) if row["metadata"] else {}
                )
                for row in rows
            ]


# Singleton instance for application-wide access
_souvenir_manager: Optional[SouvenirManager] = None


def get_souvenir_manager(db_pool=None, config: Optional[Dict] = None) -> SouvenirManager:
    """Get or create the singleton SouvenirManager instance."""
    global _souvenir_manager
    if _souvenir_manager is None:
        _souvenir_manager = SouvenirManager(db_pool=db_pool, config=config)
    return _souvenir_manager


# Export public API
__all__ = [
    "SouvenirManager",
    "SouvenirMemory",
    "CrossGraphLink",
    "CompressionJob",
    "MemoryTier",
    "CompressionStatus",
    "get_souvenir_manager"
]
