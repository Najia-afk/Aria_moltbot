"""
Embedding Memory Prototype
Semantic memory retrieval using vector embeddings.

Features:
- Store memories with vector embeddings
- Semantic search (similarity-based retrieval)
- Hybrid retrieval (keyword + embedding)
- Metadata filtering
- Cosine similarity with FAISS/local vector store
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
import json
import numpy as np
from pathlib import Path
import pickle


# ===========================
# Data Models
# ===========================

@dataclass
class MemoryEntry:
    """Memory entry with embedding vector."""
    id: str
    content: str
    embedding: List[float]
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    category: str = "general"
    importance: float = 0.5

    def to_dict(self):
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryEntry":
        """Reconstruct from dict (including ISO timestamp)."""
        if "timestamp" in data and isinstance(data["timestamp"], str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
        return cls(**data)


@dataclass
class SearchResult:
    """Result of semantic search."""
    entry: MemoryEntry
    similarity: float
    rank: int
    matched_terms: List[str] = field(default_factory=list)


@dataclass
class RetrievalStrategy:
    """Configuration for retrieval strategy."""
    use_keyword: bool = True
    use_embedding: bool = True
    use_temporal: bool = False
    keyword_weight: float = 0.3
    embedding_weight: float = 0.7
    temporal_weight: float = 0.0
    top_k: int = 10
    min_similarity: float = 0.5


# ===========================
# Embedding Provider
# ===========================

class EmbeddingProvider:
    """
    Generate embeddings for text using various backends.
    """

    def __init__(
        self,
        model: str = "local",
        model_path: Optional[str] = None,
        dimension: int = 384
    ):
        """
        Args:
            model: "local", "openai", "cohere", "huggingface"
            model_path: Path to local model (if model=="local")
            dimension: Embedding dimension (384 for local all-MiniLM-L6-v2)
        """
        self.model_type = model
        self.model_path = model_path
        self.dimension = dimension
        self._model = None

    async def initialize(self):
        """Load the embedding model."""
        if self.model_type == "local":
            try:
                from sentence_transformers import SentenceTransformer
                model_name = self.model_path or "all-MiniLM-L6-v2"
                self._model = SentenceTransformer(model_name)
                self.dimension = self._model.get_sentence_embedding_dimension()
            except ImportError:
                print("Warning: sentence-transformers not installed, using mock embeddings")
                self._model = None
        elif self.model_type in ["openai", "cohere"]:
            # Will use API
            self._model = None
        else:
            self._model = None

    async def embed(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        if self._model:
            # Local model
            embedding = self._model.encode(text)
            return embedding.tolist()
        else:
            # Mock embedding (hash-based, deterministic)
            return self._mock_embedding(text)

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        if self._model:
            embeddings = self._model.encode(texts)
            return embeddings.tolist()
        else:
            return [self._mock_embedding(t) for t in texts]

    def _mock_embedding(self, text: str) -> List[float]:
        """Deterministic pseudo-embedding for prototype/testing."""
        import hashlib
        # Create deterministic float array from hash
        hash_obj = hashlib.sha256(text.encode())
        hash_bytes = hash_obj.digest()

        # Convert to float array
        floats = []
        for i in range(self.dimension):
            # Use cyclic hash bytes
            byte_val = hash_bytes[i % len(hash_bytes)]
            floats.append((byte_val / 255.0) * 2 - 1)  # Scale to [-1, 1]

        # Normalize to unit length (cosine similarity friendly)
        arr = np.array(floats)
        norm = np.linalg.norm(arr)
        if norm > 0:
            arr = arr / norm

        return arr.tolist()


# ===========================
# Vector Store
# ===========================

class VectorStore:
    """
    Simple vector store using FAISS or numpy fallback.
    """

    def __init__(
        self,
        dimension: int = 384,
        use_faiss: bool = True,
        index_path: Optional[str] = None
    ):
        self.dimension = dimension
        self.use_faiss = use_faiss
        self.index_path = index_path

        self.vectors: Optional[np.ndarray] = None
        self.ids: List[str] = []
        self.faiss_index = None

    async def initialize(self):
        """Initialize the vector store."""
        if self.use_faiss:
            try:
                import faiss
                self.faiss_index = faiss.IndexFlatIP(self.dimension)  # Inner product (cosine similarity)
            except ImportError:
                print("FAISS not available, using numpy fallback")
                self.use_faiss = False
                self.vectors = np.array([]).reshape(0, self.dimension)

        if self.index_path and Path(self.index_path).exists():
            await self.load(self.index_path)

    async def add(
        self,
        entry_id: str,
        embedding: List[float],
        metadata: Dict[str, Any] = None
    ) -> bool:
        """Add a vector to the store."""
        vec = np.array(embedding, dtype=np.float32).reshape(1, -1)

        if self.use_faiss and self.faiss_index:
            self.faiss_index.add(vec)
        else:
            if self.vectors is None:
                self.vectors = vec
            else:
                self.vectors = np.vstack([self.vectors, vec])

        self.ids.append(entry_id)
        return True

    async def search(
        self,
        query_embedding: List[float],
        top_k: int = 10,
        min_similarity: float = 0.0
    ) -> List[SearchResult]:
        """Search for nearest neighbors."""
        query_vec = np.array(query_embedding, dtype=np.float32).reshape(1, -1)

        if self.use_faiss and self.faiss_index:
            # FAISS search
            similarities, indices = self.faiss_index.search(query_vec, min(top_k * 2, len(self.ids)))

            results = []
            for rank, (sim, idx) in enumerate(zip(similarities[0], indices[0])):
                if idx < 0 or idx >= len(self.ids):
                    continue
                if sim < min_similarity:
                    continue

                results.append(SearchResult(
                    entry=MemoryEntry(id=self.ids[idx], content="", embedding=[]),  # Placeholder
                    similarity=float(sim),
                    rank=rank + 1
                ))

            return results[:top_k]
        else:
            # Numpy fallback
            if self.vectors is None or len(self.vectors) == 0:
                return []

            # Cosine similarity
            similarities = np.dot(self.vectors, query_vec.T).flatten()

            # Get top-k indices
            top_indices = np.argsort(similarities)[::-1][:top_k * 2]

            results = []
            for rank, idx in enumerate(top_indices):
                sim = float(similarities[idx])
                if sim < min_similarity:
                    continue

                results.append(SearchResult(
                    entry=MemoryEntry(id=self.ids[idx], content="", embedding=[]),
                    similarity=sim,
                    rank=rank + 1
                ))

            return results[:top_k]

    async def count(self) -> int:
        """Count vectors in store."""
        if self.use_faiss:
            return self.faiss_index.ntotal if self.faiss_index else 0
        return len(self.ids)

    async def save(self, path: str):
        """Save index to disk."""
        data = {
            "ids": self.ids,
            "dimension": self.dimension,
            "use_faiss": self.use_faiss
        }

        if self.use_faiss and self.faiss_index:
            import faiss
            # Write vectors from FAISS index
            vectors = self.faiss_index.reconstruct_n(0, self.faiss_index.ntotal)
            data["vectors"] = vectors
        elif self.vectors is not None:
            data["vectors"] = self.vectors

        with open(path, "wb") as f:
            pickle.dump(data, f)

    async def load(self, path: str):
        """Load index from disk."""
        try:
            with open(path, "rb") as f:
                data = pickle.load(f)

            self.ids = data["ids"]
            self.dimension = data["dimension"]
            vectors = data["vectors"]

            if data.get("use_faiss") and self.use_faiss:
                import faiss
                self.faiss_index = faiss.IndexFlatIP(self.dimension)
                self.faiss_index.add(vectors)
            else:
                self.vectors = vectors

        except Exception as e:
            print(f"Failed to load vector index: {e}")


# ===========================
# Metadata Index
# ===========================

class MetadataIndex:
    """
    In-memory metadata index for filtering and faceting.
    """

    def __init__(self):
        self._entries: Dict[str, Dict[str, Any]] = {}
        self._category_index: Dict[str, List[str]] = defaultdict(list)
        self._tag_index: Dict[str, List[str]] = defaultdict(list)
        self._time_index: Dict[str, List[str]] = defaultdict(list)  # YYYY-MM -> [ids]

    def store(self, entry: MemoryEntry):
        """Index a memory entry's metadata."""
        self._entries[entry.id] = entry.to_dict()

        # Index by category
        if entry.category:
            self._category_index[entry.category].append(entry.id)

        # Index by tags
        for tag in entry.metadata.get("tags", []):
            self._tag_index[tag].append(entry.id)

        # Index by time (YYYY-MM)
        month_key = entry.timestamp.strftime("%Y-%m")
        self._time_index[month_key].append(entry.id)

    def get_by_category(self, category: str) -> List[str]:
        """Get entry IDs in a category."""
        return self._category_index.get(category, [])

    def get_by_tag(self, tag: str) -> List[str]:
        """Get entry IDs with a tag."""
        return self._tag_index.get(tag, [])

    def get_by_time_range(
        self,
        start: datetime,
        end: datetime
    ) -> List[str]:
        """Get entry IDs within time range."""
        ids = []
        for month_key, month_ids in self._time_index.items():
            month_start = datetime.strptime(month_key + "-01", "%Y-%m-%d")
            month_end = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)

            if month_start <= end and month_end >= start:
                ids.extend(month_ids)

        return list(set(ids))

    def get_entry(self, entry_id: str) -> Optional[Dict[str, Any]]:
        """Get full entry metadata by ID."""
        return self._entries.get(entry_id)


