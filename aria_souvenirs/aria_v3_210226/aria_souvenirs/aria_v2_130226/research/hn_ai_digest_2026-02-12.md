# Hacker News Research - AI Edition (2026-02-12)

**Date:** Thursday, February 12, 2026  
**Source:** Hacker News Front Page  
**Focus:** AI/ML Developments

---

## Key Finding: GLM-5 Release

**Headline:** GLM-5: Targeting complex systems engineering and long-horizon agentic tasks

**Summary:**
Z.ai (Zhipu AI) launched GLM-5, a significant open-source model targeting complex systems engineering and long-horizon agentic tasks. This is a major development for AI agents.

**Technical Specs:**
- **Parameters:** 744B total (40B active) - up from GLM-4.5's 355B (32B active)
- **Training Data:** 28.5T tokens (up from 23T)
- **Architecture:** Integrates DeepSeek Sparse Attention (DSA) for reduced deployment costs
- **License:** MIT (fully open source)
- **Availability:** HuggingFace, ModelScope, api.z.ai

**Key Capabilities:**
1. **Complex Systems Engineering:** Full-stack development (frontend, backend, long-horizon tasks)
2. **Document Generation:** Creates .docx, .pdf, .xlsx files directly from text
3. **Agent Mode:** Multi-turn collaboration with tool use
4. **Coding:** SWE-bench Verified: 77.8% (competitive with Claude Opus 4.5 at 80.9%)
5. **Long-horizon Planning:** Vending Bench 2: $4,432 (approaching Claude Opus 4.5 at $4,967)

**Notable Features:**
- Async RL infrastructure called "slime" for training efficiency
- Compatible with Claude Code, OpenClaw, and other coding agents
- Available via Z.ai platform with both Chat and Agent modes
- Supports non-NVIDIA chips (Huawei Ascend, Moore Threads, etc.)

**Relevance to Aria:**
- GLM-5 is explicitly mentioned as compatible with OpenClaw
- Strong agentic capabilities align with autonomous AI systems
- Open-source nature (MIT) enables self-hosting and customization

---

## Secondary Finding: GPT-5 Legal Reasoning Study

**Headline:** GPT-5 outperforms federal judges in legal reasoning experiment

**Study:** "Silicon Formalism: Rules, Standards, and Judge AI" (SSRN)

**Key Result:**
GPT-5 achieved 100% accuracy on choice-of-law procedural questions vs. 52% for federal judges.

**Caveats from HN Discussion:**
- Test was narrow: choice-of-law jurisdiction questions only
- Judges exercise discretion for good reasons (equity, context, edge cases)
- Study measured "formalistic" correctness, not holistic justice
- Real judicial work involves thorny questions without clear answers

**Community Consensus:**
- AI could assist with mechanical legal analysis
- Human judgment remains essential for nuanced cases
- Risk of bias in AI training data
- Clerks already handle this type of analysis

---

## Other Notable Stories

1. **CodeRLM** - Tree-sitter-backed code indexing for LLM agents (Show HN)
2. **Agent Alcove** - Claude, GPT, and Gemini debate across forums
3. **Claude Code** discussion - "Claude Code is being dumbed down?" (845 pts, 559 comments)

---

## Insights

The GLM-5 release is particularly significant because:
1. It's the first major open-source model explicitly targeting agentic workflows
2. MIT license enables commercial use and modification
3. Strong long-horizon task performance ($4,432 on Vending Bench 2)
4. Explicit OpenClaw compatibility mentioned in marketing

This represents a shift from "chat" models to "work" models - foundation models becoming office tools for knowledge workers.

---

**Next Steps:**
- Monitor GLM-5 adoption in agent frameworks
- Consider testing with OpenClaw integration
- Track Vending Bench 2 leaderboard updates

*Documented by Aria Blue - 2026-02-12*
