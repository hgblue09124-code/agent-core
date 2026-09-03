#!/usr/bin/env python3
# tests/test_task_engine.py
"""Task Engine v0.1 — unit tests.

Run: python tests/test_task_engine.py
Or: python -m unittest discover -v

Stdlib only. No external dependencies.
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

from core.tasks.schema import (
    Task, TaskStatus, StepType, TaskStep,
    StepResult, VerificationResult, new_task_id,
)
from core.tasks.manager import TaskManager
from core.tasks.context import TaskContext, load_task_context
from core.tasks.runner import TaskRunner


# ── Fixtures ───────────────────────────────────────────────────────────────

TASK_MANAGER_TMPDIR: Path = Path(tempfile.mkdtemp(prefix="task_engine_test_"))

# A valid task dict for testing
VALID_TASK_DATA = {
    "task_id": "TASK-9999",
    "project_id": "cuu-gioi",
    "title": "Test Task",
    "description": "A test task",
    "status": "PENDING",
    "created_at": "2026-09-02T12:00:00+00:00",
    "started_at": "",
    "completed_at": "",
    "steps": [],
    "result": None,
    "verification": None,
    "error": None,
}


# ── Schema tests ───────────────────────────────────────────────────────────

class TestSchema(unittest.TestCase):
    """Tests for Task schema, serialization, and lifecycle."""

    def test_new_task_id_format(self):
        """Task IDs are zero-padded 4 digits."""
        self.assertEqual(new_task_id(1), "TASK-0001")
        self.assertEqual(new_task_id(42), "TASK-0042")
        self.assertEqual(new_task_id(9999), "TASK-9999")

    def test_task_status_valid_transitions(self):
        """Valid transitions are allowed, invalid are rejected."""
        self.assertTrue(TaskStatus.valid_transition(TaskStatus.PENDING, TaskStatus.RUNNING))
        self.assertTrue(TaskStatus.valid_transition(TaskStatus.PENDING, TaskStatus.CANCELLED))
        self.assertTrue(TaskStatus.valid_transition(TaskStatus.RUNNING, TaskStatus.COMPLETED))
        self.assertTrue(TaskStatus.valid_transition(TaskStatus.RUNNING, TaskStatus.FAILED))
        self.assertFalse(TaskStatus.valid_transition(TaskStatus.COMPLETED, TaskStatus.RUNNING))
        self.assertFalse(TaskStatus.valid_transition(TaskStatus.FAILED, TaskStatus.COMPLETED))

    def test_task_status_is_string_enum(self):
        """TaskStatus values are usable as strings."""
        self.assertEqual(TaskStatus.PENDING.value, "PENDING")
        self.assertEqual(TaskStatus.RUNNING.value, "RUNNING")  # uppercase by spec

    def test_task_to_dict_roundtrip(self):
        """Task.to_dict() → from_dict() is lossless."""
        t = Task(
            task_id="TASK-0010",
            project_id="proj-a",
            title="Roundtrip Test",
            description="Testing",
            status=TaskStatus.PENDING,
            created_at="2026-01-01T00:00:00+00:00",
            steps=[],
        )
        d = t.to_dict()
        restored = Task.from_dict(d)
        self.assertEqual(restored.task_id, t.task_id)
        self.assertEqual(restored.status, t.status)
        self.assertEqual(restored.project_id, t.project_id)

    def test_task_to_json_roundtrip(self):
        """Task.to_json() → from_json() is lossless."""
        t = Task(
            task_id="TASK-0011",
            project_id="proj-b",
            title="JSON Roundtrip",
            description="",
            status=TaskStatus.RUNNING,
            created_at="2026-01-01T00:00:00+00:00",
            steps=[],
        )
        json_str = t.to_json()
        restored = Task.from_json(json_str)
        self.assertEqual(restored.task_id, "TASK-0011")
        self.assertIsInstance(json.loads(json_str), dict)  # valid JSON

    def test_task_mark_running_sets_time(self):
        """mark_running() updates status and started_at."""
        t = Task(
            task_id="TASK-0012",
            project_id="p",
            title="t",
            status=TaskStatus.PENDING,
            created_at="2026-01-01T00:00:00+00:00",
        )
        t.mark_running()
        self.assertEqual(t.status, TaskStatus.RUNNING)
        self.assertNotEqual(t.started_at, "")

    def test_task_mark_completed_sets_time(self):
        """mark_completed() updates status and completed_at."""
        t = Task(task_id="TASK-0013", project_id="p", title="t",
                 created_at="2026-01-01T00:00:00+00:00")
        t.mark_completed()
        self.assertEqual(t.status, TaskStatus.COMPLETED)
        self.assertNotEqual(t.completed_at, "")

    def test_task_mark_failed_sets_error(self):
        """mark_failed() sets status and error."""
        t = Task(task_id="TASK-0014", project_id="p", title="t",
                 created_at="2026-01-01T00:00:00+00:00")
        t.mark_failed("Something went wrong")
        self.assertEqual(t.status, TaskStatus.FAILED)
        self.assertEqual(t.error, "Something went wrong")

    def test_task_can_run_only_pending(self):
        """can_run() is True only for PENDING tasks."""
        t = Task(task_id="TASK-0015", project_id="p", title="t",
                 created_at="2026-01-01T00:00:00+00:00")
        self.assertTrue(t.can_run())
        t.mark_running()
        self.assertFalse(t.can_run())
        t.status = TaskStatus.FAILED  # override
        self.assertFalse(t.can_run())

    def test_task_can_cancel_pending_or_running(self):
        """can_cancel() is True for PENDING and RUNNING."""
        t = Task(task_id="TASK-0016", project_id="p", title="t",
                 created_at="2026-01-01T00:00:00+00:00")
        self.assertTrue(t.can_cancel())
        t.mark_running()
        self.assertTrue(t.can_cancel())
        t.status = TaskStatus.COMPLETED
        self.assertFalse(t.can_cancel())

    def test_task_step_to_dict_roundtrip(self):
        """TaskStep serializes and deserializes correctly."""
        step = TaskStep(
            type=StepType.SHELL,
            title="Echo test",
            command="echo",
            args=["hello"],
            expect_exit_code=0,
            verify_contains=["hello"],
        )
        d = step.to_dict()
        restored = TaskStep.from_dict(d)
        self.assertEqual(restored.type, StepType.SHELL)
        self.assertEqual(restored.command, "echo")
        self.assertEqual(restored.args, ["hello"])
        self.assertEqual(restored.expect_exit_code, 0)
        self.assertEqual(restored.verify_contains, ["hello"])

    def test_task_step_summary_counts(self):
        """step_summary() counts passed/failed/pending."""
        t = Task(task_id="TASK-0017", project_id="p", title="t",
                 created_at="2026-01-01T00:00:00+00:00")
        t.steps = [
            TaskStep(type=StepType.INSPECT, title="s1"),
            TaskStep(type=StepType.INSPECT, title="s2"),
        ]
        t.steps[0].result = StepResult(
            stdout="ok", stderr="", exit_code=0,
            duration_seconds=0.1,
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:00:00+00:00",
        )
        t.steps[1].result = StepResult(
            stdout="", stderr="err", exit_code=1,
            duration_seconds=0.1,
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:00:00+00:00",
        )
        summary = t.step_summary()
        self.assertIn("1 passed", summary)
        self.assertIn("1 failed", summary)
        self.assertIn("0 pending", summary)

    def test_task_total_duration(self):
        """total_duration() sums all step durations."""
        t = Task(task_id="TASK-0018", project_id="p", title="t",
                 created_at="2026-01-01T00:00:00+00:00")
        t.steps = [TaskStep(type=StepType.INSPECT, title="s1")]
        t.steps[0].result = StepResult(
            stdout="", stderr="", exit_code=0,
            duration_seconds=1.5,
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:00:00+00:00",
        )
        self.assertAlmostEqual(t.total_duration(), 1.5)


# ── Task Manager tests ───────────────────────────────────────────────────────

class TestTaskManager(unittest.TestCase):
    """Tests for TaskManager JSON persistence."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="tm_test_"))
        self.mgr = TaskManager(tasks_dir=str(self.tmpdir))

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_create_task_assigns_id(self):
        """create_task() assigns a unique TASK-XXXX ID."""
        t = self.mgr.create_task("proj-x", "My Task", "A description")
        self.assertTrue(t.task_id.startswith("TASK-"))
        self.assertEqual(t.project_id, "proj-x")
        self.assertEqual(t.title, "My Task")
        self.assertEqual(t.description, "A description")
        self.assertEqual(t.status, TaskStatus.PENDING)
        self.assertNotEqual(t.created_at, "")

    def test_create_task_persists(self):
        """Created task is retrievable from disk."""
        t = self.mgr.create_task("proj-x", "Persist Test")
        retrieved = self.mgr.get_task(t.task_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.task_id, t.task_id)

    def test_task_ids_are_incremental(self):
        """Each create_task() increments the ID."""
        t1 = self.mgr.create_task("p", "Task 1")
        t2 = self.mgr.create_task("p", "Task 2")
        t3 = self.mgr.create_task("p", "Task 3")
        self.assertNotEqual(t1.task_id, t2.task_id)
        self.assertNotEqual(t2.task_id, t3.task_id)

    def test_get_task_missing_returns_none(self):
        """get_task() returns None for unknown ID."""
        self.assertIsNone(self.mgr.get_task("TASK-99999"))

    def test_list_tasks_all(self):
        """list_tasks() returns all tasks, newest first."""
        self.mgr.create_task("proj-x", "First")
        self.mgr.create_task("proj-x", "Second")
        self.mgr.create_task("proj-x", "Third")
        tasks = self.mgr.list_tasks()
        self.assertEqual(len(tasks), 3)

    def test_list_tasks_filter_by_project(self):
        """list_tasks() filters by project_id."""
        self.mgr.create_task("proj-a", "Task A1")
        self.mgr.create_task("proj-a", "Task A2")
        self.mgr.create_task("proj-b", "Task B1")
        tasks_a = self.mgr.list_tasks(project_id="proj-a")
        tasks_b = self.mgr.list_tasks(project_id="proj-b")
        self.assertEqual(len(tasks_a), 2)
        self.assertEqual(len(tasks_b), 1)
        self.assertEqual(tasks_b[0].project_id, "proj-b")

    def test_list_tasks_filter_by_status(self):
        """list_tasks() filters by status."""
        t = self.mgr.create_task("p", "Filterable")
        t.mark_running()
        self.mgr.update_task(t)
        pending = self.mgr.list_tasks(status=TaskStatus.PENDING)
        running = self.mgr.list_tasks(status=TaskStatus.RUNNING)
        self.assertTrue(all(x.status == TaskStatus.PENDING for x in pending))
        self.assertTrue(all(x.status == TaskStatus.RUNNING for x in running))

    def test_update_task_persists(self):
        """update_task() saves changes to disk."""
        t = self.mgr.create_task("p", "Update Test")
        t.description = "Modified"
        self.mgr.update_task(t)
        retrieved = self.mgr.get_task(t.task_id)
        self.assertEqual(retrieved.description, "Modified")

    def test_delete_task_removes_file(self):
        """delete_task() removes the file and index entry."""
        t = self.mgr.create_task("p", "To Delete")
        task_id = t.task_id
        self.assertIsNotNone(self.mgr.get_task(task_id))
        ok = self.mgr.delete_task(task_id)
        self.assertTrue(ok)
        self.assertIsNone(self.mgr.get_task(task_id))

    def test_delete_missing_task_returns_false(self):
        """delete_task() returns False for unknown ID."""
        self.assertFalse(self.mgr.delete_task("TASK-99999"))

    def test_count_tasks(self):
        """count_tasks() returns the correct number."""
        self.assertEqual(self.mgr.count_tasks(), 0)
        self.mgr.create_task("p", "T1")
        self.mgr.create_task("p", "T2")
        self.assertEqual(self.mgr.count_tasks(), 2)


