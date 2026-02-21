# RML (Retrieval-Augmented Machine Learning) Research Findings

**Date:** 2026-02-13  
**Goal:** Research RML Documentation for Skill Pathfinding  
**Progress Update:** Literature search completed, key papers identified

## Key Papers Identified from arXiv Search

### 1. Atomic Information Flow (AIF) - arXiv:2602.04912
- **Title:** Atomic Information Flow: A Network Flow Model for Tool Attributions in RAG Systems
- **Authors:** James Gao, Josh Zhou, Qi Sun, Ryan Huang, Steven Yoo
- **Relevance:** HIGH - Graph-based network flow model for tracing RAG responses to tool components
- **Key Insight:** Addresses critical gap in multi-agent RAG systems - precise attribution mechanisms
- **Application:** Could inform skill routing attribution in aria_skills pathfinding

### 2. ContextBench - arXiv:2602.05892
- **Title:** ContextBench: A Benchmark for Context Retrieval in Coding Agents
- **Authors:** Han Li et al.
- **Relevance:** MEDIUM - Process-oriented evaluation of context retrieval
- **Key Insight:** Focuses on HOW agents retrieve and use context, not just success rates
- **Application:** Benchmarking approach for skill selection evaluation

### 3. Neurosymbolic Retrievers - arXiv:2601.04568
- **Title:** Neurosymbolic Retrievers for Retrieval-augmented Generation
- **Authors:** Yash Saxena, Manas Gaur
- **Relevance:** HIGH - Combines neural and symbolic approaches
- **Key Insight:** Hybrid retrieval methods for better tool selection
- **Application:** Could inspire hybrid skill routing (vector + symbolic)

### 4. Quantifying Document Impact - arXiv:2601.05260
- **Title:** Quantifying Document Impact in RAG-LLMs
- **Authors:** Armin Gerami et al.
- **Relevance:** MEDIUM - Measuring retrieval contribution
- **Key Insight:** Methods for quantifying which retrieved docs matter most
- **Application:** Skill impact scoring in pathfinding

## Research Directions for Aria Skill Pathfinding

### Vector-Based Skill Retrieval
- Embedding strategies for skill descriptions
- Similarity search for tool-to-task matching
- HNSW/graph-based approximate nearest neighbor (ANN) search

### Semantic Routing Algorithms
- Multi-hop reasoning for complex skill chains
- Graph traversal on skill dependency graphs
- Dynamic routing based on context windows

### Embedding Strategies
- Task embedding vs skill embedding alignment
- Cross-modal embeddings (text → tool parameters)
- Fine-tuning embeddings on successful skill invocations

### Benchmark Comparisons
- ContextBench approach for evaluating skill selection
- Success rate vs retrieval quality metrics
- Energy/efficiency trade-offs in RAG systems (arXiv:2601.02522)

## Next Steps
1. Fetch and read full AIF paper for implementation details
2. Investigate vector DB options for skill embeddings
3. Design skill dependency graph schema
4. Prototype semantic skill router

## Integration with aria_skills Catalog
- Current: Skills defined in skill.json with manual routing
- Future: Vector-indexed skills with semantic search
- Catalog layer could maintain embedding index
- API client could expose skill retrieval endpoint
