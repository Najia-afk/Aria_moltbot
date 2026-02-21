# S9-05: Python 3.13 JIT Flags + Benchmarks
**Epic:** E7 — Python 3.13+ Modernization | **Priority:** P2 | **Points:** 2 | **Phase:** 9

## Problem
Python 3.13 introduces an experimental JIT compiler (`PYTHON_JIT=1`). We need to benchmark Aria's key operations — LLM calls, DB queries, context assembly, skill routing — with and without JIT to determine if it provides measurable benefit. If so, we enable it in the Docker entrypoint.

## Root Cause
No performance benchmarking suite exists for Aria. The JIT flag was never tested because we previously targeted Python 3.12. With 3.13+ as our minimum, we should evaluate every available optimization and establish a performance baseline.

## Fix
### `tests/benchmarks/benchmark_engine.py`
```python
"""
Aria Engine performance benchmarks.

Measures key operations with and without Python 3.13 JIT.
Run with:
    PYTHON_JIT=0 python tests/benchmarks/benchmark_engine.py  # baseline
    PYTHON_JIT=1 python tests/benchmarks/benchmark_engine.py  # JIT enabled

Results are written to docs/benchmarks.md
"""
import asyncio
import json
import os
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Determine JIT status
JIT_ENABLED = os.environ.get("PYTHON_JIT", "0") == "1"
ITERATIONS = 100
WARMUP = 10


@dataclass
class BenchmarkResult:
    """Result of a single benchmark."""
    name: str
    iterations: int
    mean_ms: float
    median_ms: float
    p95_ms: float
    p99_ms: float
    min_ms: float
    max_ms: float
    std_ms: float
    jit_enabled: bool = JIT_ENABLED

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "iterations": self.iterations,
            "mean_ms": round(self.mean_ms, 3),
            "median_ms": round(self.median_ms, 3),
            "p95_ms": round(self.p95_ms, 3),
            "p99_ms": round(self.p99_ms, 3),
            "min_ms": round(self.min_ms, 3),
            "max_ms": round(self.max_ms, 3),
            "std_ms": round(self.std_ms, 3),
            "jit": self.jit_enabled,
        }


def benchmark(func, iterations: int = ITERATIONS, warmup: int = WARMUP) -> BenchmarkResult:
    """Run a synchronous benchmark function."""
    # Warmup
    for _ in range(warmup):
        func()

    # Measure
    times_ms: list[float] = []
    for _ in range(iterations):
        start = time.perf_counter_ns()
        func()
        elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000
        times_ms.append(elapsed_ms)

    times_ms.sort()
    p95_idx = int(len(times_ms) * 0.95)
    p99_idx = int(len(times_ms) * 0.99)

    return BenchmarkResult(
        name=func.__name__,
        iterations=iterations,
        mean_ms=statistics.mean(times_ms),
        median_ms=statistics.median(times_ms),
        p95_ms=times_ms[p95_idx],
        p99_ms=times_ms[p99_idx],
        min_ms=times_ms[0],
        max_ms=times_ms[-1],
        std_ms=statistics.stdev(times_ms) if len(times_ms) > 1 else 0,
    )


async def async_benchmark(
    func,
    iterations: int = ITERATIONS,
    warmup: int = WARMUP,
) -> BenchmarkResult:
    """Run an async benchmark function."""
    # Warmup
    for _ in range(warmup):
        await func()

    # Measure
    times_ms: list[float] = []
    for _ in range(iterations):
        start = time.perf_counter_ns()
        await func()
        elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000
        times_ms.append(elapsed_ms)

    times_ms.sort()
    p95_idx = int(len(times_ms) * 0.95)
    p99_idx = int(len(times_ms) * 0.99)

    return BenchmarkResult(
        name=func.__name__,
        iterations=iterations,
        mean_ms=statistics.mean(times_ms),
        median_ms=statistics.median(times_ms),
        p95_ms=times_ms[p95_idx],
        p99_ms=times_ms[p99_idx],
        min_ms=times_ms[0],
        max_ms=times_ms[-1],
        std_ms=statistics.stdev(times_ms) if len(times_ms) > 1 else 0,
    )


# ============================================================================
# Benchmark Functions
# ============================================================================

def bench_model_resolution():
    """Benchmark model name resolution from models.yaml."""
    from aria_models.loader import load_models_config, normalize_model_id
    config = load_models_config()
    normalize_model_id("step-35-flash-free")


def bench_toml_parsing():
    """Benchmark pyproject.toml parsing with stdlib tomllib."""
    import tomllib
    with open("pyproject.toml", "rb") as f:
        tomllib.load(f)


def bench_yaml_parsing():
    """Benchmark models.yaml parsing."""
    import yaml
    with open("aria_models/models.yaml") as f:
        yaml.safe_load(f)


def bench_context_assembly():
    """Benchmark context window assembly (simulated)."""
    # Simulate assembling 50 messages into context
    messages: list[dict[str, str]] = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"Message {i} " * 50}
        for i in range(50)
    ]
    # Simulate sliding window
    window = messages[-30:]
    # Simulate token counting (approximate)
    total_tokens = sum(len(m["content"].split()) for m in window)
    _ = total_tokens


def bench_pheromone_scoring():
    """Benchmark pheromone score calculation."""
    import math
    # Simulate scoring 6 agents
    agents = [
        {"success_rate": 0.85, "latency_avg": 1200, "task_count": 50},
        {"success_rate": 0.92, "latency_avg": 800, "task_count": 120},
        {"success_rate": 0.78, "latency_avg": 2000, "task_count": 30},
        {"success_rate": 0.95, "latency_avg": 600, "task_count": 200},
        {"success_rate": 0.60, "latency_avg": 3000, "task_count": 10},
        {"success_rate": 0.88, "latency_avg": 1000, "task_count": 80},
    ]
    for agent in agents:
        score = (
            agent["success_rate"] * 0.4
            + (1 - min(agent["latency_avg"] / 5000, 1.0)) * 0.3
            + min(math.log(agent["task_count"] + 1) / 6, 1.0) * 0.3
        )
        _ = round(score, 3)


def bench_json_serialization():
    """Benchmark JSON serialization of chat messages."""
    messages = [
        {
            "id": f"msg-{i}",
            "role": "assistant",
            "content": "This is a response " * 100,
            "thinking": "Let me think about this " * 50,
            "tool_calls": [{"name": "search", "args": {"query": "test"}}] if i % 3 == 0 else None,
            "tokens_input": 500,
            "tokens_output": 300,
            "cost": 0.001,
        }
        for i in range(50)
    ]
    json.dumps(messages)


async def bench_async_context_switch():
    """Benchmark asyncio context switching overhead."""
    async def noop():
        pass
    await noop()


async def bench_semaphore_acquire():
    """Benchmark semaphore acquire/release (agent pool concurrency)."""
    sem = asyncio.Semaphore(5)
    async with sem:
        pass


# ============================================================================
# Report Generation
# ============================================================================

def generate_report(results: list[BenchmarkResult]) -> str:
    """Generate markdown benchmark report."""
    jit_status = "Enabled" if JIT_ENABLED else "Disabled"
    python_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    lines = [
        f"# Aria Engine Benchmarks",
        f"",
        f"**Python:** {python_ver}  ",
        f"**JIT:** {jit_status}  ",
        f"**Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}  ",
        f"**Iterations:** {ITERATIONS}  ",
        f"",
        f"## Results",
        f"",
        f"| Benchmark | Mean (ms) | Median (ms) | P95 (ms) | P99 (ms) | Std (ms) |",
        f"|-----------|-----------|-------------|----------|----------|----------|",
    ]

    for r in results:
        lines.append(
            f"| {r.name} | {r.mean_ms:.3f} | {r.median_ms:.3f} | "
            f"{r.p95_ms:.3f} | {r.p99_ms:.3f} | {r.std_ms:.3f} |"
        )

    lines.extend([
        "",
        "## Notes",
        "",
        f"- JIT ({jit_status}): Set via `PYTHON_JIT={'1' if JIT_ENABLED else '0'}`",
        "- All times in milliseconds",
        "- Warmup iterations excluded from measurement",
        "- Run both JIT=0 and JIT=1 and compare results",
    ])

    return "\n".join(lines)


async def main() -> int:
    print(f"Python {sys.version}")
    print(f"JIT: {'ENABLED' if JIT_ENABLED else 'DISABLED'}")
    print(f"Iterations: {ITERATIONS}")
    print()

    results: list[BenchmarkResult] = []

    # Synchronous benchmarks
    sync_benches = [
        bench_toml_parsing,
        bench_yaml_parsing,
        bench_context_assembly,
        bench_pheromone_scoring,
        bench_json_serialization,
    ]

    # Only run model resolution if aria_models is importable
    try:
        from aria_models.loader import load_models_config
        sync_benches.insert(0, bench_model_resolution)
    except ImportError:
        print("SKIP: bench_model_resolution (aria_models not available)")

    for func in sync_benches:
        print(f"Running {func.__name__}... ", end="", flush=True)
        result = benchmark(func)
        results.append(result)
        print(f"{result.mean_ms:.3f}ms (p95: {result.p95_ms:.3f}ms)")

    # Async benchmarks
    async_benches = [
        bench_async_context_switch,
        bench_semaphore_acquire,
    ]

    for func in async_benches:
        print(f"Running {func.__name__}... ", end="", flush=True)
        result = await async_benchmark(func)
        results.append(result)
        print(f"{result.mean_ms:.3f}ms (p95: {result.p95_ms:.3f}ms)")

    # Generate report
    report = generate_report(results)
    report_path = Path("docs/benchmarks.md")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    print(f"\nReport written to {report_path}")

    # Also write JSON for programmatic comparison
    json_path = Path("docs/benchmarks.json")
    json_data = {
        "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "jit": JIT_ENABLED,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "results": [r.to_dict() for r in results],
    }
    json_path.write_text(json.dumps(json_data, indent=2), encoding="utf-8")
    print(f"JSON data written to {json_path}")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
```