# ── TaskContext tests ───────────────────────────────────────────────────────

class TestTaskContext(unittest.TestCase):
    """Tests for TaskContext bridging."""

    def test_load_task_context_for_cuu_gioi(self):
        """TaskContext loads cuu-gioi project from registry."""
        mgr = TaskManager(tasks_dir=str(Path(tempfile.mkdtemp(prefix="tc_test_")))
                          if not hasattr(self, '_tmpdir') else self._tmpdir)
        t = Task(
            task_id="TASK-0001",
            project_id="cuu-gioi",
            title="Test",
            created_at="2026-01-01T00:00:00+00:00",
        )
        tc = load_task_context(t)
        self.assertEqual(tc.project_id, "cuu-gioi")
        self.assertTrue(tc.project_exists)
        self.assertIn("Cửu Giới", tc.project_name)

    def test_load_task_context_missing_project(self):
        """TaskContext handles unknown project gracefully."""
        t = Task(
            task_id="TASK-9998",
            project_id="nonexistent-project",
            title="Unknown Project",
            created_at="2026-01-01T00:00:00+00:00",
        )
        tc = load_task_context(t)
        self.assertFalse(tc.project_exists)
        self.assertIn("not found", tc.load_error)


# ── Task Runner tests ───────────────────────────────────────────────────────

