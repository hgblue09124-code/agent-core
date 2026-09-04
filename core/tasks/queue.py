# core/tasks/queue.py
"""Task Queue — persistent, priority-based task queue for Agent-Core."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from core.tasks.schema import Task, TaskStatus
from core.tasks.manager import TaskManager


class TaskQueue:
    """Persistent priority queue for scheduling and managing autonomous tasks."""

    def __init__(self, task_manager: Optional[TaskManager] = None):
        self.tm = task_manager or TaskManager()

    def enqueue(self, task: Task) -> Task:
        """Enqueue a new task."""
        if not task.created_at:
            task.created_at = task._now() if hasattr(task, "_now") else ""
        return self.tm.create_task(task)

    def dequeue(self) -> Optional[Task]:
        """Pop the highest priority pending task whose dependencies are satisfied."""
        pending_tasks = [t for t in self.tm.list_tasks() if t.status in (TaskStatus.PENDING, TaskStatus.RETRY)]
        if not pending_tasks:
            return None

        # Sort by priority (asc), then created_at (asc)
        pending_tasks.sort(key=lambda t: (t.priority, t.created_at or ""))

        completed_ids = {t.task_id for t in self.tm.list_tasks() if t.status == TaskStatus.COMPLETED}

        for task in pending_tasks:
            # Check dependencies
            if all(dep_id in completed_ids for dep_id in task.dependencies):
                return task

        return None

    def pause(self, task_id: str) -> Optional[Task]:
        """Pause a pending or running task."""
        task = self.tm.get_task(task_id)
        if not task:
            return None
        task.status = TaskStatus.PAUSED
        return self.tm.save_task(task)

    def resume(self, task_id: str) -> Optional[Task]:
        """Resume a paused task."""
        task = self.tm.get_task(task_id)
        if not task:
            return None
        if task.status == TaskStatus.PAUSED:
            task.status = TaskStatus.PENDING
            return self.tm.save_task(task)
        return task

    def cancel(self, task_id: str) -> Optional[Task]:
        """Cancel a task."""
        task = self.tm.get_task(task_id)
        if not task:
            return None
        task.mark_cancelled()
        return self.tm.save_task(task)

    def list_queue(self) -> list[Task]:
        """Return all tasks in priority order."""
        tasks = self.tm.list_tasks()
        tasks.sort(key=lambda t: (t.priority, t.created_at or ""))
        return tasks
