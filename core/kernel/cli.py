#!/usr/bin/env python3
# core/kernel/cli.py
"""Agent Kernel CLI v1.0.

Usage:
    python -m core.kernel.cli run "<goal>" [--project-id <pid>]
    python -m core.kernel.cli status <run_id>
    python -m core.kernel.cli inspect <run_id>
    python -m core.kernel.cli list
"""

import argparse
import sys
from pathlib import Path

_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from core.kernel.kernel import Kernel
from core.kernel.schema import KernelStatus, KernelPhase


def cmd_run(args):
    kernel = Kernel(project_id=args.project_id)
    result = kernel.run(args.goal, project_id=args.project_id)
    print(f"Run ID   : {result.run_id}")
    print(f"Status   : {result.status}")
    print(f"Phase    : {result.phase}")
    print(f"LLM calls: {result.llm_calls}")
    print(f"Duration : {result.duration_seconds:.3f}s")
    if result.errors:
        print(f"Errors   : {', '.join(result.errors)}")
    return 0


def cmd_status(args):
    kernel = Kernel()
    ctx = kernel.get_run(args.run_id)
    if not ctx:
        print(f"Không tìm thấy: {args.run_id}")
        return 1
    print(f"Run ID   : {ctx.run_id}")
    print(f"Goal     : {ctx.goal}")
    print(f"Phase    : {ctx.kernel_phase}")
    print(f"Status   : {ctx.kernel_status}")
    print(f"LLM calls: {ctx.llm_calls}")
    print(f"Errors   : {ctx.errors or '—'}")
    return 0


def cmd_inspect(args):
    kernel = Kernel()
    ctx = kernel.get_run(args.run_id)
    if not ctx:
        print(f"Không tìm thấy: {args.run_id}")
        return 1
    import json
    print(json.dumps(ctx.to_dict(), indent=2, default=str))
    return 0


def cmd_list(args):
    kernel = Kernel()
    runs = kernel.list_runs()
    if not runs:
        print("Không có run nào.")
        return 0
    for rid in runs:
        ctx = kernel.get_run(rid)
        if ctx:
            print(f"  {rid}  [{ctx.kernel_status:9}]  {ctx.goal[:50]}")
    print(f"\n{len(runs)} run(s)")
    return 0


def main():
    parser = argparse.ArgumentParser(prog="python -m core.kernel.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="Chạy một goal")
    p_run.add_argument("goal")
    p_run.add_argument("--project-id", dest="project_id")
    p_run.set_defaults(func=cmd_run)

    p_status = sub.add_parser("status", help="Trạng thái một run")
    p_status.add_argument("run_id")
    p_status.set_defaults(func=cmd_status)

    p_insp = sub.add_parser("inspect", help="Chi tiết một run")
    p_insp.add_argument("run_id")
    p_insp.set_defaults(func=cmd_inspect)

    sub.add_parser("list", help="Liệt kê các run").set_defaults(func=cmd_list)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