### `scripts/compare_jit_benchmarks.py`
```python
"""
Compare JIT=0 vs JIT=1 benchmark results.

Usage:
    PYTHON_JIT=0 python tests/benchmarks/benchmark_engine.py
    cp docs/benchmarks.json docs/benchmarks_nojit.json
    PYTHON_JIT=1 python tests/benchmarks/benchmark_engine.py
    cp docs/benchmarks.json docs/benchmarks_jit.json
    python scripts/compare_jit_benchmarks.py
"""
import json
import sys
from pathlib import Path


def main() -> int:
    nojit_path = Path("docs/benchmarks_nojit.json")
    jit_path = Path("docs/benchmarks_jit.json")

    if not nojit_path.exists() or not jit_path.exists():
        print("ERROR: Run benchmarks with JIT=0 and JIT=1 first.")
        print("  PYTHON_JIT=0 python tests/benchmarks/benchmark_engine.py")
        print("  cp docs/benchmarks.json docs/benchmarks_nojit.json")
        print("  PYTHON_JIT=1 python tests/benchmarks/benchmark_engine.py")
        print("  cp docs/benchmarks.json docs/benchmarks_jit.json")
        return 1

    nojit = json.loads(nojit_path.read_text())
    jit = json.loads(jit_path.read_text())

    nojit_by_name = {r["name"]: r for r in nojit["results"]}
    jit_by_name = {r["name"]: r for r in jit["results"]}

    print(f"{'Benchmark':<35} {'No-JIT (ms)':>12} {'JIT (ms)':>10} {'Speedup':>10}")
    print("-" * 70)

    improvements: list[float] = []
    for name, nj in nojit_by_name.items():
        j = jit_by_name.get(name)
        if not j:
            continue
        speedup = nj["mean_ms"] / j["mean_ms"] if j["mean_ms"] > 0 else 0
        improvements.append(speedup)
        marker = "✓" if speedup > 1.05 else "≈" if speedup > 0.95 else "✗"
        print(
            f"{name:<35} {nj['mean_ms']:>10.3f}ms {j['mean_ms']:>8.3f}ms {speedup:>8.2f}x {marker}"
        )

    avg_speedup = sum(improvements) / len(improvements) if improvements else 0
    print()
    print(f"Average speedup: {avg_speedup:.2f}x")
    recommend = avg_speedup > 1.05
    print(f"Recommendation: {'ENABLE JIT in Docker' if recommend else 'JIT not beneficial enough'}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

### Dockerfile addition (conditional, after benchmarks):
```dockerfile
# If benchmarks show JIT is beneficial, add to Docker entrypoint:
# ENV PYTHON_JIT=1

