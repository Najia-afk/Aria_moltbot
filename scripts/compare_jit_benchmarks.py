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
        marker = "+" if speedup > 1.05 else "=" if speedup > 0.95 else "-"
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
