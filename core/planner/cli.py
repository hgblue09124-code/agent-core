#!/usr/bin/env python3
# core/planner/cli.py
"""Planner CLI — LLM-assisted task planning.

Usage:
    python -m core.planner.cli plan <project_id> <objective> [--save]
    python -m core.planner.cli validate <plan.json>
    python -m core.planner.cli --help

Examples:
    python -m core.planner.cli plan cuu-gioi "Audit Runtime Console"
    python -m core.planner.cli plan cuu-gioi "Inspect frontend source-of-truth" --save
"""

import json
import sys
from pathlib import Path

_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from core.planner import (
    Planner,
    create_provider,
    load_provider_config,
    plan_to_task,
    validate_plan,
)
from core.planner.schema import Plan
from core.tasks.manager import TaskManager
from core.projects.manager import ProjectManager


BANNER = """
╔══════════════════════════════════════════════════════════════╗
║  Planner v0.2 — LLM-assisted task planning                ║
║  LLM = PLANNER | TaskRunner = EXECUTOR | Verification    ║
║  NEVER executes commands.                                  ║
╚══════════════════════════════════════════════════════════════╝
"""


HELP = """
Cách dùng:

  python -m core.planner.cli plan <project_id> <objective> [--save]
      Tạo plan từ objective.
      --save: lưu thành task (chưa chạy).

  python -m core.planner.cli validate <plan.json>
      Kiểm tra plan JSON.

  python -m core.planner.cli --help
      Hiển thị hướng dẫn này.
"""


def print_plan(plan: Plan, raw: str = "") -> None:
    """Display a plan in human-readable form."""
    print(f"Objective : {plan.objective}")
    print(f"Dự án    : {plan.project_id}")
    print(f"Complexity: {plan.estimated_complexity.value}")
    print(f"Tổng bước: {len(plan.steps)}")
    print()

    if plan.assumptions:
        print("Giả định:")
        for a in plan.assumptions:
            print(f"  • {a}")
        print()

    print("Các bước:")
    for i, step in enumerate(plan.steps, 1):
        deps = f" (deps: {', '.join(step.dependencies)})" if step.dependencies else ""
        print(f"  {i}. [{step.step_type}] {step.title}{deps}")
        if step.description:
            print(f"       {step.description}")
        if step.command:
            cmd_str = step.command
            if step.arguments:
                cmd_str += " " + " ".join(step.arguments)
            print(f"       → {cmd_str}")

    if plan.verification:
        print()
        print("Xác minh:")
        for v in plan.verification:
            method_tag = f"[{v.method}]" if v.method else ""
            print(f"  • {v.description} {method_tag}")

    if plan.risks:
        print()
        print("Rủi ro:")
        for r in plan.risks:
            print(f"  ⚠ {r}")

    if plan.notes:
        print()
        print(f"Ghi chú: {plan.notes}")

    if raw:
        print()
        print(f"[Raw LLM output: {len(raw)} chars]")


def run_plan(project_id: str, objective: str, save: bool) -> None:
    """Run the full planning pipeline."""
    # Verify project exists
    proj_mgr = ProjectManager()
    project = proj_mgr.get(project_id)
    if not project:
        print(f"❌ Project không tồn tại trong registry: {project_id}")
        print("   Dùng: python -m core.projects.cli list")
        sys.exit(1)

    # Load provider config
    cfg = load_provider_config()
    print(f"Provider : {cfg.provider}")
    print(f"Model    : {cfg.model}")
    print(f"Project  : {project.name}")
    print()

    # Create planner
    provider = create_provider(cfg)
    planner = Planner(provider=provider)

    print(f"▶ Đang lên kế hoạch: {objective!r}")

    # Run planning
    result = planner.plan(project_id, objective)

    # Context stats
    if result.context_stats:
        print()
        print("Context:")
        print(f"  Tổng chars : {result.context_stats.total_chars}")
        print(f"  Tokens ≈    : {result.context_stats.approx_tokens} (APPROXIMATE)")
        print(f"  Docs        : {', '.join(result.context_stats.documents_included)}")

    # Error check
    if result.error:
        print()
        print(f"❌ Lỗi: {result.error}")

    if not result.validation.valid:
        print()
        print("❌ Validation failed:")
        for err in result.validation.errors:
            print(f"  [{err.code}] {err.message}")
            if err.field:
                print(f"    Field: {err.field}")
        if result.raw_llm_output:
            print()
            print(f"Raw LLM output (first 500 chars):")
            print(result.raw_llm_output[:500])
        sys.exit(1)

    # Warnings
    if result.validation.warnings:
        print()
        print("⚠️  Cảnh báo:")
        for w in result.validation.warnings:
            print(f"  [{w.code}] {w.message}")

    # Display plan
    print()
    if result.plan:
        print_plan(result.plan, result.raw_llm_output)

    # Save as task
    if save and result.plan:
        task_mgr = TaskManager()
        task = plan_to_task(result.plan)
        task = task_mgr.create_task(
            project_id=result.plan.project_id,
            title=result.plan.objective,
            description=result.plan.notes or result.plan.objective,
            steps=task.steps,
        )
        print()
        print(f"✅ Đã lưu thành task: {task.task_id}")
        print(f"   Tiêu đề: {task.title}")
        print(f"   Bước   : {len(task.steps)}")
        print()
        print(f"   Tiếp theo: python -m core.tasks.cli run {task.task_id}")
    elif save and not result.plan:
        print("⚠️  Không lưu được vì plan không hợp lệ.")


def run_validate(plan_path: str) -> None:
    """Validate a plan from a JSON file."""
    path = Path(plan_path)
    if not path.exists():
        print(f"❌ File không tồn tại: {plan_path}")
        sys.exit(1)

    try:
        raw = path.read_text(encoding="utf-8")
        parsed = json.loads(raw)
        plan = Plan.from_dict(parsed)
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        print(f"❌ Parse error: {exc}")
        sys.exit(1)

    # Load registered project IDs
    mgr = ProjectManager()
    project_ids = [p.project_id for p in mgr.list_projects()]
    validation = validate_plan(plan, project_ids)

    print(f"Plan     : {plan.objective}")
    print(f"Dự án    : {plan.project_id}")
    print(f"Hợp lệ   : {'✅ Có' if validation.valid else '❌ Không'}")

    if validation.errors:
        print()
        print("Lỗi:")
        for e in validation.errors:
            print(f"  [{e.code}] {e.message}")
            if e.field:
                print(f"    Field: {e.field}")

    if validation.warnings:
        print()
        print("Cảnh báo:")
        for w in validation.warnings:
            print(f"  [{w.code}] {w.message}")

    if not validation.valid:
        sys.exit(1)


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(BANNER)
        print(HELP)
        sys.exit(0)

    cmd = sys.argv[1].lower()

    if cmd == "plan":
        if len(sys.argv) < 4:
            print("Usage: plan <project_id> <objective> [--save]")
            sys.exit(1)

        project_id = sys.argv[2]
        objective = sys.argv[3]
        save = "--save" in sys.argv

        run_plan(project_id, objective, save)

    elif cmd == "validate":
        if len(sys.argv) < 3:
            print("Usage: validate <plan.json>")
            sys.exit(1)
        run_validate(sys.argv[2])

    else:
        print(f"❌ Lệnh không rõ: {cmd}")
        print(HELP)
        sys.exit(1)


if __name__ == "__main__":
    main()