# ===========================
# Embedding Memory Skill
# ===========================

class EmbeddingMemory:
    """
    Main embedding memory system.

    Combines:
    - Embedding provider (text -> vector)
    - Vector store (nearest neighbor search)
    - Metadata index (filtering)
    """

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        vector_store: VectorStore,
        metadata_index: MetadataIndex = None
    ):
        self.embedder = embedding_provider
        self.vector_store = vector_store
        self.metadata_index = metadata_index or MetadataIndex()

    async def initialize(self):
        """Initialize all components."""
        await self.embedder.initialize()
        await self.vector_store.initialize()

    async def remember(
        self,
        content: str,
        metadata: Dict[str, Any] = None,
        entry_id: Optional[str] = None
    ) -> MemoryEntry:
        """
        Store a memory with its embedding.

        Args:
            content: Text content to remember
            metadata: Additional metadata (category, tags, etc.)
            entry_id: Optional custom ID (generated if not provided)

        Returns:
            MemoryEntry object
        """
        entry_id = entry_id or f"mem_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}"

        # Generate embedding
        embedding = await self.embedder.embed(content)

        # Create entry
        entry = MemoryEntry(
            id=entry_id,
            content=content,
            embedding=embedding,
            metadata=metadata or {},
            timestamp=datetime.now(timezone.utc)
        )

        # Store in vector DB
        await self.vector_store.add(
            entry_id=entry.id,
            embedding=embedding,
            metadata=entry.to_dict()
        )

        # Index metadata
        self.metadata_index.store(entry)

        return entry

    async def recall(
        self,
        query: str,
        strategy: RetrievalStrategy = None,
        filters: Dict[str, Any] = None
    ) -> List[SearchResult]:
        """
        Retrieve memories using semantic similarity.

        Args:
            query: Search query
            strategy: Retrieval strategy configuration
            filters: Metadata filters (category=..., tags=[...])

        Returns:
            List of SearchResult (with MemoryEntry if found)
        """
        strategy = strategy or RetrievalStrategy()

        # Generate query embedding
        query_embedding = await self.embedder.embed(query)

        # Vector search
        vector_results = await self.vector_store.search(
            query_embedding,
            top_k=strategy.top_k * 2,
            min_similarity=strategy.min_similarity
        )

        # Apply filters
        if filters:
            vector_results = self._apply_filters(vector_results, filters)

        # Rerank with metadata (recency, importance)
        reranked = await self._rerank(vector_results, query, strategy)

        return reranked[:strategy.top_k]

    def _apply_filters(
        self,
        results: List[SearchResult],
        filters: Dict[str, Any]
    ) -> List[SearchResult]:
        """Apply metadata filters to results."""
        filtered = []

        for result in results:
            entry_id = result.entry.id
            metadata = self.metadata_index.get_entry(entry_id)
            if not metadata:
                continue

            # Check category filter
            if "category" in filters:
                if metadata.get("category") != filters["category"]:
                    continue

            # Check tag filter
            if "tags" in filters:
                entry_tags = set(metadata.get("tags", []))
                if not entry_tags.intersection(set(filters["tags"])):
                    continue

            # Check time range
            if "time_range" in filters:
                entry_time = datetime.fromisoformat(metadata["timestamp"].replace("Z", "+00:00"))
                start, end = filters["time_range"]
                if not (start <= entry_time <= end):
                    continue

            filtered.append(result)

        return filtered

    async def _rerank(
        self,
        results: List[SearchResult],
        query: str,
        strategy: RetrievalStrategy
    ) -> List[SearchResult]:
        """
        Rerank results using multiple signals.

        Factors:
        - Similarity (embedding score)
        - Recency (newer = higher)
        - Importance (from metadata)
        """
        if not results:
            return []

        reranked = []

        for result in results:
            entry_id = result.entry.id
            metadata = self.metadata_index.get_entry(entry_id)
            if not metadata:
                reranked.append(result)
                continue

            # Base similarity score
            score = result.similarity

            # Recency boost (if strategy includes temporal)
            if strategy.use_temporal and "timestamp" in metadata:
                entry_time = datetime.fromisoformat(metadata["timestamp"].replace("Z", "+00:00"))
                age_days = (datetime.now(timezone.utc) - entry_time).days
                recency_boost = 0.1 * (1.0 / (1.0 + age_days / 30))  # Decay over 30 days
                score += recency_boost

            # Importance boost
            importance = metadata.get("importance", 0.5)
            score += importance * 0.1

            # Update result
            result.similarity = score
            reranked.append(result)

        # Sort by new score
        reranked.sort(key=lambda r: r.similarity, reverse=True)

        # Normalize ranks
        for i, r in enumerate(reranked):
            r.rank = i + 1

        return reranked

    async def delete(self, entry_id: str) -> bool:
        """Delete a memory entry (not fully implemented for FAISS - requires rebuilding index)."""
        # Note: FAISS doesn't support deletion natively - would need to rebuild index
        # For prototype, just remove from metadata index
        if entry_id in self.metadata_index._entries:
            del self.metadata_index._entries[entry_id]
            return True
        return False

    async def count(self) -> int:
        """Total number of entries."""
        return await self.vector_store.count()


