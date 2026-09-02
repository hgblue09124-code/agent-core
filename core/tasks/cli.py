#!/usr/bin/env python3
# core/tasks/cli.py
"""Task Engine CLI.

Usage:
    python -m core.tasks.cli list
    python -m core.tasks.cli list <project_id>
    python -m core.tasks.cli create <project_id> <title> [--description ...]
    python -m core.tasks.cli inspect <task_id>
    python -m core.tasks.cli run <task_id>
    python -m core.tasks.cli delete <task_id>
    python -m core.tasks.cli --help
"""

import sys
from pathlib import Path

# Allow running as script
_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from core.tasks.manager import TaskManager
from core.tasks.runner import TaskRunner
from core.projects.manager import ProjectManager
from core.tasks.schema import (
    TaskStep,
    StepType,
    Task,
    TaskStatus,
)


BANNER = """
╔═══════════════════════════════════════════════════════════╗
║  Task Engine v0.1 — deterministic task runner            ║
║  Không có LLM. Không có eval(). Stdlib only.              ║
╚═══════════════════════════════════════════════════════════╝
"""


HELP = """
Cách dùng:

  python -m core.tasks.cli list [--project <id>]
      Liệt kê tất cả task (hoặc theo project).

  python -m core.tasks.cli create <project_id> <title> [--description <text>]
      Tạo task mới, gắn với project đã đăng ký.
      Sau khi tạo, dùng 'add-step' hoặc sửa file JSON để thêm bước.

  python -m core.tasks.cli add-step <task_id> <type> <title>
      Thêm bước vào task. Type: shell | python | inspect
      Bước shell: --cmd "echo hi" [--arg arg1 --arg arg2]
      Bước python: --module <name> [--py-arg a --py-arg b]
      Bước inspect: (không cần tham số)

  python -m core.tasks.cli inspect <task_id>
      Xem chi tiết task.

  python -m core.tasks.cli run <task_id>
      Chạy task. Cập nhật file JSON.

  python -m core.tasks.cli delete <task_id>
      Xoá task.

Ví dụ:

  python -m core.tasks.cli create cuu-gioi "Audit Runtime Console"
  python -m core.tasks.cli add-step TASK-0001 inspect "Kiểm tra dự án"
  python -m core.tasks.cli add-step TASK-0001 shell "Liệt kê docs" --cmd "ls docs/"
  python -m core.tasks.cli run TASK-0001
  python -m core.tasks.cli inspect TASK-0001
"""


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(BANNER)
        print(HELP)
        sys.exit(0)

    cmd = sys.argv[1].lower()
    mgr = TaskManager()

    if cmd == "list":
        if len(sys.argv) >= 4 and sys.argv[2] == "--project":
            mgr.cli_list(project_id=sys.argv[3])
        else:
            mgr.cli_list()

    elif cmd == "create":
        if len(sys.argv) < 4:
            print("Usage: create <project_id> <title> [--description ...]")
            sys.exit(1)
        project_id = sys.argv[2]
        title = sys.argv[3]
        description = ""
        if "--description" in sys.argv:
            i = sys.argv.index("--description")
            if i + 1 < len(sys.argv):
                description = sys.argv[i + 1]

        # Validate project exists
        proj_mgr = ProjectManager()
        if not proj_mgr.project_exists(project_id):
            print(f"❌ Project không tồn tại trong registry: {project_id}")
            print("   Dùng: python -m core.projects.cli list")
            sys.exit(1)

        task = mgr.create_task(project_id, title, description)
        print(f"✅ Đã tạo: {task.task_id}")
        print(f"   Dự án : {task.project_id}")
        print(f"   Tiêu đề: {task.title}")
        print()
        print(f"   Tiếp theo: python -m core.tasks.cli add-step {task.task_id} inspect \"...\"")
        print(f"              python -m core.tasks.cli run {task.task_id}")

    elif cmd == "add-step":
        if len(sys.argv) < 5:
            print("Usage: add-step <task_id> <type> <title> [--cmd ...] [--arg ...] [--module ...] [--py-arg ...]")
            sys.exit(1)

        task_id = sys.argv[2]
        step_type_str = sys.argv[3]

        # Find the first --arg / --cmd / --module / --py-arg flag
        # Everything between step_type and the first flag is the title
        first_flag_idx = len(sys.argv)
        for i, arg in enumerate(sys.argv):
            if i >= 4 and arg.startswith("--"):
                first_flag_idx = i
                break
        step_title = " ".join(sys.argv[4:first_flag_idx])

        try:
            step_type = StepType(step_type_str)
        except ValueError:
            print(f"❌ Loại bước không hợp lệ: {step_type_str}")
            print(f"   Hợp lệ: {[s.value for s in StepType]}")
            sys.exit(1)

        task = mgr.get_task(task_id)
        if not task:
            print(f"❌ Không tìm thấy task: {task_id}")
            sys.exit(1)

        if task.status != TaskStatus.PENDING:
            print(f"❌ Task đã chạy rồi (status={task.status.value}). Không thể thêm bước.")
            sys.exit(1)

        step = TaskStep(type=step_type, title=step_title or step_type_str)

        if step_type == StepType.SHELL:
            if "--cmd" in sys.argv:
                i = sys.argv.index("--cmd")
                if i + 1 < len(sys.argv):
                    step.command = sys.argv[i + 1]
            # Parse --arg pairs
            args = []
            i = 0
            while i < len(sys.argv):
                if sys.argv[i] == "--arg" and i + 1 < len(sys.argv):
                    args.append(sys.argv[i + 1])
                i += 1
            step.args = args

        elif step_type == StepType.PYTHON:
            if "--module" in sys.argv:
                i = sys.argv.index("--module")
                if i + 1 < len(sys.argv):
                    step.module = sys.argv[i + 1]
            elif step.command:
                step.module = step.command
            py_args = []
            i = 0
            while i < len(sys.argv):
                if sys.argv[i] == "--py-arg" and i + 1 < len(sys.argv):
                    py_args.append(sys.argv[i + 1])
                i += 1
            step.py_args = py_args

        task.add_step(step)
        mgr.update_task(task)
        print(f"✅ Đã thêm bước vào {task_id}:")
        print(f"   Loại   : {step.type.value}")
        print(f"   Tiêu đề: {step.title}")
        if step.command:
            print(f"   Command: {step.command}")
        if step.module:
            print(f"   Module : {step.module}")

    elif cmd == "inspect":
        if len(sys.argv) < 3:
            print("Usage: inspect <task_id>")
            sys.exit(1)
        mgr.cli_inspect(sys.argv[2])

    elif cmd == "run":
        if len(sys.argv) < 3:
            print("Usage: run <task_id>")
            sys.exit(1)
        task_id = sys.argv[2]
        task = mgr.get_task(task_id)
        if not task:
            print(f"❌ Không tìm thấy: {task_id}")
            sys.exit(1)
        if not task.can_run():
            print(f"❌ Task đã chạy (status={task.status.value}).")
            sys.exit(1)
        if not task.steps:
            print(f"❌ Task chưa có bước nào. Dùng add-step trước.")
            sys.exit(1)

        print(f"▶ Chạy {task_id}: {task.title}")
        print()
        runner = TaskRunner()
        updated = runner.run(task)
        print()
        mgr.cli_inspect(task_id)
        print()
        if updated.status == TaskStatus.COMPLETED:
            if updated.verification and updated.verification.verified:
                print("✅ HOÀN THÀNH VÀ ĐÃ XÁC MINH")
            else:
                print("⚠️  HOÀN THÀNH NHƯNG CHƯA XÁC MINH (verification=fail)")
        elif updated.status == TaskStatus.FAILED:
            print(f"❌ THẤT BẠI: {updated.error}")
            sys.exit(1)

    elif cmd == "delete":
        if len(sys.argv) < 3:
            print("Usage: delete <task_id>")
            sys.exit(1)
        ok = mgr.delete_task(sys.argv[2])
        print(f"Đã xoá: {sys.argv[2]}" if ok else f"Không tìm thấy: {sys.argv[2]}")

    else:
        print(f"❌ Lệnh không rõ: {cmd}")
        print(HELP)
        sys.exit(1)


if __name__ == "__main__":
    main()
