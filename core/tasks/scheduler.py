# core/tasks/scheduler.py
"""Task Scheduler — deterministic autonomous execution loop for Agent-Core tasks."""

from __future__ import annotations

import time
from typing import Optional, Callable

from core.tasks.schema import Task, TaskStatus
from core.tasks.queue import TaskQueue
from core.events.bus import EventBus
from core.events.schema import new_event, EventPhase, EventStatus


class TaskScheduler:
    """Bounded, deterministic autonomous scheduler for processing queued tasks."""

    def __init__(
        self,
        queue: Optional[TaskQueue] = None,
        event_bus: Optional[EventBus] = None,
    ):
        self.queue = queue or TaskQueue()
        self.event_bus = event_bus or EventBus()

    def step_once(self, executor_fn: Callable[[Task], Task]) -> Optional[Task]:
        """Process a single task from the queue deterministically."""
        task = self.queue.dequeue()
        if not task:
            return None

        # State transition -> PLANNING -> RUNNING
        task.status = TaskStatus.PLANNING
        self.queue.tm.save_task(task)

        if self.event_bus:
            self.event_bus.publish(
                new_event(
                    run_id=task.task_id,
                    phase=EventPhase.PLAN.value,
                    action=f"Planning task '{task.title}'",
                    task_id=task.task_id,
                )
            )

        task.mark_running()
        self.queue.tm.save_task(task)

        if self.event_bus:
            self.event_bus.publish(
                new_event(
                    run_id=task.task_id,
                    phase=EventPhase.EXECUTE.value,
                    action=f"Executing task '{task.title}'",
                    task_id=task.task_id,
                )
            )

        try:
            executed_task = executor_fn(task)
            if executed_task.status == TaskStatus.COMPLETED:
                if self.event_bus:
                    self.event_bus.publish(
                        new_event(
                            run_id=task.task_id,
                            phase=EventPhase.RESULT.value,
                            action=f"Task '{task.title}' COMPLETED",
                            status=EventStatus.PASS.value,
                            task_id=task.task_id,
                        )
                    )
            elif executed_task.status == TaskStatus.FAILED:
                # Handle bounded retries
                if executed_task.retry_count < executed_task.max_retries:
                    executed_task.retry_count += 1
                    executed_task.status = TaskStatus.RETRY
                    self.queue.tm.save_task(executed_task)
                    if self.event_bus:
                        self.event_bus.publish(
                            new_event(
                                run_id=task.task_id,
                                phase=EventPhase.RECOVERY.value,
                                action=f"Task '{task.title}' scheduled for RETRY ({executed_task.retry_count}/{executed_task.max_retries})",
                                status=EventStatus.PENDING.value,
                                task_id=task.task_id,
                            )
                        )
                else:
                    if self.event_bus:
                        self.event_bus.publish(
                            new_event(
                                run_id=task.task_id,
                                phase=EventPhase.RESULT.value,
                                action=f"Task '{task.title}' FAILED (max retries reached)",
                                status=EventStatus.FAIL.value,
                                task_id=task.task_id,
                            )
                        )
            return executed_task
        except Exception as exc:
            task.mark_failed(str(exc))
            self.queue.tm.save_task(task)
            if self.event_bus:
                self.event_bus.publish(
                    new_event(
                        run_id=task.task_id,
                        phase=EventPhase.RESULT.value,
                        action=f"Task execution error: {exc}",
                        status=EventStatus.ERROR.value,
                        task_id=task.task_id,
                    )
                )
            return task

        return task

    def run_until_empty(
        self,
        executor_fn: Callable[[Task], Task],
        max_steps: int = 10,
    ) -> list[Task]:
        """Run up to max_steps tasks autonomously. Prevents infinite loops."""
        processed = []
        steps = 0
        while steps < max_steps:
            t = self.step_once(executor_fn)
            if not t:
                break
            processed.append(t)
            steps += 1
        return processed
