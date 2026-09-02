#!/usr/bin/env python3
# tests/test_executor.py
"""Executor v0.3 — unit tests.

Run: python tests/test_executor.py
Or:  python -m unittest tests.test_executor -v

All tests run offline. No external API calls.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from core.executor import AgentExecutor, ExecutorResult
from core.executor.executor import AgentExecutor as _ExecClass
from core.planner.schema import (
    Plan, PlanStep, PlanComplexity, ValidationResult,
)
from core.planner.planner import MockPlannerProvider, PlanResult
from core.tasks.schema import Task, TaskStatus, StepType, TaskStep
from core.tasks.manager import TaskManager


# ── Test fixtures ───────────────────────────────────────────────────────

_TASK_DIR_COUNTER = 0


def make_temp_tasks_dir():
    """Create a temporary tasks directory for isolated tests."""
    global _TASK_DIR_COUNTER
    tmp = tempfile.mkdtemp(prefix=f"tasks-exec-{_TASK_DIR_COUNTER}-")
    _TASK_DIR_COUNTER += 1
    # Write minimal index
    Path(tmp, "index.json").write_text(
        json.dumps({"next_id": 1, "tasks": {}}),
        encoding="utf-8",
    )
    return tmp


def _valid_plan(project_id: str = "cuu-gioi") -> Plan:
    return Plan(
        objective="Inspect the project",
        project_id=project_id,
        assumptions=["Assumption 1"],
        steps=[
            PlanStep(
                step_id="s1",
                title="Inspect",
                step_type="inspect",
                dependencies=[],
                command="",
                arguments=[],
                expected_result="metadata",
                verify_contains=[],
                verify_not_contains=[],
                expect_exit_code=0,
            ),
            PlanStep(
                step_id="s2",
                title="Echo hello",
                step_type="shell",
                dependencies=["s1"],
                command="echo",
                arguments=["hello"],
                expected_result="hello printed",
                verify_contains=["hello"],
                verify_not_contains=[],
                expect_exit_code=0,
            ),
        ],
        verification=[],
        risks=["Minor risk"],
        estimated_complexity=PlanComplexity.SIMPLE,
        notes="Test plan",
    )


# ── ExecutorResult tests ────────────────────────────────────────────────

class TestExecutorResult(unittest.TestCase):
    """Tests for ExecutorResult dataclass."""

    def test_executor_result_fields(self):
        """All fields are present and accessible."""
        result = ExecutorResult(
            goal="Inspect project",
            project_id="proj-x",
            task_id="TASK-0001",
            status="VERIFIED",
            plan=None,
            task=None,
            plan_result=PlanResult(
                plan=None,
                validation=ValidationResult(valid=False),
                raw_llm_output="",
                context_stats=None,
                provider_name="Mock",
            ),
            error=None,
        )
        self.assertEqual(result.goal, "Inspect project")
        self.assertEqual(result.status, "VERIFIED")
        self.assertEqual(result.task_id, "TASK-0001")
        self.assertFalse(result.verified)

    def test_executor_result_verified_property_true(self):
        """verified=True when task has verified=True."""
        task = Task(
            task_id="TASK-0001",
            project_id="proj-x",
            title="Test",
            status=TaskStatus.COMPLETED,
        )
        task.verification = type("V", (), {"verified": True})()
        result = ExecutorResult(
            goal="x", project_id="x", task_id="TASK-0001",
            status="COMPLETED", plan=None, task=task,
            plan_result=PlanResult(plan=None, validation=None, raw_llm_output="", context_stats=None, provider_name=""),
        )
        self.assertTrue(result.verified)

    def test_executor_result_summary(self):
        """summary() returns a non-empty string."""
        result = ExecutorResult(
            goal="Test goal",
            project_id="proj-x",
            task_id="TASK-0001",
            status="COMPLETED",
            plan=None,
            task=None,
            plan_result=PlanResult(plan=None, validation=None, raw_llm_output="", context_stats=None, provider_name=""),
        )
        s = result.summary()
        self.assertIn("Test goal", s)
        self.assertIn("COMPLETED", s)


# ── AgentExecutor.run() tests ──────────────────────────────────────────

class TestAgentExecutorRun(unittest.TestCase):
    """Tests for AgentExecutor.run() full pipeline."""

    def test_run_full_pipeline(self):
        """run() produces a valid ExecutorResult with task_id."""
        tasks_dir = make_temp_tasks_dir()
        try:
            mgr = TaskManager(tasks_dir=tasks_dir)
            planner = _ExecClass(
                task_manager=mgr,
                auto_execute=False,  # plan only, no real execution
            )

            # MockPlannerProvider returns a valid plan for "Inspect project"
            result = planner.run("cuu-gioi", "Inspect the project")

            self.assertEqual(result.status, "PLANNED")
            self.assertIsNotNone(result.task_id)
            self.assertTrue(result.task_id.startswith("TASK-"))
            self.assertIsNotNone(result.plan)
            self.assertIsNotNone(result.task)
            self.assertEqual(result.task.project_id, "cuu-gioi")
            self.assertEqual(result.error, None)
            # Task persisted
            saved = mgr.get_task(result.task_id)
            self.assertIsNotNone(saved)
        finally:
            import shutil
            shutil.rmtree(tasks_dir)

    def test_run_with_execute(self):
        """run() with auto_execute=True produces COMPLETED or VERIFIED."""
        tasks_dir = make_temp_tasks_dir()
        try:
            mgr = TaskManager(tasks_dir=tasks_dir)
            executor = _ExecClass(
                task_manager=mgr,
                auto_execute=True,
            )
            result = executor.run("cuu-gioi", "Inspect the project")

            self.assertIn(result.status, ("COMPLETED", "VERIFIED"))
            self.assertIsNotNone(result.task)
            self.assertEqual(result.task.status, TaskStatus.COMPLETED)
        finally:
            import shutil
            shutil.rmtree(tasks_dir)

    def test_run_unknown_project(self):
        """Unknown project returns ERROR."""
        tasks_dir = make_temp_tasks_dir()
        try:
            mgr = TaskManager(tasks_dir=tasks_dir)
            executor = _ExecClass(task_manager=mgr, auto_execute=True)
            result = executor.run("nonexistent-project", "Do something")

            self.assertEqual(result.status, "ERROR")
            self.assertIsNone(result.task_id)
            self.assertIsNotNone(result.error)
            self.assertIn("not found", result.error)
        finally:
            import shutil
            shutil.rmtree(tasks_dir)

    def test_run_plan_only_shorthand(self):
        """plan_only() returns PLANNED without executing."""
        tasks_dir = make_temp_tasks_dir()
        try:
            mgr = TaskManager(tasks_dir=tasks_dir)
            executor = _ExecClass(task_manager=mgr, auto_execute=False)
            result = executor.plan_only("cuu-gioi", "Inspect")

            self.assertEqual(result.status, "PLANNED")
            self.assertIsNotNone(result.task_id)
        finally:
            import shutil
            shutil.rmtree(tasks_dir)


# ── AgentExecutor.execute_existing() tests ─────────────────────────────

class TestExecuteExisting(unittest.TestCase):
    """Tests for execute_existing()."""

    def test_execute_existing_task(self):
        """execute_existing() runs a saved task."""
        tasks_dir = make_temp_tasks_dir()
        try:
            mgr = TaskManager(tasks_dir=tasks_dir)
            # Pre-create a task
            task = mgr.create_task(
                project_id="cuu-gioi",
                title="Pre-existing task",
                description="Created directly",
                steps=[
                    TaskStep(
                        type=StepType.INSPECT,
                        title="Inspect project",
                        command="",
                        args=[],
                    ),
                ],
            )
            self.assertEqual(task.status, TaskStatus.PENDING)

            executor = _ExecClass(task_manager=mgr, auto_execute=True)
            result = executor.execute_existing(task.task_id)

            self.assertIn(result.status, ("COMPLETED", "VERIFIED"))
            self.assertEqual(result.task_id, task.task_id)
            self.assertEqual(result.task.status, TaskStatus.COMPLETED)
        finally:
            import shutil
            shutil.rmtree(tasks_dir)

    def test_execute_existing_not_found(self):
        """execute_existing() with unknown task_id returns ERROR."""
        tasks_dir = make_temp_tasks_dir()
        try:
            mgr = TaskManager(tasks_dir=tasks_dir)
            executor = _ExecClass(task_manager=mgr, auto_execute=True)
            result = executor.execute_existing("TASK-DOES-NOT-EXIST")

            self.assertEqual(result.status, "ERROR")
            self.assertIn("not found", result.error)
        finally:
            import shutil
            shutil.rmtree(tasks_dir)

    def test_execute_existing_already_run(self):
        """execute_existing() with already-run task returns ERROR."""
        tasks_dir = make_temp_tasks_dir()
        try:
            mgr = TaskManager(tasks_dir=tasks_dir)
            task = mgr.create_task(
                project_id="cuu-gioi",
                title="Already done",
                description="",
                steps=[TaskStep(type=StepType.INSPECT, title="I")],
            )
            # Mark as already run
            task.status = TaskStatus.COMPLETED
            mgr.update_task(task)

            executor = _ExecClass(task_manager=mgr, auto_execute=True)
            result = executor.execute_existing(task.task_id)

            self.assertEqual(result.status, "ERROR")
            self.assertIn("cannot run", result.error)
        finally:
            import shutil
            shutil.rmtree(tasks_dir)


# ── Status mapping tests ────────────────────────────────────────────────

class TestStatusMapping(unittest.TestCase):
    """Tests for _status_from_task()."""

    def test_status_from_task_verified(self):
        """COMPLETED + verified=True → VERIFIED."""
        tasks_dir = make_temp_tasks_dir()
        try:
            mgr = TaskManager(tasks_dir=tasks_dir)
            executor = _ExecClass(task_manager=mgr, auto_execute=False)

            task = Task(
                task_id="TASK-0001",
                project_id="proj-x",
                title="Test",
                status=TaskStatus.COMPLETED,
            )
            task.verification = type("V", (), {"verified": True})()

            status = executor._status_from_task(task)
            self.assertEqual(status, "VERIFIED")
        finally:
            import shutil
            shutil.rmtree(tasks_dir)

    def test_status_from_task_completed_not_verified(self):
        """COMPLETED + verified=False → COMPLETED."""
        tasks_dir = make_temp_tasks_dir()
        try:
            mgr = TaskManager(tasks_dir=tasks_dir)
            executor = _ExecClass(task_manager=mgr, auto_execute=False)

            task = Task(
                task_id="TASK-0001",
                project_id="proj-x",
                title="Test",
                status=TaskStatus.COMPLETED,
            )
            task.verification = type("V", (), {"verified": False})()

            status = executor._status_from_task(task)
            self.assertEqual(status, "COMPLETED")
        finally:
            import shutil
            shutil.rmtree(tasks_dir)

    def test_status_from_task_failed(self):
        """FAILED → FAILED."""
        tasks_dir = make_temp_tasks_dir()
        try:
            mgr = TaskManager(tasks_dir=tasks_dir)
            executor = _ExecClass(task_manager=mgr, auto_execute=False)

            task = Task(
                task_id="TASK-0001",
                project_id="proj-x",
                title="Test",
                status=TaskStatus.FAILED,
            )

            status = executor._status_from_task(task)
            self.assertEqual(status, "FAILED")
        finally:
            import shutil
            shutil.rmtree(tasks_dir)


# ── CLI smoke tests ────────────────────────────────────────────────────

class TestCLISmoke(unittest.TestCase):
    """Smoke tests for CLI module."""

    def test_cli_import(self):
        """CLI module can be imported."""
        from core.executor.cli import main, BANNER, HELP
        self.assertIn("Executor", BANNER)
        self.assertIsInstance(HELP, str)

    def test_cli_run_goal_end_to_end(self):
        """CLI: goal → plan → task → execute → verify → result."""
        import io, contextlib
        from core.executor.cli import run_goal

        tasks_dir = make_temp_tasks_dir()
        try:
            mgr = TaskManager(tasks_dir=tasks_dir)
            from core.executor.executor import AgentExecutor
            # Patch the default TaskManager via env-free injection by mocking
            import core.executor.cli as cli_mod
            orig_init = AgentExecutor.__init__

            def patched_init(self, **kwargs):
                kwargs.setdefault("task_manager", mgr)
                orig_init(self, **kwargs)
            AgentExecutor.__init__ = patched_init
            try:
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    run_goal("cuu-gioi", "Inspect the project", no_execute=False)
                out = buf.getvalue()
            finally:
                AgentExecutor.__init__ = orig_init

            self.assertIn("Status", out)
            self.assertIn("TASK-", out)
            # Final result must be either COMPLETED or VERIFIED
            self.assertTrue(
                "VERIFIED" in out or "COMPLETED" in out,
                f"Expected VERIFIED/COMPLETED in output, got:\n{out}",
            )
        finally:
            import shutil
            shutil.rmtree(tasks_dir)


# ── Test runner ─────────────────────────────────────────────────────────

def run_tests() -> bool:
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == "__main__":
    sys.exit(0 if run_tests() else 1)
