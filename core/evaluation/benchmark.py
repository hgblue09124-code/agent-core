# core/evaluation/benchmark.py
"""Benchmarking for the evaluation engine.

Measures:
    - knowledge retrieval latency
    - planning context construction time
    - experience recording overhead
    - evaluation overhead
    - kernel orchestration overhead
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional, Callable, Any


@dataclass
class BenchmarkResult:
    name: str
    iterations: int
    total_seconds: float
    avg_seconds: float
    min_seconds: float
    max_seconds: float
    ops_per_second: float = 0.0
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "iterations": self.iterations,
            "total_seconds": round(self.total_seconds, 6),
            "avg_seconds": round(self.avg_seconds, 6),
            "min_seconds": round(self.min_seconds, 6),
            "max_seconds": round(self.max_seconds, 6),
            "ops_per_second": round(self.ops_per_second, 2),
            "notes": self.notes,
        }


class Benchmark:
    """Simple benchmarking harness."""

    def run(self, name: str, fn: Callable[[], Any],
            iterations: int = 100,
            warmup: int = 2) -> BenchmarkResult:
        """Run a benchmark. Returns BenchmarkResult."""
        # Warmup
        for _ in range(warmup):
            fn()

        times: list[float] = []
        for _ in range(iterations):
            t0 = time.perf_counter()
            fn()
            times.append(time.perf_counter() - t0)

        total = sum(times)
        avg = total / len(times)
        return BenchmarkResult(
            name=name,
            iterations=iterations,
            total_seconds=total,
            avg_seconds=avg,
            min_seconds=min(times),
            max_seconds=max(times),
            ops_per_second=1.0 / avg if avg > 0 else 0.0,
        )


@dataclass
class BenchmarkReport:
    results: list[BenchmarkResult] = field(default_factory=list)
    timestamp: str = ""

    def add(self, result: BenchmarkResult) -> None:
        self.results.append(result)

    def summary(self) -> str:
        lines = [f"Benchmark Report — {len(self.results)} benchmarks"]
        lines.append("-" * 60)
        for r in self.results:
            lines.append(
                f"  {r.name:<40} avg={r.avg_seconds*1000:6.2f}ms  "
                f"ops/s={r.ops_per_second:8.0f}  n={r.iterations}"
            )
        return "\n".join(lines)