class TestTaskRunner(unittest.TestCase):
    """Tests for deterministic command execution."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="runner_test_"))
        self.mgr = TaskManager(tasks_dir=str(self.tmpdir))

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_runner_executes_shell_step_success(self):
        """Runner captures stdout, stderr, exit_code from shell step."""
        task = self.mgr.create_task("cuu-gioi", "Echo Test")
        step = TaskStep(
            type=StepType.SHELL,
            title="Echo hello",
            command="echo",
            args=["hello world"],
            expect_exit_code=0,
        )
        task.add_step(step)
        self.mgr.update_task(task)

        runner = TaskRunner(timeout_per_step=10.0)
        updated = runner.run(task)

        self.assertEqual(updated.status, TaskStatus.COMPLETED)
        self.assertEqual(updated.steps[0].result.exit_code, 0)
        self.assertIn("hello world", updated.steps[0].result.stdout)
        self.assertEqual(updated.steps[0].result.stderr, "")

    def test_runner_executes_shell_step_failure(self):
        """Runner marks task FAILED when shell step returns non-zero."""
        task = self.mgr.create_task("cuu-gioi", "Fail Test")
        step = TaskStep(
            type=StepType.SHELL,
            title="Exit 1",
            command="python3",
            args=["-c", "import sys; sys.exit(1)"],
            expect_exit_code=0,  # expect success, will fail
        )
        task.add_step(step)
        self.mgr.update_task(task)

        runner = TaskRunner(timeout_per_step=10.0)
        updated = runner.run(task)

        self.assertEqual(updated.status, TaskStatus.FAILED)
        self.assertIn("exit=", updated.error)

    def test_runner_executes_python_step(self):
        """Runner executes a Python module step."""
        task = self.mgr.create_task("cuu-gioi", "Python Step Test")
        step = TaskStep(
            type=StepType.PYTHON,
            title="Run projects CLI",
            module="core.projects.cli",
            py_args=["list"],
            expect_exit_code=0,
        )
        task.add_step(step)
        self.mgr.update_task(task)

        runner = TaskRunner(timeout_per_step=30.0)
        updated = runner.run(task)

        self.assertEqual(updated.status, TaskStatus.COMPLETED)
        self.assertEqual(updated.steps[0].result.exit_code, 0)
        self.assertIn("cuu-gioi", updated.steps[0].result.stdout)

    def test_runner_executes_inspect_step(self):
        """Runner executes inspect step and returns project info."""
        task = self.mgr.create_task("cuu-gioi", "Inspect Test")
        step = TaskStep(
            type=StepType.INSPECT,
            title="Inspect project",
            inspect_project_id="cuu-gioi",
            expect_exit_code=0,
        )
        task.add_step(step)
        self.mgr.update_task(task)

        runner = TaskRunner(timeout_per_step=10.0)
        updated = runner.run(task)

        self.assertEqual(updated.status, TaskStatus.COMPLETED)
        self.assertEqual(updated.steps[0].result.exit_code, 0)
        self.assertIn("cuu-gioi", updated.steps[0].result.stdout)

    def test_runner_verification_sets_verified_flag(self):
        """COMPLETED task has verification with verified=True."""
        task = self.mgr.create_task("cuu-gioi", "Verify Test")
        project_root = load_task_context(task).project_root
        step = TaskStep(
            type=StepType.SHELL,
            title="List dir",
            command="ls",
            args=[project_root],
            expect_exit_code=0,
            verify_contains=["AGENT.md"],
        )
        task.add_step(step)
        self.mgr.update_task(task)

        runner = TaskRunner(timeout_per_step=10.0)
        updated = runner.run(task)

        self.assertEqual(updated.status, TaskStatus.COMPLETED)
        self.assertIsNotNone(updated.verification)
        self.assertTrue(updated.verification.verified)
        self.assertTrue(updated.verification.all_steps_passed)

    def test_runner_verification_catches_failure(self):
        """Verification sets verified=False when stdout lacks expected content."""
        task = self.mgr.create_task("cuu-gioi", "Verify Fail Test")
        step = TaskStep(
            type=StepType.SHELL,
            title="Echo hi",
            command="echo",
            args=["hi"],
            expect_exit_code=0,
            verify_contains=["nonexistent-word-xyz"],  # not in "hi"
        )
        task.add_step(step)
        self.mgr.update_task(task)

        runner = TaskRunner(timeout_per_step=10.0)
        updated = runner.run(task)

        # Step exits 0 (matches expect_exit_code=0) → COMPLETED
        # Then verification runs and fails on missing string
        # → verification.verified = False, but status is COMPLETED
        # NOTE: in v0.1, COMPLETED + verification=False is possible
        self.assertEqual(updated.status, TaskStatus.COMPLETED)
        self.assertIsNotNone(updated.verification)
        self.assertFalse(updated.verification.verified)
        self.assertTrue(len(updated.verification.failures) > 0)

    def test_runner_captures_duration(self):
        """Step result includes duration_seconds > 0."""
        task = self.mgr.create_task("cuu-gioi", "Duration Test")
        step = TaskStep(
            type=StepType.SHELL,
            title="Sleep",
            command="/bin/python3",
            args=["-c", "import time; time.sleep(0.1)"],
            expect_exit_code=0,
        )
        task.add_step(step)
        self.mgr.update_task(task)

        runner = TaskRunner(timeout_per_step=10.0)
        updated = runner.run(task)

        if updated.steps[0].result is None:
            self.fail("Step result is None; task status = " + str(updated.status.value))
        self.assertGreater(updated.steps[0].result.duration_seconds, 0)

    def test_runner_task_already_run(self):
        """Cannot re-run a task that is not PENDING."""
        task = self.mgr.create_task("proj-x", "Re-run Test")
        task.mark_running()
        task.mark_completed()
        self.mgr.update_task(task)

        runner = TaskRunner()
        updated = runner.run(task)

        self.assertEqual(updated.status, TaskStatus.FAILED)
        self.assertIn("Cannot run", updated.error)

    def test_runner_unknown_project_fails(self):
        """Task for unknown project fails gracefully."""
        task = Task(
            task_id="TASK-0000",
            project_id="does-not-exist",
            title="Unknown Project Task",
            created_at="2026-01-01T00:00:00+00:00",
        )
        # Save it directly
        self.mgr.create_task("dummy", "dummy")  # init index
        self.mgr.update_task(task)

        runner = TaskRunner()
        updated = runner.run(task)

        self.assertEqual(updated.status, TaskStatus.FAILED)
        self.assertIn("not found", updated.error.lower())

    def test_runner_sequential_steps_all_pass(self):
        """Multiple steps run sequentially; all must pass."""
        task = self.mgr.create_task("cuu-gioi", "Multi-step Test")
        task.add_step(TaskStep(
            type=StepType.SHELL, title="Step 1",
            command="echo", args=["one"], expect_exit_code=0,
        ))
        task.add_step(TaskStep(
            type=StepType.SHELL, title="Step 2",
            command="echo", args=["two"], expect_exit_code=0,
        ))
        self.mgr.update_task(task)

        runner = TaskRunner(timeout_per_step=10.0)
        updated = runner.run(task)

        self.assertEqual(updated.status, TaskStatus.COMPLETED)
        self.assertEqual(len(updated.steps), 2)
        self.assertEqual(updated.steps[0].result.exit_code, 0)
        self.assertEqual(updated.steps[1].result.exit_code, 0)

    def test_runner_stops_on_first_failure(self):
        """If step 1 fails, step 2 is not executed."""
        task = self.mgr.create_task("cuu-gioi", "Stop on Fail Test")
        task.add_step(TaskStep(
            type=StepType.SHELL, title="Failing step",
            command="/bin/python3", args=["-c", "import sys; sys.exit(1)"],
            expect_exit_code=0,
        ))
        task.add_step(TaskStep(
            type=StepType.SHELL, title="Never reached",
            command="echo", args=["should not run"],
            expect_exit_code=0,
        ))
        self.mgr.update_task(task)

        runner = TaskRunner(timeout_per_step=10.0)
        updated = runner.run(task)

        self.assertEqual(updated.status, TaskStatus.FAILED)
        self.assertIsNotNone(updated.steps[0].result)
        self.assertEqual(updated.steps[0].result.exit_code, 1)
        self.assertIsNone(updated.steps[1].result)  # not executed


# ── CLI behavior tests ───────────────────────────────────────────────────────

class TestCLICreate(unittest.TestCase):
    """Smoke tests for CLI module import and basic functions."""

    def test_cli_module_imports(self):
        """CLI module can be imported without error."""
        from core.tasks.cli import main, HELP, BANNER
        self.assertIsInstance(HELP, str)
        self.assertIsInstance(BANNER, str)
        self.assertIn("Task Engine", BANNER)

    def test_runner_imports(self):
        """TaskRunner and all schema classes import cleanly."""
        from core.tasks import TaskRunner, TaskManager, TaskContext
        from core.tasks.schema import Task, TaskStatus, StepType, TaskStep
        self.assertIsNotNone(TaskRunner)
        self.assertIsNotNone(TaskManager)


# ── Test runner ─────────────────────────────────────────────────────────────

def run_tests() -> bool:
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
