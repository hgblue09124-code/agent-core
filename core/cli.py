# core/cli.py
"""Agent-Core Beta v0.1.0-beta CLI Entrypoint.

Commands:
    agent-core run "<goal>" [--project <id>] [--provider <name>]
    agent-core inspect <run_id>
    agent-core history [--limit <N>]
    agent-core benchmark
    agent-core version
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# Ensure root is on path
_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from core.agent import Agent, AgentRunResult


BANNER = """
==========================================================
              AGENT-CORE BETA (v0.1.0-beta)
    Reference Developer Preview & Runtime Inspection
==========================================================
"""


def cmd_version(args) -> int:
    print("Agent-Core v0.1.0-beta (Developer Preview)")
    print("Kernel Version: v1.0")
    print("Constitution Version: 1.0.0")
    return 0


def cmd_run(args) -> int:
    print(BANNER)
    print(f"Project   : {args.project}")
    print(f"Goal      : {args.goal}")
    if args.provider:
        print(f"Provider  : {args.provider}")
    print("-" * 58)

    agent = Agent(project_id=args.project, provider=args.provider)
    res: AgentRunResult = agent.run(goal=args.goal, project_id=args.project)

    print("\n--- Execution Lifecycle ---")
    print(f"  [TASK]         Accepted ({res.project_id})")
    print(f"  [PLAN]         Generated ({len(res.plan_steps)} steps)")
    for step in res.plan_steps[:5]:
        print(f"                 • {step}")
    print(f"  [AUTHORITY]    {'Authorized' if res.authorized else 'REJECTED'}")
    print(f"  [EXECUTION]    Completed via TaskRunner")
    print(f"  [OBSERVATION]  Captured stdout/stderr")
    print(f"  [VERIFICATION] {res.verification_verdict}")
    print(f"  [RESULT]       {res.status} ({res.duration_seconds:.3f}s)")
    print(f"  [EXPERIENCE]   {'Recorded' if res.experience_recorded else 'Not recorded'} (Run ID: {res.run_id})")

    if res.errors:
        print("\n--- Errors ---")
        for err in res.errors:
            print(f"  ✗ {err}")

    print("\n" + "=" * 58)
    return 0 if res.success else 1


def cmd_inspect(args) -> int:
    agent = Agent(project_id="cuu-gioi")
    info = agent.inspect_run(args.run_id)

    if not info:
        print(f"Run ID '{args.run_id}' not found.")
        return 1

    print(BANNER)
    print(f"Run ID     : {info.get('run_id')}")
    print(f"Goal       : {info.get('goal')}")
    print(f"Project    : {info.get('project_id')}")
    print(f"Status     : {info.get('kernel_status')}")
    print(f"Phase      : {info.get('kernel_phase')}")
    print(f"Started    : {info.get('started_at')}")
    print(f"Finished   : {info.get('finished_at')}")
    print(f"LLM Calls  : {info.get('llm_calls')}")
    print(f"Retrieved  : {info.get('knowledge_retrieved')}")

    if info.get("errors"):
        print("\nErrors:")
        for err in info["errors"]:
            print(f"  ✗ {err}")

    print()
    return 0


def cmd_history(args) -> int:
    agent = Agent(project_id="cuu-gioi")
    hist = agent.history()

    if not hist:
        print("No run history found.")
        return 0

    print(BANNER)
    print(f"{'RUN ID':<15} {'STATUS':<12} {'PROJECT':<12} {'GOAL'}")
    print("-" * 65)

    limit = args.limit if args.limit > 0 else len(hist)
    for entry in hist[:limit]:
        print(
            f"{entry['run_id']:<15} {entry['status']:<12} "
            f"{entry['project_id']:<12} {entry['goal'][:25]}"
        )

    print()
    return 0


def cmd_benchmark(args) -> int:
    from verification.benchmarks.benchmark_cuu_gioi import main as run_benchmark
    return run_benchmark()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="agent-core",
        description="Agent-Core Beta v0.1.0-beta CLI",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # run
    p_run = subparsers.add_parser("run", help="Run a task on Agent-Core")
    p_run.add_argument("goal", type=str, help="Task objective/goal")
    p_run.add_argument("--project", "-p", type=str, default="cuu-gioi", help="Project ID")
    p_run.add_argument("--provider", type=str, default=None, help="LLM planner provider (mock | openrouter | openai | local)")
    p_run.set_defaults(func=cmd_run)

    # inspect
    p_inspect = subparsers.add_parser("inspect", help="Inspect a run lifecycle state")
    p_inspect.add_argument("run_id", type=str, help="Run ID to inspect (e.g. KRUN-12345)")
    p_inspect.set_defaults(func=cmd_inspect)

    # history
    p_hist = subparsers.add_parser("history", help="List run history")
    p_hist.add_argument("--limit", "-n", type=int, default=10, help="Max runs to display")
    p_hist.set_defaults(func=cmd_history)

    # benchmark
    p_bench = subparsers.add_parser("benchmark", help="Run Cửu Giới benchmark suite")
    p_bench.set_defaults(func=cmd_benchmark)

    # version
    p_ver = subparsers.add_parser("version", help="Print Agent-Core version metadata")
    p_ver.set_defaults(func=cmd_version)

    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
