# S12-02: Memory Profiling (24h Soak Test)
**Epic:** E8 — Quality & Testing | **Priority:** P1 | **Points:** 3 | **Phase:** 12

## Problem
Aria Blue runs 24/7 on a Mac Mini with limited RAM (24GB shared with PostgreSQL, Ollama, and Grafana). Memory leaks that don't appear in short tests can crash the system after hours of operation. We need a memory profiling suite that detects leaks during a sustained soak test, identifies the top allocators, and sets hard limits.

## Root Cause
Python's garbage collector handles most memory management, but async generators, cached LLM responses, session state accumulation, and pheromone score histories can all leak. `tracemalloc` catches Python-level leaks; `memray` catches C-extension leaks. We need both.

## Fix
### `tests/profiling/memory_profile.py`
```python
"""
Memory profiling suite for Aria Blue.

Runs a simulated 24-hour soak test (compressed to configurable duration)
and monitors memory growth. Uses tracemalloc for Python allocations
and reports top memory consumers.

Usage:
    python tests/profiling/memory_profile.py --duration 3600  # 1 hour
    python tests/profiling/memory_profile.py --duration 86400  # 24 hours
    python tests/profiling/memory_profile.py --quick           # 5 min smoke test
"""
import argparse
import asyncio
import gc
import json
import linecache
import os
import sys
import time
import tracemalloc
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class ProfileConfig:
    """Memory profiling configuration."""
    duration_seconds: int = 3600       # Total test duration
    sample_interval: int = 60          # Seconds between memory samples
    leak_threshold_mb: float = 50.0    # Max allowed growth over test
    max_rss_mb: float = 512.0          # Absolute RSS limit
    top_n_allocations: int = 20        # Show top N allocations
    output_dir: Path = field(default_factory=lambda: Path("tests/profiling/results"))
    enable_tracemalloc: bool = True
    gc_collect_between_samples: bool = True


@dataclass
class MemorySample:
    """A single memory measurement."""
    timestamp: str
    elapsed_seconds: float
    rss_mb: float
    vms_mb: float
    tracemalloc_current_mb: float
    tracemalloc_peak_mb: float
    gc_objects: int
    gc_collections: dict[str, int]


# ---------------------------------------------------------------------------
# Memory monitoring
# ---------------------------------------------------------------------------

class MemoryProfiler:
    """Profiles memory usage over time."""

    def __init__(self, config: ProfileConfig):
        self.config = config
        self.samples: list[MemorySample] = []
        self.start_time: float = 0.0
        self._tracemalloc_started = False

    def start(self) -> None:
        """Start profiling."""
        self.start_time = time.monotonic()

        if self.config.enable_tracemalloc:
            tracemalloc.start(25)  # 25 frames deep
            self._tracemalloc_started = True

        # Ensure output directory exists
        self.config.output_dir.mkdir(parents=True, exist_ok=True)

    def stop(self) -> None:
        """Stop profiling."""
        if self._tracemalloc_started:
            tracemalloc.stop()
            self._tracemalloc_started = False

    def sample(self) -> MemorySample:
        """Take a memory sample."""
        import resource

        # RSS from resource module (Unix) or psutil
        try:
            import psutil
            proc = psutil.Process()
            mem = proc.memory_info()
            rss_mb = mem.rss / (1024 * 1024)
            vms_mb = mem.vms / (1024 * 1024)
        except ImportError:
            # Fallback to resource module
            rusage = resource.getrusage(resource.RUSAGE_SELF)
            rss_mb = rusage.ru_maxrss / 1024  # KB to MB on Linux
            vms_mb = 0.0

        # Tracemalloc stats
        if self._tracemalloc_started:
            current, peak = tracemalloc.get_traced_memory()
            tm_current_mb = current / (1024 * 1024)
            tm_peak_mb = peak / (1024 * 1024)
        else:
            tm_current_mb = 0.0
            tm_peak_mb = 0.0

        # GC stats
        gc_stats = gc.get_stats()
        gc_collections = {
            f"gen{i}": stats["collections"] for i, stats in enumerate(gc_stats)
        }

        sample = MemorySample(
            timestamp=datetime.now(timezone.utc).isoformat(),
            elapsed_seconds=time.monotonic() - self.start_time,
            rss_mb=rss_mb,
            vms_mb=vms_mb,
            tracemalloc_current_mb=tm_current_mb,
            tracemalloc_peak_mb=tm_peak_mb,
            gc_objects=len(gc.get_objects()),
            gc_collections=gc_collections,
        )
        self.samples.append(sample)
        return sample

    def get_top_allocations(self) -> list[dict]:
        """Get top memory allocations from tracemalloc."""
        if not self._tracemalloc_started:
            return []

        snapshot = tracemalloc.take_snapshot()
        # Filter out tracemalloc internals
        snapshot = snapshot.filter_traces([
            tracemalloc.Filter(False, "<frozen importlib._bootstrap>"),
            tracemalloc.Filter(False, "<frozen importlib._bootstrap_external>"),
            tracemalloc.Filter(False, tracemalloc.__file__),
        ])

        top_stats = snapshot.statistics("lineno")

        allocations = []
        for stat in top_stats[:self.config.top_n_allocations]:
            frame = stat.traceback[0]
            allocations.append({
                "file": frame.filename,
                "line": frame.lineno,
                "size_mb": stat.size / (1024 * 1024),
                "count": stat.count,
                "source": linecache.getline(frame.filename, frame.lineno).strip(),
            })

        return allocations

    def detect_leak(self) -> dict:
        """Analyze samples for memory growth pattern."""
        if len(self.samples) < 5:
            return {"leak_detected": False, "reason": "Not enough samples"}

        # Compare first 10% and last 10% of samples
        n = len(self.samples)
        early = self.samples[:max(n // 10, 1)]
        late = self.samples[-max(n // 10, 1):]

        early_avg = sum(s.rss_mb for s in early) / len(early)
        late_avg = sum(s.rss_mb for s in late) / len(late)

        growth_mb = late_avg - early_avg
        growth_pct = (growth_mb / early_avg * 100) if early_avg > 0 else 0

        # Linear regression for trend
        xs = [s.elapsed_seconds for s in self.samples]
        ys = [s.rss_mb for s in self.samples]
        n_samples = len(xs)
        x_mean = sum(xs) / n_samples
        y_mean = sum(ys) / n_samples
        slope = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / max(
            sum((x - x_mean) ** 2 for x in xs), 1e-10
        )
        # MB per hour
        growth_rate_mb_per_hour = slope * 3600

        leak_detected = growth_mb > self.config.leak_threshold_mb

        return {
            "leak_detected": leak_detected,
            "growth_mb": round(growth_mb, 2),
            "growth_pct": round(growth_pct, 2),
            "growth_rate_mb_per_hour": round(growth_rate_mb_per_hour, 2),
            "early_avg_mb": round(early_avg, 2),
            "late_avg_mb": round(late_avg, 2),
            "threshold_mb": self.config.leak_threshold_mb,
            "samples_analyzed": n_samples,
        }

    def generate_report(self) -> dict:
        """Generate full profiling report."""
        leak_analysis = self.detect_leak()
        top_allocs = self.get_top_allocations()

        report = {
            "test_info": {
                "start": self.samples[0].timestamp if self.samples else None,
                "end": self.samples[-1].timestamp if self.samples else None,
                "duration_seconds": self.samples[-1].elapsed_seconds if self.samples else 0,
                "sample_count": len(self.samples),
            },
            "memory_summary": {
                "min_rss_mb": round(min(s.rss_mb for s in self.samples), 2) if self.samples else 0,
                "max_rss_mb": round(max(s.rss_mb for s in self.samples), 2) if self.samples else 0,
                "avg_rss_mb": round(
                    sum(s.rss_mb for s in self.samples) / len(self.samples), 2
                ) if self.samples else 0,
                "peak_tracemalloc_mb": round(
                    max(s.tracemalloc_peak_mb for s in self.samples), 2
                ) if self.samples else 0,
            },
            "leak_analysis": leak_analysis,
            "top_allocations": top_allocs,
            "samples": [
                {
                    "elapsed_s": round(s.elapsed_seconds),
                    "rss_mb": round(s.rss_mb, 2),
                    "tm_current_mb": round(s.tracemalloc_current_mb, 2),
                    "gc_objects": s.gc_objects,
                }
                for s in self.samples
            ],
        }

        return report

    def save_report(self) -> Path:
        """Save report to JSON file."""
        report = self.generate_report()
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        report_path = self.config.output_dir / f"memory_profile_{timestamp}.json"
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return report_path


# ---------------------------------------------------------------------------
# Soak test workload
# ---------------------------------------------------------------------------

async def simulate_workload(profiler: MemoryProfiler, config: ProfileConfig) -> None:
    """Simulate realistic workload for soak testing."""
    from aria_engine.chat_engine import ChatEngine
    from aria_engine.llm_gateway import LLMGateway
    from aria_engine.session_manager import NativeSessionManager
    from aria_engine.scheduler import EngineScheduler

    # Initialize components
    gateway = LLMGateway()
    sessions = NativeSessionManager()
    chat = ChatEngine(gateway=gateway, sessions=sessions)

    profiler.start()
    start = time.monotonic()
    last_sample = start
    cycle = 0

    print(f"Starting soak test: {config.duration_seconds}s duration")
    print(f"Sample interval: {config.sample_interval}s")
    print()

    try:
        while (time.monotonic() - start) < config.duration_seconds:
            cycle += 1

            # Simulate chat session lifecycle
            session_id = f"soak-{cycle}"
            await sessions.create(session_id, title=f"Soak Test {cycle}")

            # Send a few messages
            for i in range(3):
                await chat.process(
                    session_id=session_id,
                    content=f"Soak test message {cycle}-{i}",
                )

            # Close some sessions (not all — simulate real usage)
            if cycle % 3 == 0:
                await sessions.delete(session_id)

            # Periodic memory sample
            if (time.monotonic() - last_sample) >= config.sample_interval:
                if config.gc_collect_between_samples:
                    gc.collect()

                sample = profiler.sample()
                elapsed = sample.elapsed_seconds
                print(
                    f"  [{elapsed:>7.0f}s] RSS: {sample.rss_mb:.1f}MB | "
                    f"TM: {sample.tracemalloc_current_mb:.1f}MB | "
                    f"GC objects: {sample.gc_objects:,}"
                )

                # Check RSS limit
                if sample.rss_mb > config.max_rss_mb:
                    print(f"\n  ABORT: RSS ({sample.rss_mb:.1f}MB) exceeds limit ({config.max_rss_mb}MB)")
                    break

                last_sample = time.monotonic()

            # Small delay to prevent CPU saturation
            await asyncio.sleep(0.1)

    finally:
        profiler.stop()


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Aria Blue Memory Profiler")
    parser.add_argument("--duration", type=int, default=3600, help="Test duration in seconds")
    parser.add_argument("--interval", type=int, default=60, help="Sample interval in seconds")
    parser.add_argument("--threshold", type=float, default=50.0, help="Leak threshold in MB")
    parser.add_argument("--max-rss", type=float, default=512.0, help="Max RSS in MB")
    parser.add_argument("--quick", action="store_true", help="Quick 5-minute test")
    parser.add_argument("--output", type=str, default="tests/profiling/results", help="Output directory")
    args = parser.parse_args()

    if args.quick:
        args.duration = 300
        args.interval = 15

    config = ProfileConfig(
        duration_seconds=args.duration,
        sample_interval=args.interval,
        leak_threshold_mb=args.threshold,
        max_rss_mb=args.max_rss,
        output_dir=Path(args.output),
    )

    profiler = MemoryProfiler(config)

    print("=" * 60)
    print("  ARIA BLUE MEMORY PROFILER")
    print(f"  Duration: {config.duration_seconds}s")
    print(f"  Leak threshold: {config.leak_threshold_mb}MB")
    print(f"  Max RSS: {config.max_rss_mb}MB")
    print("=" * 60)
    print()

    asyncio.run(simulate_workload(profiler, config))

    # Generate and save report
    report_path = profiler.save_report()
    report = profiler.generate_report()

    print()
    print("=" * 60)
    print("  RESULTS")
    print("=" * 60)
    print(f"  RSS: {report['memory_summary']['min_rss_mb']:.1f} → {report['memory_summary']['max_rss_mb']:.1f} MB")
    print(f"  Growth: {report['leak_analysis']['growth_mb']:.1f} MB ({report['leak_analysis']['growth_pct']:.1f}%)")
    print(f"  Rate: {report['leak_analysis']['growth_rate_mb_per_hour']:.1f} MB/hour")
    print(f"  Leak detected: {report['leak_analysis']['leak_detected']}")
    print(f"  Report: {report_path}")
    print()

    if report["top_allocations"]:
        print("  Top allocations:")
        for alloc in report["top_allocations"][:10]:
            print(f"    {alloc['size_mb']:.2f}MB - {alloc['file']}:{alloc['line']} - {alloc['source'][:60]}")
        print()

    # Exit with failure if leak detected
    if report["leak_analysis"]["leak_detected"]:
        print("  FAIL: Memory leak detected!")
        sys.exit(1)
    else:
        print("  PASS: No memory leak detected")
        sys.exit(0)


if __name__ == "__main__":
    main()
```

