#!/usr/bin/env python3
# verification/benchmarks/benchmark_personal_agent_beta.py
"""Personal Agent Beta v0.1 End-to-End Benchmark Suite.

Measures latency and throughput across:
- E2E agent orchestration loop latency
- Personal Vault context retrieval latency
- Personal Vault storage operation latency
- Capability dispatch & execution latency (GitHub capability target)
- Experience recording latency
- Run state resume / continuation latency
- Success and failure rates

Saves results to verification/benchmarks/personal_agent_beta_v01_report.json.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

# Force mock planner provider for local deterministic benchmark execution
os.environ["AGENTCORE_PLANNER_PROVIDER"] = "mock"

_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from core.agent import Agent, AgentRunResult
from core.capabilities.github import GitHubCapabilityAdapter
from core.capabilities.schema import CapabilityResult
from core.evaluation.benchmark import Benchmark, BenchmarkReport, BenchmarkResult
from core.vault.adapter import PersonalVaultAdapter


def benchmark_e2e_run(agent: Agent, iterations: int = 10) -> tuple[BenchmarkResult, float, float]:
    """Measure full E2E Agent run pipeline latency and success/failure rate."""
    success_count = 0
    fail_count = 0

    # Warmup run
    agent.run(
        "Benchmark E2E warmup",
        capability_dispatch=(
            "github_integration",
            {"action": "get_repo", "owner": "hgblue09124", "repo": "agent-core"},
        ),
    )

    t0 = time.time()
    times = []
    for _ in range(iterations):
        t_iter_0 = time.time()
        res: AgentRunResult = agent.run(
            "Benchmark E2E request",
            capability_dispatch=(
                "github_integration",
                {"action": "get_repo", "owner": "hgblue09124", "repo": "agent-core"},
            ),
        )
        t_elapsed = time.time() - t_iter_0
        times.append(t_elapsed)

        if res.success:
            success_count += 1
        else:
            fail_count += 1

    avg_sec = sum(times) / len(times) if times else 0.0
    min_sec = min(times) if times else 0.0
    max_sec = max(times) if times else 0.0
    ops_per_sec = (1.0 / avg_sec) if avg_sec > 0 else 0.0

    bm_res = BenchmarkResult(
        name="personal_agent_e2e_run",
        iterations=iterations,
        total_seconds=sum(times),
        avg_seconds=avg_sec,
        min_seconds=min_sec,
        max_seconds=max_sec,
        ops_per_second=ops_per_sec,
    )

    tot = iterations
    success_rate = (success_count / tot) * 100.0 if tot > 0 else 0.0
    failure_rate = (fail_count / tot) * 100.0 if tot > 0 else 0.0
    return bm_res, success_rate, failure_rate


def benchmark_vault_operations(iterations: int = 20) -> BenchmarkResult:
    """Measure Personal Vault store and context retrieval latency."""
    vault = PersonalVaultAdapter()

    def fn():
        vault.store_context("bench_pref", {"editor": "neovim"}, category="user_pref")
        ctxs = vault.retrieve_context("neovim")
        assert len(ctxs) > 0

    bm = Benchmark()
    return bm.run("vault_operations", fn, iterations=iterations, warmup=2)


def benchmark_context_retrieval(agent: Agent, iterations: int = 20) -> BenchmarkResult:
    """Measure personal context retrieval latency (Vault + Memory query)."""
    vault = agent._vault
    vault.store_context("context_search_item", {"info": "retrieval_benchmark_data"}, category="bench")

    def fn():
        ctxs = vault.retrieve_context("retrieval_benchmark_data")
        assert len(ctxs) > 0

    bm = Benchmark()
    return bm.run("context_retrieval", fn, iterations=iterations, warmup=2)


def benchmark_capability_dispatch(agent: Agent, iterations: int = 20) -> BenchmarkResult:
    """Measure capability authorization and dispatch latency."""
    def fn():
        res: CapabilityResult = agent.execute_capability(
            "github_integration",
            {"action": "get_repo", "owner": "hgblue09124", "repo": "agent-core"},
        )
        assert res.success

    bm = Benchmark()
    return bm.run("capability_dispatch_execution", fn, iterations=iterations, warmup=2)


def benchmark_experience_recording(agent: Agent, iterations: int = 15) -> BenchmarkResult:
    """Measure experience engine recording latency."""
    from core.experience.schema import Experience

    def fn():
        rid = f"BENCH-{int(time.time()*1000)%100000:05d}"
        exp = Experience(
            run_id=rid,
            goal="Benchmark experience goal",
            project_id="default",
            outcome="success",
        )
        rec = agent._experience_engine.record_experience(exp)
        assert rec is not None

    bm = Benchmark()
    return bm.run("experience_recording", fn, iterations=iterations, warmup=1)


def benchmark_run_resume(agent: Agent, iterations: int = 10) -> BenchmarkResult:
    """Measure run checkpoint loading and resume latency."""
    res = agent.run("Run for resume benchmark")

    def fn():
        resumed = agent.resume(res.run_id)
        assert resumed.success

    bm = Benchmark()
    return bm.run("run_resume_continuity", fn, iterations=iterations, warmup=1)


def main():
    print("==========================================================")
    print("  PERSONAL AGENT BETA v0.1 END-TO-END BENCHMARK SUITE")
    print("==========================================================")
    t_start = time.time()

    report = BenchmarkReport()
    report.timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    agent = Agent(project_id="default")

    print("\n[1/6] Benchmarking E2E Agent Run Pipeline...")
    bm_e2e, success_rate, failure_rate = benchmark_e2e_run(agent, iterations=10)
    report.add(bm_e2e)
    print(f"      Avg: {bm_e2e.avg_seconds*1000:.2f} ms | Ops/s: {bm_e2e.ops_per_second:.1f} | Success: {success_rate:.1f}%")

    print("\n[2/6] Benchmarking Personal Vault Operations...")
    bm_vault = benchmark_vault_operations(iterations=20)
    report.add(bm_vault)
    print(f"      Avg: {bm_vault.avg_seconds*1000:.2f} ms | Ops/s: {bm_vault.ops_per_second:.1f}")

    print("\n[3/6] Benchmarking Personal Context Retrieval...")
    bm_context = benchmark_context_retrieval(agent, iterations=20)
    report.add(bm_context)
    print(f"      Avg: {bm_context.avg_seconds*1000:.2f} ms | Ops/s: {bm_context.ops_per_second:.1f}")

    print("\n[4/6] Benchmarking Capability Dispatch & Execution...")
    bm_cap = benchmark_capability_dispatch(agent, iterations=20)
    report.add(bm_cap)
    print(f"      Avg: {bm_cap.avg_seconds*1000:.2f} ms | Ops/s: {bm_cap.ops_per_second:.1f}")

    print("\n[5/6] Benchmarking Experience Recording...")
    bm_exp = benchmark_experience_recording(agent, iterations=15)
    report.add(bm_exp)
    print(f"      Avg: {bm_exp.avg_seconds*1000:.2f} ms | Ops/s: {bm_exp.ops_per_second:.1f}")

    print("\n[6/6] Benchmarking Run Resume & State Continuity...")
    bm_resume = benchmark_run_resume(agent, iterations=10)
    report.add(bm_resume)
    print(f"      Avg: {bm_resume.avg_seconds*1000:.2f} ms | Ops/s: {bm_resume.ops_per_second:.1f}")

    print("\n==========================================================")
    print(report.summary())
    print("==========================================================")

    total_elapsed = time.time() - t_start
    test_mode = "REAL_EXTERNAL" if os.getenv("GITHUB_TOKEN") else "MOCK/LOCAL"

    artifact_path = Path(_root) / "verification" / "benchmarks" / "personal_agent_beta_v01_report.json"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)

    report_data = {
        "benchmark_id": "personal_agent_beta_v01",
        "description": "Personal Agent Beta v0.1 End-to-End Performance Benchmark",
        "timestamp": report.timestamp,
        "test_mode": test_mode,
        "environment": {
            "platform": sys.platform,
            "python_version": sys.version.split()[0],
            "planner_provider": os.getenv("AGENTCORE_PLANNER_PROVIDER", "mock"),
            "has_github_token": bool(os.getenv("GITHUB_TOKEN")),
        },
        "overall_summary": {
            "total_benchmark_duration_seconds": round(total_elapsed, 3),
            "success_rate_percent": success_rate,
            "failure_rate_percent": failure_rate,
        },
        "metrics": {
            "e2e_latency_avg_ms": round(bm_e2e.avg_seconds * 1000, 2),
            "e2e_latency_min_ms": round(bm_e2e.min_seconds * 1000, 2),
            "e2e_latency_max_ms": round(bm_e2e.max_seconds * 1000, 2),
            "vault_op_latency_avg_ms": round(bm_vault.avg_seconds * 1000, 2),
            "vault_op_latency_min_ms": round(bm_vault.min_seconds * 1000, 2),
            "vault_op_latency_max_ms": round(bm_vault.max_seconds * 1000, 2),
            "context_retrieval_latency_avg_ms": round(bm_context.avg_seconds * 1000, 2),
            "capability_dispatch_latency_avg_ms": round(bm_cap.avg_seconds * 1000, 2),
            "experience_recording_latency_avg_ms": round(bm_exp.avg_seconds * 1000, 2),
            "resume_latency_avg_ms": round(bm_resume.avg_seconds * 1000, 2),
        },
        "benchmarks": [r.to_dict() for r in report.results],
    }

    with open(artifact_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)

    print(f"\nPersonal Agent Beta v0.1 Report saved to: {artifact_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
