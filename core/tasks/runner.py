# core/tasks/runner.py
"""Deterministic Task Runner — executes TaskSteps safely.

Task Engine v0.1 — no LLM, no eval(), stdlib subprocess only.

Execution pipeline:
    TASK → LOAD PROJECT → LOAD CONTEXT → EXECUTE STEPS → VERIFY → SAVE
"""

from __future__ import annotations

import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from core.tasks.schema import (
    Task,
    TaskStatus,
    StepType,
    TaskStep,
    StepResult,
    VerificationResult,
)
from core.tasks.context import load_task_context


class TaskRunner:
    """Deterministic task executor. No intelligence. No LLM."""

    def __init__(self, timeout_per_step: float = 60.0):
        """Args:
            timeout_per_step: max seconds per step before SIGKILL.
        """
        self.timeout = timeout_per_step
        self._cancelled = False

    # ── Public API ────────────────────────────────────────────────────────

    def run(self, task: Task) -> Task:
        """Execute a task end-to-end. Returns updated task."""
        from core.tasks.manager import TaskManager
        mgr = TaskManager()

        # Validate
        if not task.can_run():
            task.mark_failed(
                f"Cannot run task in status {task.status.value}"
            )
            mgr.update_task(task)
            return task

        # Mark running
        task.mark_running()
        mgr.update_task(task)

        try:
            # Load project context
            tc = load_task_context(task)

            if tc.load_error:
                task.mark_failed(f"Lỗi project: {tc.load_error}")
                mgr.update_task(task)
                return task

            # Execute steps sequentially
            for i, step in enumerate(task.steps):
                if self._cancelled:
                    task.mark_cancelled()
                    mgr.update_task(task)
                    return task

                result = self._execute_step(step, tc)
                step.result = result

                # Save after each step (partial progress)
                mgr.update_task(task)

                # Stop on first failure unless step allows continuation
                if result.exit_code != 0 and step.expect_exit_code != result.exit_code:
                    task.mark_failed(
                        f"Bước {i+1} thất bại: {step.title} "
                        f"(exit={result.exit_code})"
                    )
                    mgr.update_task(task)
                    return task

            # All steps passed
            task.result = task.step_summary()
            task.mark_completed()
            mgr.update_task(task)

            # Verify
            self._verify(task, tc)
            mgr.update_task(task)

        except Exception as exc:
            task.mark_failed(str(exc))
            mgr.update_task(task)

        return task

    def cancel(self) -> None:
        """Request cancellation of the current run (best-effort)."""
        self._cancelled = True

    # ── Step execution ────────────────────────────────────────────────────

    def _execute_step(self, step: TaskStep, tc) -> StepResult:
        """Execute a single step. Returns StepResult."""
        started = datetime.now(timezone.utc)
        started_str = started.isoformat(timespec="seconds")

        try:
            if step.type == StepType.SHELL:
                return self._run_shell(step, started, started_str)
            elif step.type == StepType.PYTHON:
                return self._run_python(step, started, started_str)
            elif step.type == StepType.INSPECT:
                return self._run_inspect(step, started, started_str, tc)
            else:
                return StepResult(
                    stdout="",
                    stderr=f"Unknown step type: {step.type}",
                    exit_code=1,
                    duration_seconds=0.0,
                    started_at=started_str,
                    finished_at=started_str,
                    error=f"Unknown type: {step.type}",
                )
        except Exception as exc:
            finished = datetime.now(timezone.utc)
            return StepResult(
                stdout="",
                stderr=str(exc),
                exit_code=1,
                duration_seconds=(finished - started).total_seconds(),
                started_at=started_str,
                finished_at=finished.isoformat(timespec="seconds"),
                error=str(exc),
            )

    def _run_shell(
        self,
        step: TaskStep,
        started: datetime,
        started_str: str,
    ) -> StepResult:
        """Execute a shell command with explicit arguments (no shell=True)."""
        if not step.args:
            # Fallback: use command string split on whitespace (safe for simple cases)
            cmd_parts = step.command.split()
        else:
            cmd_parts = [step.command] + list(step.args)

        cwd = step.cwd if step.cwd else None

        proc = subprocess.run(
            cmd_parts,
            capture_output=True,
            text=True,
            timeout=self.timeout,
            cwd=cwd,
            # Do NOT use shell=True to avoid injection
        )

        finished = datetime.now(timezone.utc)
        return StepResult(
            stdout=proc.stdout,
            stderr=proc.stderr,
            exit_code=proc.returncode,
            duration_seconds=(finished - started).total_seconds(),
            started_at=started_str,
            finished_at=finished.isoformat(timespec="seconds"),
        )

    def _run_python(
        self,
        step: TaskStep,
        started: datetime,
        started_str: str,
    ) -> StepResult:
        """Execute a Python module via python -m."""
        # Find python executable (sys.executable can be empty in some envs)
        python_exe = sys.executable
        if not python_exe or not Path(python_exe).exists():
            # Fallback: try to find python3 in PATH or common locations
            import shutil
            python_exe = shutil.which("python3") or "/usr/bin/python3"

        cmd = [python_exe, "-m"]
        if step.module:
            cmd.append(step.module)
        else:
            cmd.append(step.command)
        cmd.extend(step.py_args)

        cwd = step.cwd if step.cwd else None

        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=self.timeout,
            cwd=cwd,
        )

        finished = datetime.now(timezone.utc)
        return StepResult(
            stdout=proc.stdout,
            stderr=proc.stderr,
            exit_code=proc.returncode,
            duration_seconds=(finished - started).total_seconds(),
            started_at=started_str,
            finished_at=finished.isoformat(timespec="seconds"),
        )

    def _run_inspect(
        self,
        step: TaskStep,
        started: datetime,
        started_str: str,
        tc,
    ) -> StepResult:
        """Run project inspection, return context summary as stdout."""
        # Use ProjectManager to load details about the project
        from core.projects.manager import ProjectManager
        mgr = ProjectManager()
        proj = mgr.get(step.inspect_project_id or tc.project_id)

        if not proj:
            finished = datetime.now(timezone.utc)
            return StepResult(
                stdout="",
                stderr=f"Project not found: {step.inspect_project_id}",
                exit_code=1,
                duration_seconds=(finished - started).total_seconds(),
                started_at=started_str,
                finished_at=finished.isoformat(timespec="seconds"),
                error="project not found",
            )

        # Build summary
        lines = [
            f"Project: {proj.name}",
            f"ID: {proj.project_id}",
            f"Root: {proj.root_path}",
            f"Status: {proj.status}",
            "",
        ]

        docs = mgr.locate_all_documents(proj.project_id)
        for key, path in docs.items():
            if path and Path(path).exists():
                lines.append(f"  ✓ {key}: {path} ({Path(path).stat().st_size} bytes)")
            else:
                lines.append(f"  ✗ {key}: not found")

        finished = datetime.now(timezone.utc)
        stdout = "\n".join(lines)

        return StepResult(
            stdout=stdout,
            stderr="",
            exit_code=0,
            duration_seconds=(finished - started).total_seconds(),
            started_at=started_str,
            finished_at=finished.isoformat(timespec="seconds"),
        )

    # ── Verification ──────────────────────────────────────────────────────

    def _verify(self, task: Task, tc) -> None:
        """Run verification checks on a COMPLETED task.

        COMPLETED != VERIFIED.
        A task can be COMPLETED but not yet VERIFIED.
        """
        checks: list[str] = []
        failures: list[str] = []
        all_passed = True
        failed_idx = -1

        for i, step in enumerate(task.steps):
            if step.result is None:
                checks.append(f"Bước {i+1}: chưa chạy")
                all_passed = False
                failed_idx = i
                continue

            r = step.result

            # Check exit code
            expected = step.expect_exit_code
            actual = r.exit_code
            check_desc = f"Bước {i+1} [{step.title}]: exit={actual}"
            checks.append(check_desc)

            if expected != actual:
                failures.append(
                    f"Bước {i+1}: exit code {actual} != {expected}"
                )
                all_passed = False
                failed_idx = i
                continue

            # Check stdout contains
            for needle in step.verify_contains:
                if needle not in r.stdout:
                    failures.append(
                        f"Bước {i+1}: expected stdout to contain: {needle!r}"
                    )
                    all_passed = False
                    failed_idx = i

            # Check stdout NOT contains
            for forbid in step.verify_not_contains:
                if forbid in r.stdout:
                    failures.append(
                        f"Bước {i+1}: stdout should NOT contain: {forbid!r}"
                    )
                    all_passed = False
                    failed_idx = i

        # Project context verification
        checks.append("Project context loaded")
        if not tc.project_exists:
            failures.append("Project root path does not exist")
            all_passed = False

        now = datetime.now(timezone.utc).isoformat(timespec="seconds")

        task.verification = VerificationResult(
            verified=all_passed,
            checks_performed=checks,
            failures=failures,
            verified_at=now,
            all_steps_passed=all_passed,
            failed_step_index=failed_idx,
        )