### `tests/profiling/run_memray.sh`
```bash
#!/bin/bash
# Run memray profiling for Aria Blue
# Captures C-level allocations that tracemalloc misses

DURATION="${1:-300}"  # seconds
OUTPUT_DIR="tests/profiling/results"
mkdir -p "$OUTPUT_DIR"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
MEMRAY_FILE="$OUTPUT_DIR/memray_${TIMESTAMP}.bin"

echo "=== Aria Blue Memray Profile ==="
echo "Duration: ${DURATION}s"
echo "Output: $MEMRAY_FILE"
echo ""

# Run with memray
python -m memray run --output "$MEMRAY_FILE" \
    tests/profiling/memory_profile.py --duration "$DURATION" --interval 30

# Generate reports
echo ""
echo "Generating reports..."
python -m memray stats "$MEMRAY_FILE" > "$OUTPUT_DIR/memray_stats_${TIMESTAMP}.txt"
python -m memray flamegraph "$MEMRAY_FILE" --output "$OUTPUT_DIR/memray_flamegraph_${TIMESTAMP}.html"
python -m memray table "$MEMRAY_FILE" --output "$OUTPUT_DIR/memray_table_${TIMESTAMP}.html"

echo ""
echo "Reports generated:"
echo "  Stats: $OUTPUT_DIR/memray_stats_${TIMESTAMP}.txt"
echo "  Flamegraph: $OUTPUT_DIR/memray_flamegraph_${TIMESTAMP}.html"
echo "  Table: $OUTPUT_DIR/memray_table_${TIMESTAMP}.html"
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer architecture | ✅ | Profiles the full stack |
| 2 | .env for secrets | ✅ | DATABASE_URL |
| 3 | models.yaml single source | ❌ | No model switching |
| 4 | Docker-first testing | ✅ | Profile inside container |
| 5 | aria_memories only writable path | ❌ | Profile output in tests/ |
| 6 | No soul modification | ❌ | No soul access |

## Dependencies
- `pip install psutil memray`
- Working aria_engine stack
- PostgreSQL for session persistence

## Verification
```bash
# 1. Quick smoke test (5 minutes):
python tests/profiling/memory_profile.py --quick

# 2. Full 1-hour soak test:
python tests/profiling/memory_profile.py --duration 3600

# 3. Memray profile (catches C-level leaks):
bash tests/profiling/run_memray.sh 300

# 4. Check report:
cat tests/profiling/results/memory_profile_*.json | python -m json.tool

# 5. Verify no leak:
# EXPECTED: "leak_detected": false, growth < 50MB
```

## Prompt for Agent
```
Create a memory profiling and soak test suite.

FILES TO READ FIRST:
- tests/profiling/memory_profile.py (this ticket's output)
- aria_engine/chat_engine.py (main memory consumer)
- aria_engine/session_manager.py (session state accumulation)
- aria_engine/agent_pool.py (pheromone history)

STEPS:
1. Create tests/profiling/memory_profile.py
2. Create tests/profiling/run_memray.sh
3. Run quick 5-minute test locally
4. Analyze report — look for growth rate > 10MB/hour
5. If leak found: trace to specific allocation

CONSTRAINTS:
- Use tracemalloc (Python) + memray (C-level)
- Detect leaks via linear regression of RSS over time
- Threshold: <50MB growth over test duration
- Max RSS: 512MB absolute limit
- Output: JSON report + memray flamegraph
```
