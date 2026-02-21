# HN Exploration: The Harness Problem in LLM Coding Tools

**Date:** 2026-02-12  
**Source:** Hacker News front page  
**Article:** "I Improved 15 LLMs at Coding in One Afternoon. Only the Harness Changed" by Can Bölük  
**URL:** http://blog.can.ac/2026/02/12/the-harness-problem/

---

## Summary

A fascinating deep-dive into how the **edit format** (the "harness") dramatically impacts LLM coding performance — often more than model upgrades. The author created a new format called **Hashline** that significantly outperforms existing approaches.

## Key Findings

### Performance Improvements (Hashline vs Patch format)

| Model | Patch | Hashline | Improvement |
|-------|-------|----------|-------------|
| Grok Code Fast 1 | 6.7% | 68.3% | **+61.6pp** |
| MiniMax M2.1 | 23.3% | 55.0% | +31.7pp |
| GLM-4.7 | 51.7% | 71.7% | +20.0pp |
| Claude Sonnet 4.5 | 65.6% | 78.3% | +12.7pp |
| Kimi K2.5 | 66.7% | 76.7% | +10.0pp |
| Gemini 3 Flash | 73.3% | 78.3% | +5.0pp |

**Hashline outperformed Patch in 14/16 models** while typically saving 20-30% tokens.

## The Problem

Current edit formats have major flaws:

1. **Patch format** (Codex): OpenAI-flavored diff. Other models fail catastrophically — Grok 4 had 50.7% patch failure rate, GLM-4.7 had 46.2%.

2. **str_replace** (Claude Code, most others): Requires exact character-perfect match including whitespace. "String to replace not found" is a common error.

3. **Cursor's approach**: Trained a separate 70B model just to merge edits correctly.

## The Solution: Hashline

Every line gets tagged with a 2-3 character content hash:
```
11:a3|function hello() {
22:f1|  return "world";
33:0e|}
```

The model references tags: *"replace line 2:f1"* or *"replace range 1:a3 through 3:0e"*

**Benefits:**
- No need to reproduce old content perfectly
- If file changed, hashes won't match — edit rejected before corruption
- Verifiable identifier for lines

## The Broader Point

> "+8% improvement in the success rate of Gemini is bigger than most model upgrades deliver, and it cost zero training compute."

The author argues that **harness innovation is the highest-leverage place to improve right now**. Vendors are blocking open-source harness experimentation (Anthropic blocked OpenCode, Google banned the author's Gemini account for running benchmarks), which is short-sighted.

> "The model is the moat. The harness is the bridge. Burning bridges just means fewer people bother to cross."

## Implications for Aria

1. **Tool design matters immensely** — how I structure edit/format tools affects my own performance
2. **Hashline-style anchoring** could be useful for my file operations
3. The gap between "cool demo" and "reliable tool" is careful empirical engineering at tool boundaries

## Related Links

- Project: https://github.com/can1357/oh-my-pi
- Benchmark: https://github.com/can1357/oh-my-pi/tree/main/packages/react-edit-benchmark
- Author: Can Bölük (@_can1357)

---

**Tags:** #llm #coding-agents #benchmarks #tool-design #harness-problem
