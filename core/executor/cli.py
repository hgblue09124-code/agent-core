#!/usr/bin/env python3
# core/executor/cli.py
"""Executor CLI — run goal through Planner → Task Engine.

Usage:
    python -m core.executor.cli run <project_id> <goal> [--no-execute]
    python -m core.executor.cli run-existing <task_id>
    python -m core.executor.cli --help
"""

import sys
from pathlib import Path

_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from core.executor import AgentExecutor


BANNER = """
╔══════════════════════════════════════════════════════════════╗
║  Executor v0.3 — Planner → Task Engine                   ║
║  LLM = PLANNER | Executor = ORCHESTRATOR              ║
║  TaskRunner = EXECUTOR | Verification = AUTHORITY     ║
╚══════════════════════════════════════════════════════════════╝
"""

HELP = """
Cách dùng:

  python -m core.executor.cli run <project_id> <goal> [--no-execute]
      Plan + execute (default).
      --no-execute: chỉ plan, không chạy.

  python -m core.executor.cli run-existing <task_id>
      Chạy lại task đã có (bỏ qua planning).

  python -m core.executor.cli --help
"""


def run_goal(project_id: str, goal: str, no_execute: bool) -> None:
    """Plan and optionally execute."""
    executor = AgentExecutor(auto_execute=not no_execute)
    print(BANNER)
    print(f"▶ Goal: {goal!r}")
    print(f"  Project: {project_id}")
    print()

    result = executor.run(project_id, goal)
    print(result.summary())

    if result.error:
        print(f"\n❌ Error: {result.error}")
    else:
        print(f"\n✅ Status: {result.status}")


def run_existing(task_id: str) -> None:
    """Execute an already-saved task."""
    executor = AgentExecutor(auto_execute=False)
    print(BANNER)
    print(f"▶ Running existing task: {task_id}")
    print()

    result = executor.execute_existing(task_id)
    print(result.summary())

    if result.error:
        print(f"\n❌ Error: {result.error}")
    else:
        print(f"\n✅ Status: {result.status}")


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(BANNER)
        print(HELP)
        sys.exit(0)

    cmd = sys.argv[1].lower()

    if cmd == "run":
        if len(sys.argv) < 4:
            print("Usage: run <project_id> <goal> [--no-execute]")
            sys.exit(1)
        project_id = sys.argv[2]
        goal = sys.argv[3]
        no_execute = "--no-execute" in sys.argv
        run_goal(project_id, goal, no_execute)

    elif cmd == "run-existing":
        if len(sys.argv) < 3:
            print("Usage: run-existing <task_id>")
            sys.exit(1)
        run_existing(sys.argv[2])

    else:
        print(BANNER)
        print(HELP)
        sys.exit(1)


if __name__ == "__main__":
    main()
