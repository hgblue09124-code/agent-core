# core/executor/executor.py
"""Agent Executor v0.3.

Orchestrates the existing Planner v0.2 and Task Engine v0.1.

Pipeline:
    goal
      ↓
    Planner.plan()             (existing, returns Plan)
      ↓
    plan_to_task()             (existing, returns Task)
      ↓
    TaskManager.create_task()  (existing, persists + returns Task)
      ↓
    TaskRunner.run()           (existing, returns updated Task)
      ↓
    Result (Task with verification)

Properties:
- Stateless. No autonomous loop, no memory, no retry loop.
- One goal in → one Task executed → one Result out.
- Provider-agnostic: works with any PlannerProvider.
- No source modification outside `core/executor/`.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from core.planner.planner import Planner, plan_to_task
from core.planner.schema import Plan
from core.planner.planner import PlanResult
from core.tasks.manager import TaskManager
from core.tasks.runner import TaskRunner
from core.tasks.schema import Task, VerificationResult


@dataclass
class ExecutorResult:
    """Result of a full plan→execute pipeline."""
    goal: str
    project_id: str
    task_id: Optional[str]
    status: str                # "PLANNED" | "COMPLETED" | "FAILED" | "VERIFIED" | "ERROR"
    plan: Optional[Plan]
    task: Optional[Task]
    plan_result: PlanResult
    error: Optional[str] = None

    @property
    def verified(self) -> bool:
        if self.task is None or self.task.verification is None:
            return False
        return bool(self.task.verification.verified)

    def summary(self) -> str:
        parts = [
            f"Goal      : {self.goal!r}",
            f"Project   : {self.project_id}",
            f"Task      : {self.task_id or '(none)'}",
            f"Status    : {self.status}",
            f"Verified  : {'YES' if self.verified else 'NO'}",
        ]
        if self.task is not None:
            parts.append(f"Steps     : {len(self.task.steps)}")
            parts.append(f"Result    : {self.task.step_summary()}")
        if self.error:
            parts.append(f"Error     : {self.error}")
        return "\n".join(parts)


class AgentExecutor:
    """Stateless orchestrator. Wires existing components together."""

    def __init__(
        self,
        planner: Optional[Planner] = None,
        task_manager: Optional[TaskManager] = None,
        task_runner: Optional[TaskRunner] = None,
        auto_execute: bool = True,
    ):
        """Args:
            planner: Planner instance (default: Planner with MockProvider).
            task_manager: TaskManager (default: new).
            task_runner: TaskRunner (default: new, 60s/step timeout).
            auto_execute: if True, run the task immediately after planning.
        """
        self.planner = planner or Planner()
        self.task_manager = task_manager or TaskManager()
        self.task_runner = task_runner or TaskRunner()
        self.auto_execute = auto_execute

    def run(self, project_id: str, goal: str) -> ExecutorResult:
        """End-to-end: plan → task → execute → verify → result.

        Returns an ExecutorResult. Never raises under normal conditions;
        all errors are captured in `error`.
        """
        # 1. Plan
        plan_result = self.planner.plan(project_id, goal)
        if plan_result.plan is None:
            return ExecutorResult(
                goal=goal,
                project_id=project_id,
                task_id=None,
                status="ERROR",
                plan=None,
                task=None,
                plan_result=plan_result,
                error=plan_result.error or "Planning failed.",
            )

        # 2. Plan → Task (in-memory)
        task_template = plan_to_task(plan_result.plan)

        # 3. Persist via TaskManager (assigns task_id, returns full Task)
        task = self.task_manager.create_task(
            project_id=task_template.project_id,
            title=task_template.title,
            description=task_template.description,
            steps=task_template.steps,
        )

        # 4. Optionally execute
        if not self.auto_execute:
            return ExecutorResult(
                goal=goal,
                project_id=project_id,
                task_id=task.task_id,
                status="PLANNED",
                plan=plan_result.plan,
                task=task,
                plan_result=plan_result,
            )

        executed = self.task_runner.run(task)

        # 5. Determine status
        status = self._status_from_task(executed)
        return ExecutorResult(
            goal=goal,
            project_id=project_id,
            task_id=executed.task_id,
            status=status,
            plan=plan_result.plan,
            task=executed,
            plan_result=plan_result,
        )

    def plan_only(self, project_id: str, goal: str) -> ExecutorResult:
        """Plan but do not execute. Convenience method."""
        return self.run(project_id, goal)

    def execute_existing(self, task_id: str) -> ExecutorResult:
        """Execute an already-saved task (skip the planning step).

        Useful for re-running tasks or running CLI-generated tasks.
        """
        task = self.task_manager.get_task(task_id)
        if task is None:
            return ExecutorResult(
                goal="",
                project_id="",
                task_id=task_id,
                status="ERROR",
                plan=None,
                task=None,
                plan_result=PlanResult(
                    plan=None,
                    validation=None,  # type: ignore[arg-type]
                    raw_llm_output="",
                    context_stats=None,
                    provider_name="",
                ),
                error=f"Task '{task_id}' not found.",
            )

        if not task.can_run():
            return ExecutorResult(
                goal=task.title,
                project_id=task.project_id,
                task_id=task.task_id,
                status="ERROR",
                plan=None,
                task=task,
                plan_result=PlanResult(
                    plan=None,
                    validation=None,  # type: ignore[arg-type]
                    raw_llm_output="",
                    context_stats=None,
                    provider_name="",
                ),
                error=f"Task in status {task.status.value} cannot run.",
            )

        executed = self.task_runner.run(task)
        return ExecutorResult(
            goal=task.title,
            project_id=task.project_id,
            task_id=executed.task_id,
            status=self._status_from_task(executed),
            plan=None,
            task=executed,
            plan_result=PlanResult(
                plan=None,
                validation=None,  # type: ignore[arg-type]
                raw_llm_output="",
                context_stats=None,
                provider_name="",
            ),
        )

    def _status_from_task(self, task: Task) -> str:
        """Map a Task's status + verification to an ExecutorResult status."""
        if task.status.value == "COMPLETED":
            if task.verification and task.verification.verified:
                return "VERIFIED"
            return "COMPLETED"
        if task.status.value == "FAILED":
            return "FAILED"
        if task.status.value == "CANCELLED":
            return "CANCELLED"
        return task.status.value
