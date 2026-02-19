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
        # RSS from psutil or fallback
        try:
            import psutil
            proc = psutil.Process()
            mem = proc.memory_info()
            rss_mb = mem.rss / (1024 * 1024)
            vms_mb = mem.vms / (1024 * 1024)
        except ImportError:
            try:
                import resource
                rusage = resource.getrusage(resource.RUSAGE_SELF)
                rss_mb = rusage.ru_maxrss / 1024  # KB to MB on Linux
                vms_mb = 0.0
            except ImportError:
                # Windows fallback without psutil
                rss_mb = 0.0
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
    profiler.start()
    start = time.monotonic()
    last_sample = start
    cycle = 0

    print(f"Starting soak test: {config.duration_seconds}s duration")
    print(f"Sample interval: {config.sample_interval}s")
    print()

    # Simulated in-memory state to test for leaks
    sessions: dict[str, list[str]] = {}

    try:
        while (time.monotonic() - start) < config.duration_seconds:
            cycle += 1

            # Simulate session lifecycle — accumulate state
            session_id = f"soak-{cycle}"
            sessions[session_id] = []

            # Simulate adding messages to session
            for i in range(3):
                sessions[session_id].append(
                    f"Message {cycle}-{i}: {'x' * random.randint(100, 1000)}"
                )

            # Close some sessions (not all — simulate real usage)
            if cycle % 3 == 0 and session_id in sessions:
                del sessions[session_id]

            # Periodic memory sample
            if (time.monotonic() - last_sample) >= config.sample_interval:
                if config.gc_collect_between_samples:
                    gc.collect()

                sample = profiler.sample()
                elapsed = sample.elapsed_seconds
                print(
                    f"  [{elapsed:>7.0f}s] RSS: {sample.rss_mb:.1f}MB | "
                    f"TM: {sample.tracemalloc_current_mb:.1f}MB | "
                    f"GC objects: {sample.gc_objects:,} | "
                    f"Sessions: {len(sessions)}"
                )

                # Check RSS limit
                if sample.rss_mb > config.max_rss_mb:
                    print(f"\n  ABORT: RSS ({sample.rss_mb:.1f}MB) exceeds limit ({config.max_rss_mb}MB)")
                    break

                last_sample = time.monotonic()

            # Small delay to prevent CPU saturation
            await asyncio.sleep(0.01)

    finally:
        profiler.stop()


# We need random for the workload simulation
import random


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
    print(f"  RSS: {report['memory_summary']['min_rss_mb']:.1f} -> {report['memory_summary']['max_rss_mb']:.1f} MB")
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