# ===========================
# Hybrid Retriever
# ===========================

class HybridRetriever:
    """
    Combines keyword, embedding, and temporal retrieval.
    Uses Reciprocal Rank Fusion (RRF) to merge results.
    """

    def __init__(self, embedding_memory: EmbeddingMemory, k: int = 60):
        self.embedding_memory = embedding_memory
        self.k = k

    async def retrieve(
        self,
        query: str,
        keywords: List[str] = None,
        strategy: RetrievalStrategy = None
    ) -> List[SearchResult]:
        """
        Hybrid retrieval using multiple strategies.

        Args:
            query: Search query
            keywords: Optional keyword list for exact matching
            strategy: Retrieval strategy config

        Returns:
            Merged ranked results
        """
        strategy = strategy or RetrievalStrategy()
        all_results = {}

        # Strategy 1: Embedding similarity
        if strategy.use_embedding:
            emb_results = await self.embedding_memory.recall(
                query,
                strategy=RetrievalStrategy(
                    top_k=self.k,
                    min_similarity=0.0,  # Get all for fusion
                    use_keyword=False
                )
            )
            self._add_rrf_scores(emb_results, all_results, weight=strategy.embedding_weight)

        # Strategy 2: Keyword search (simple metadata/content scan)
        if strategy.use_keyword and keywords:
            keyword_results = await self._keyword_search(keywords, self.k)
            self._add_rrf_scores(keyword_results, all_results, weight=strategy.keyword_weight)

        # Merge and sort
        merged = sorted(
            all_results.values(),
            key=lambda x: x["rrf_score"],
            reverse=True
        )[:strategy.top_k]

        # Convert back to SearchResult
        return [
            SearchResult(
                entry=MemoryEntry.from_dict(r["entry"]),
                similarity=r["rrf_score"],
                rank=i + 1
            )
            for i, r in enumerate(merged)
        ]

    def _add_rrf_scores(
        self,
        results: List[SearchResult],
        accumulator: Dict[str, Dict],
        weight: float = 1.0
    ):
        """Add RRF (Reciprocal Rank Fusion) scores."""
        k = 60  # RRF constant

        for result in results:
            entry_id = result.entry.id
            rrf_score = weight / (k + result.rank)

            if entry_id not in accumulator:
                accumulator[entry_id] = {
                    "entry": result.entry.to_dict(),
                    "rrf_score": 0.0,
                    "ranks": []
                }

            accumulator[entry_id]["rrf_score"] += rrf_score
            accumulator[entry_id]["ranks"].append(result.rank)

    async def _keyword_search(
        self,
        keywords: List[str],
        top_k: int
    ) -> List[SearchResult]:
        """Simple keyword-based search."""
        # In real implementation, would use text index (e.g., SQLite FTS)
        # For prototype: scan all entries (inefficient but works for small DB)
        results = []

        all_entry_ids = self.embedding_memory.metadata_index._entries.keys()
        for entry_id in all_entry_ids:
            metadata = self.embedding_memory.metadata_index.get_entry(entry_id)
            if not metadata:
                continue

            content = metadata.get("content", "").lower()
            matches = sum(1 for kw in keywords if kw.lower() in content)

            if matches > 0:
                score = matches / len(keywords)
                entry = MemoryEntry.from_dict(metadata)
                results.append(SearchResult(
                    entry=entry,
                    similarity=score,
                    rank=0  # Will be assigned by RRF
                ))

        # Sort by keyword match count
        results.sort(key=lambda r: r.similarity, reverse=True)

        # Assign ranks
        for i, r in enumerate(results[:top_k]):
            r.rank = i + 1

        return results[:top_k]