# In aria_engine entrypoint (aria_engine/entrypoint.py), check:
# import os
# if os.environ.get("PYTHON_JIT") == "1":
#     logger.info("Python JIT compiler enabled")
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ❌ | Benchmarking utility |
| 2 | .env for secrets (zero in code) | ❌ | PYTHON_JIT is not a secret |
| 3 | models.yaml single source of truth | ✅ | Model resolution benchmark uses models.yaml |
| 4 | Docker-first testing | ✅ | Benchmarks must run in Docker (python:3.13-slim) |
| 5 | aria_memories only writable path | ❌ | Writes to docs/ only |
| 6 | No soul modification | ❌ | No soul access |

## Dependencies
- S9-01 must complete first (Python 3.13+ confirmed)
- S1-01 must complete first (aria_engine package exists)

## Verification
```bash
# 1. Run benchmarks without JIT:
PYTHON_JIT=0 python tests/benchmarks/benchmark_engine.py
cp docs/benchmarks.json docs/benchmarks_nojit.json
# EXPECTED: Report generated at docs/benchmarks.md

# 2. Run benchmarks with JIT:
PYTHON_JIT=1 python tests/benchmarks/benchmark_engine.py
cp docs/benchmarks.json docs/benchmarks_jit.json
# EXPECTED: Report generated at docs/benchmarks.md

# 3. Compare results:
python scripts/compare_jit_benchmarks.py
# EXPECTED: Table comparing JIT vs no-JIT with speedup ratios

# 4. Profile hot paths:
py-spy record -o docs/profile.svg -- python tests/benchmarks/benchmark_engine.py
# EXPECTED: Flame graph SVG at docs/profile.svg

# 5. Verify benchmark report exists:
test -f docs/benchmarks.md && echo "OK" || echo "FAIL"
# EXPECTED: OK
```

## Prompt for Agent
```
Create Python 3.13 JIT benchmarks for Aria Engine operations.

FILES TO READ FIRST:
- Dockerfile (line 2 — python:3.13-slim base image)
- aria_engine/llm_gateway.py (LLM call hot path)
- aria_engine/chat_engine.py (context assembly hot path)
- aria_engine/agent_pool.py (agent scheduling hot path)
- aria_agents/scoring.py (pheromone calculation)
- aria_models/loader.py (model resolution)

STEPS:
1. Create tests/benchmarks/benchmark_engine.py with all benchmark functions
2. Create scripts/compare_jit_benchmarks.py for comparison
3. Run benchmarks with PYTHON_JIT=0 and PYTHON_JIT=1
4. Generate docs/benchmarks.md report
5. If JIT shows >5% improvement, add PYTHON_JIT=1 to Dockerfile
6. Run py-spy profiling for flame graph

CONSTRAINTS:
- Benchmarks must be deterministic (no external service calls in sync benchmarks)
- Async benchmarks use asyncio.run() — not pytest
- Each benchmark runs WARMUP=10, ITERATIONS=100
- Report format: markdown + JSON for programmatic comparison
- Do NOT add PYTHON_JIT=1 to Dockerfile unless benchmarks show improvement
```
