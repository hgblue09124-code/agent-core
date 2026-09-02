#!/usr/bin/env python3
# core/runtime/cli.py
"""Runtime v0.6 CLI.

Usage:
    python -m core.runtime.cli run "<goal>" [--project <project_id>]
    python -m core.runtime.cli status <run_id>
    python -m core.runtime.cli resume <run_id>
    python -m core.runtime.cli stop <run_id> [--reason <reason>]
    python -m core.runtime.cli list
"""

import argparse
import json
import sys
from pathlib import Path

_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from core.runtime import RuntimeEngine, RuntimeConfig, RunStatus
from core.runtime.schema import RunPhase


def _format_state(state) -> str:
    lines = [
        f"Run ID    : {state.run_id}",
        f"Status    : {state.status}",
        f"Phase     : {state.phase}",
        f"Goal      : {state.goal}",
        f"Project   : {state.project_id}",
        f"Started   : {state.started_at}",
        f"Last ckpt : {state.last_checkpoint_at}",
        f"Finished  : {state.finished_at}",
        f"Error     : {state.error or '—'}",
        f"Completed : {state.completed_task_ids or 'none'}",
        f"Failed    : {state.failed_task_ids or 'none'}",
        f"Task idx  : {state.current_task_index}",
        f"Attempts  : {state.attempt_count}",
        f"Retries   : {state.retry_count}",
        "",
        "Metrics:",
        f"  LLM calls      : {state.metrics.llm_calls} / {state.max_llm_calls}",
        f"  Est. tokens    : {state.metrics.estimated_tokens} / {state.max_token_budget}",
        f"  Refinements    : {state.metrics.plan_refinements} / {state.max_plan_refinements}",
        f"  Retries        : {state.metrics.retries}",
        f"  Checkpoints    : {state.metrics.checkpoints}",
        f"  Internet calls : {state.metrics.internet_calls}",
        "",
        f"Recovery  : {state.recovery_point or '—'}",
    ]
    return "\n".join(lines)


def cmd_run(args):
    """Run a goal end-to-end."""
    from core.runtime import RuntimeEngine, RuntimeConfig
    from core.runtime.schema import RunPhase

    cfg = RuntimeConfig.from_env()
    engine = RuntimeEngine(config=cfg)

    print(f"[Runtime v0.6] Starting run for goal: {args.goal[:80]}...")
    print(f"  Project    : {args.project}")
    print(f"  Max LLM    : {cfg.max_llm_calls}")
    print(f"  Max time   : {cfg.max_runtime_seconds}s")
    print(f"  Internet   : {cfg.internet_policy}")
    print()

    state = engine.run(args.project or "default", args.goal)

    print()
    print("=" * 60)
    print(f"STATUS : {state.status}")
    print(f"Run ID : {state.run_id}")
    print(f"Phase  : {state.phase}")
    if state.error:
        print(f"Error  : {state.error}")
    if state.completed_task_ids:
        print(f"Done   : {len(state.completed_task_ids)} task(s)")
    if state.failed_task_ids:
        print(f"Failed : {len(state.failed_task_ids)} task(s)")
    print(f"LLM calls: {state.metrics.llm_calls}")
    print(f"Checkpoints: {state.metrics.checkpoints}")

    return 0 if state.status in (
        RunStatus.COMPLETED.value, RunStatus.INTERRUPTED.value,
    ) else 1


def cmd_status(args):
    """Show run status."""
    from core.runtime import RuntimeEngine
    engine = RuntimeEngine()
    state = engine.get_state(args.run_id)
    if state is None:
        print(f"Run not found: {args.run_id}")
        return 1
    print(_format_state(state))
    return 0


def cmd_resume(args):
    """Resume an interrupted run."""
    from core.runtime import RuntimeEngine
    engine = RuntimeEngine()
    print(f"[Runtime v0.6] Resuming run: {args.run_id}")
    state = engine.resume(args.run_id)
    print()
    print(f"STATUS : {state.status}")
    print(f"Phase  : {state.phase}")
    if state.error:
        print(f"Error  : {state.error}")
    print(f"LLM calls: {state.metrics.llm_calls}")
    return 0


def cmd_stop(args):
    """Stop a running run."""
    from core.runtime import RuntimeEngine
    engine = RuntimeEngine()
    state = engine.stop(args.run_id, reason=args.reason)
    print(f"Run {args.run_id} stopped: {state.status}")
    return 0


def cmd_list(args):
    """List all runs."""
    from core.runtime import RuntimeEngine
    engine = RuntimeEngine()
    runs = engine.list_runs()
    if not runs:
        print("No runs found.")
        return 0
    for rid in runs:
        state = engine.get_state(rid)
        status = state.status if state else "CORRUPT"
        phase = state.phase if state else "?"
        print(f"  {rid}  [{status}]  {phase}")
    return 0


def main():
    parser = argparse.ArgumentParser(prog="python -m core.runtime.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # run
    p_run = sub.add_parser("run", help="Run a goal end-to-end")
    p_run.add_argument("goal", help="Goal description (quoted)")
    p_run.add_argument("--project", default="default",
                        help="Project ID (default: default)")
    p_run.set_defaults(func=cmd_run)

    # status
    p_st = sub.add_parser("status", help="Show run status")
    p_st.add_argument("run_id", help="Run ID (e.g. RUN-00001)")
    p_st.set_defaults(func=cmd_status)

    # resume
    p_re = sub.add_parser("resume", help="Resume an interrupted run")
    p_re.add_argument("run_id", help="Run ID to resume")
    p_re.set_defaults(func=cmd_resume)

    # stop
    p_sp = sub.add_parser("stop", help="Stop a running run")
    p_sp.add_argument("run_id", help="Run ID to stop")
    p_sp.add_argument("--reason", default="User requested",
                       help="Stop reason")
    p_sp.set_defaults(func=cmd_stop)

    # list
    p_ls = sub.add_parser("list", help="List all runs")
    p_ls.set_defaults(func=cmd_list)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