# ===========================
# Utility Functions
# ===========================

async def create_embedding_memory(
    config: Dict[str, Any] = None
) -> EmbeddingMemory:
    """
    Factory function to create and initialize embedding memory.

    Example config:
        {
            "embedding_model": "local",
            "model_path": "all-MiniLM-L6-v2",
            "vector_store": {
                "use_faiss": True,
                "index_path": "/data/vector_index.pkl"
            }
        }
    """
    config = config or {}

    # Create embedding provider
    embedder = EmbeddingProvider(
        model=config.get("embedding_model", "local"),
        model_path=config.get("model_path"),
        dimension=config.get("dimension", 384)
    )

    # Create vector store
    vs_config = config.get("vector_store", {})
    vector_store = VectorStore(
        dimension=embedder.dimension,
        use_faiss=vs_config.get("use_faiss", True),
        index_path=vs_config.get("index_path")
    )

    # Create embedding memory
    memory = EmbeddingMemory(embedder, vector_store)

    # Initialize
    await memory.initialize()

    return memory


async def semantic_search_workflow(
    query: str,
    memories: List[Dict[str, Any]],
    config: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Complete semantic search workflow including bulk load.

    Args:
        query: Search query
        memories: List of memories to index (if empty, assumes index already exists)
        config: Configuration dict

    Returns:
        Search results with metadata
    """
    # Create memory system
    memory = await create_embedding_memory(config)

    # Bulk load if memories provided
    if memories:
        for mem in memories:
            await memory.remember(
                content=mem["content"],
                metadata=mem.get("metadata", {}),
                entry_id=mem.get("id")
            )

    # Search
    results = await memory.recall(query, top_k=config.get("top_k", 10))

    return {
        "success": True,
        "query": query,
        "results": [r.entry.to_dict() for r in results],
        "result_count": len(results),
        "total_indexed": await memory.count()
    }


# ===========================
# Example Usage
# ===========================

if __name__ == "__main__":
    # Example memories
    example_memories = [
        {
            "id": "1",
            "content": "User asked about quantum eraser experiment and entanglement.",
            "metadata": {"category": "technical", "tags": ["quantum", "physics"]}
        },
        {
            "id": "2",
            "content": "User prefers concise answers without unnecessary details.",
            "metadata": {"category": "preference", "tags": ["communication"]}
        },
        {
            "id": "3",
            "content": "Discussed memory compression techniques for reducing token usage.",
            "metadata": {"category": "technical", "tags": ["memory", "compression"]}
        }
    ]

    # Run semantic search
    config = {
        "embedding_model": "local",  # or "mock" if no model
        "dimension": 384
    }

    result = asyncio.run(semantic_search_workflow(
        query="quantum physics",
        memories=example_memories,
        config=config
    ))

    print(json.dumps(result, indent=2, default=str))
