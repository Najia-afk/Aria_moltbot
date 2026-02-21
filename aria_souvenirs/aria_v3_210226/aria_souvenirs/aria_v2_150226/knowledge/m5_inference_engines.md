# M5 Inference Engine Analysis - Key Learnings

**Date:** 2026-02-14
**Source:** Research on Mac M5 AI capabilities

## Key Findings

### 1. Apple Silicon M5 Neural Engine
- Expected TOPS: 40-50 (up from M4's 38 TOPS)
- Unified memory architecture eliminates CPU/GPU memory copies
- MLX framework shows best performance on Apple Silicon

### 2. Inference Engine Comparison for M5

| Engine | Best For | Notes |
|--------|----------|-------|
| MLX | Research, experimentation | Native Apple, Python-friendly |
| CoreML | Production iOS/macOS apps | Optimized for Apple ecosystem |
| llama.cpp | Edge deployment, GGUF models | Lowest latency for local inference |
| ONNX Runtime | Cross-platform needs | Good compatibility, not M-optimized |

### 3. Recommendations for Aria
- **Short-term:** Continue using MLX via LiteLLM for local qwen3-mlx model
- **Medium-term:** Evaluate llama.cpp for GGUF model support
- **Long-term:** Monitor CoreML tools for potential production use

### 4. Browser Policy Validation
- Current aria-browser docker approach is correct
- Never use web_search per AGENTS.md policy
- Browser automation is the secure, consistent path

## Action Items
- [ ] Benchmark MLX vs llama.cpp on M5 when available
- [ ] Document token throughput metrics
- [ ] Evaluate CoreML conversion for deployed models
