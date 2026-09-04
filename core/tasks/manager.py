# core/tasks/manager.py
"""Task Manager — JSON-file-backed task persistence.

agent-core/tasks/
    index.json          ← {"next_id": 1, "tasks": {"TASK-0001": "task-0001.json"}}
    task-0001.json     ← full Task JSON
    task-0002.json
    ...
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Optional

from core.tasks.schema import Task, TaskStatus, new_task_id


class TaskManager:
    """CRUD operations on tasks, persisted as JSON files.

    No database. No LLM. Stdlib only.
    """

    def __init__(self, tasks_dir: Optional[str] = None):
        if tasks_dir:
            self.tasks_dir = Path(tasks_dir)
        else:
            agent_core = Path(__file__).resolve().parents[2]
            self.tasks_dir = agent_core / "tasks"

        self.index_path = self.tasks_dir / "index.json"
        self.tasks_dir.mkdir(parents=True, exist_ok=True)

        self._index: dict = self._load_index()

    # ── Index ─────────────────────────────────────────────────────────────

    def _load_index(self) -> dict:
        """Load index from disk. Returns structure with 'next_id' and 'tasks'."""
        if self.index_path.exists():
            try:
                text = self.index_path.read_text(encoding="utf-8")
                if text.strip():
                    raw = json.loads(text)
                    # Normalize old format: {"TASK-0001": "task-0001"} → {"TASK-0001": "TASK-0001"}
                    tasks = raw.get("tasks", {})
                    if tasks and all(isinstance(v, str) for v in tasks.values()):
                        tasks = {k: k for k in tasks.keys()}
                    return {
                        "next_id": int(raw.get("next_id", 1)),
                        "tasks": tasks,
                    }
            except (json.JSONDecodeError, OSError, ValueError):
                pass
        return {"next_id": 1, "tasks": {}}

    def _save_index(self) -> None:
        """Atomic write of index."""
        tmp = self.index_path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(self._index, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        tmp.replace(self.index_path)

    # ── CRUD ──────────────────────────────────────────────────────────────

    def _task_path(self, task_id: str) -> Path:
        # Normalise to filename format
        filename = task_id.lower().replace("task-", "") + ".json"
        return self.tasks_dir / f"task-{filename}"

    def _save_task_file(self, task: Task) -> None:
        """Write task JSON atomically."""
        path = self._task_path(task.task_id)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(task.to_json(), encoding="utf-8")
        tmp.replace(path)

    def _load_task_file(self, task_id: str) -> Task:
        path = self._task_path(task_id)
        return Task.from_json(path.read_text(encoding="utf-8"))

    # ── Public API ────────────────────────────────────────────────────────

    def create_task(
        self,
        project_id: str | Task,
        title: str = "",
        description: str = "",
        steps: Optional[list] = None,
    ) -> Task:
        """Create and persist a new task. Accepts either (project_id, title) or a Task instance."""
        if isinstance(project_id, Task):
            task = project_id
            if not task.task_id:
                task.task_id = new_task_id(self._index["next_id"])
                self._index["next_id"] += 1
            if not task.created_at:
                task.created_at = self._now()
        else:
            task_id = new_task_id(self._index["next_id"])
            now = self._now()
            task = Task(
                task_id=task_id,
                project_id=project_id,
                title=title,
                description=description,
                status=TaskStatus.PENDING,
                created_at=now,
                steps=list(steps) if steps else [],
            )
            self._index["next_id"] += 1

        # Persist
        self._save_task_file(task)

        # Update index
        self._index["tasks"][task.task_id] = task.task_id.lower()
        self._save_index()

        return task

    def save_task(self, task: Task) -> Task:
        """Save/upsert an existing task."""
        self._save_task_file(task)
        self._index["tasks"][task.task_id] = task.task_id.lower()
        self._save_index()
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        """Load a task by ID, or None if not found."""
        if task_id not in self._index["tasks"]:
            return None
        try:
            return self._load_task_file(task_id)
        except FileNotFoundError:
            return None

    def update_task(self, task: Task) -> None:
        """Save updated task."""
        self._save_task_file(task)

    def list_tasks(
        self,
        project_id: Optional[str] = None,
        status: Optional[TaskStatus] = None,
    ) -> list[Task]:
        """List tasks, optionally filtered."""
        results: list[Task] = []
        for task_id in self._index["tasks"]:
            try:
                task = self._load_task_file(task_id)
            except (FileNotFoundError, json.JSONDecodeError):
                continue
            if project_id and task.project_id != project_id:
                continue
            if status and task.status != status:
                continue
            results.append(task)

        # Sort newest first
        results.sort(
            key=lambda t: t.created_at,
            reverse=True,
        )
        return results

    def delete_task(self, task_id: str) -> bool:
        """Delete a task. Returns True if it existed."""
        if task_id not in self._index["tasks"]:
            return False

        path = self._task_path(task_id)
        if path.exists():
            path.unlink()

        del self._index["tasks"][task_id]
        self._save_index()
        return True

    def count_tasks(self) -> int:
        """Total number of registered task IDs."""
        return len(self._index["tasks"])

    # ── Helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _now() -> str:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    # ── CLI helpers ──────────────────────────────────────────────────────

    def cli_list(self, project_id: Optional[str] = None) -> None:
        tasks = self.list_tasks(project_id=project_id)
        if not tasks:
            print("Không có nhiệm vụ nào.")
            return
        for t in tasks:
            flag = _status_icon(t.status.value)
            duration = f"{t.total_duration():.1f}s" if t.total_duration() > 0 else ""
            print(
                f"{flag} {t.task_id}  [{t.status.value}]"
                f"{'  proj=' + t.project_id if project_id is None else ''}"
                f"  — {t.title}"
                f"{'  ' + duration if duration else ''}"
            )

    def cli_inspect(self, task_id: str) -> None:
        task = self.get_task(task_id)
        if task is None:
            print(f"Không tìm thấy: {task_id}")
            return

        print(f"Nhiệm vụ : {task.task_id}")
        print(f"Dự án     : {task.project_id}")
        print(f"Tiêu đề  : {task.title}")
        print(f"Mô tả    : {task.description}")
        print(f"Trạng thái: {task.status.value}")
        print(f"Tạo lúc  : {task.created_at}")
        if task.started_at:
            print(f"Bắt đầu  : {task.started_at}")
        if task.completed_at:
            print(f"Hoàn thành: {task.completed_at}")
        print(f"Tổng bước : {len(task.steps)}")
        print(f"Kết quả   : {task.step_summary()}")
        if task.error:
            print(f"Lỗi       : {task.error}")
        if task.verification:
            v = task.verification
            print(f"Xác minh  : {'✅ ĐÃ XÁC MINH' if v.verified else '❌ CHƯA XÁC MINH'}")
            if v.checks_performed:
                for c in v.checks_performed:
                    print(f"  • {c}")
            if v.failures:
                for f in v.failures:
                    print(f"  ✗ {f}")
        print()
        for i, step in enumerate(task.steps, 1):
            print(f"  Bước {i}: {step.title}")
            print(f"    Loại: {step.type.value}")
            if step.description:
                print(f"    Mô tả: {step.description}")
            if step.result:
                r = step.result
                # Support both StepResult dataclass and plain dict (legacy)
                if isinstance(r, dict):
                    ec = r.get("exit_code", 0)
                    dur = r.get("duration_seconds", 0.0)
                    stdout = r.get("stdout", "")
                    stderr = r.get("stderr", "")
                else:
                    ec = r.exit_code
                    dur = r.duration_seconds
                    stdout = r.stdout
                    stderr = r.stderr
                ok = "✅" if ec == 0 else "❌"
                print(f"    Kết quả: {ok} exit={ec}  time={dur:.3f}s")
                if stdout:
                    for line in stdout.splitlines()[:5]:
                        print(f"      stdout: {line}")
                if stderr and ec != 0:
                    for line in stderr.splitlines()[:5]:
                        print(f"      stderr: {line}")
            else:
                print(f"    Kết quả: ⏳ (chưa chạy)")


def _status_icon(status: str) -> str:
    icons = {
        "PENDING":   "⏳",
        "RUNNING":   "🔄",
        "COMPLETED": "✅",
        "FAILED":    "❌",
        "CANCELLED": "🚫",
    }
    return icons.get(status, "?")
