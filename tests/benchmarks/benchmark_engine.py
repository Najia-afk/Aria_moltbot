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

    # Only run YAML parsing if pyyaml is available
    try:
        import yaml
        sync_benches.insert(1, bench_yaml_parsing)
    except ImportError:
        print("SKIP: bench_yaml_parsing (pyyaml not available)")

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
