# Research: Atomic Information Flow for Tool Attribution

**Source:** arXiv:2602.04912 [cs.IR]  
**Title:** Atomic Information Flow: A Network Flow Model for Tool Attributions in RAG Systems  
**Authors:** James Gao, Josh Zhou, Qi Sun, Ryan Huang, Steven Yoo  
**Date:** February 4, 2026

## Key Concepts

### Atomic Information Flow (AIF)
- Graph-based network flow model that decomposes tool outputs and LLM calls into **atoms**
- **Atoms:** Indivisible, self-contained units of information
- Models LLM orchestration as directed flow of atoms from tool/LLM nodes to response super-sink

### Relevance to Skill Pathfinding
1. **Tool Attribution:** Enables tracing responses back to specific tool components
2. **Flow-Based Routing:** Uses max-flow min-cut theorem for optimal information routing
3. **Context Compression:** Lightweight model (Gemma3 4B) trained to approximate minimum cut

## Performance Results
- Base Gemma3-4B: 54.7% accuracy (HotpotQA)
- Post-training with AIF signals: **82.71%** (+28.01 points)
- Context token compression: **87.52%**
- Comparable to Gemma3-27B (7x larger model)

## Applications for aria_skills
- Semantic routing for skill selection
- Attribution tracking for multi-agent orchestration
- Efficient context compression for skill context windows

## Next Steps
- [ ] Study max-flow min-cut applications for skill routing
- [ ] Investigate atom-based decomposition for skill interfaces
- [ ] Evaluate context compression for skill catalogs

---
*Research logged: 2026-02-14*
