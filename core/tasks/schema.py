# core/tasks/schema.py
"""Task schema — stable dataclass definitions with JSON serialization.

Task Engine v0.1. No LLM. Stdlib only.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


# ── Status ────────────────────────────────────────────────────────────────

class TaskStatus(str, Enum):
    """Task lifecycle states."""
    PENDING    = "PENDING"
    RUNNING    = "RUNNING"
    COMPLETED  = "COMPLETED"
    FAILED     = "FAILED"
    CANCELLED  = "CANCELLED"

    @classmethod
    def valid_transition(cls, from_: "TaskStatus", to: "TaskStatus") -> bool:
        """Allowed transitions."""
        table = {
            cls.PENDING:   {cls.RUNNING, cls.CANCELLED},
            cls.RUNNING:   {cls.COMPLETED, cls.FAILED, cls.CANCELLED},
            cls.COMPLETED: set(),
            cls.FAILED:    set(),
            cls.CANCELLED: set(),
        }
        return to in table.get(from_, set())


# ── Step types ────────────────────────────────────────────────────────────

class StepType(str, Enum):
    """What a TaskStep does."""
    SHELL   = "shell"      # subprocess.run with explicit args
    PYTHON  = "python"     # python -m <module> <args>
    INSPECT = "inspect"    # project inspection (no command)


# ── Individual step ───────────────────────────────────────────────────────

@dataclass
class StepResult:
    """Result of a single TaskStep."""
    stdout: str
    stderr: str
    exit_code: int
    duration_seconds: float
    started_at: str   # ISO 8601
    finished_at: str  # ISO 8601
    error: Optional[str] = None  # any exception message (non-zero or exception)


@dataclass
class TaskStep:
    """A single executable step within a task."""
    type: StepType
    title: str
    description: str = ""
    # For type=shell
    command: str = ""          # the full command string (safe string)
    args: list[str] = field(default_factory=list)
    cwd: str = ""              # working directory override
    # For type=python
    module: str = ""           # e.g. "core.projects.cli"
    py_args: list[str] = field(default_factory=list)
    # For type=inspect
    inspect_project_id: str = ""
    # Verified output expectations
    expect_exit_code: int = 0
    verify_contains: list[str] = field(default_factory=list)
    verify_not_contains: list[str] = field(default_factory=list)
    # Runtime (filled after execution)
    result: Optional[StepResult] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["type"] = self.type.value
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "TaskStep":
        d = dict(d)
        d["type"] = StepType(d["type"])
        return cls(**d)


# ── Verification ─────────────────────────────────────────────────────────

@dataclass
class VerificationResult:
    """Post-execution verification result."""
    verified: bool = False
    checks_performed: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    verified_at: str = ""  # ISO 8601, empty if not verified
    # Aggregate per-step
    all_steps_passed: bool = False
    failed_step_index: int = -1

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "VerificationResult":
        return cls(**d)


# ── Task ─────────────────────────────────────────────────────────────────

@dataclass
class Task:
    """Root task record."""
    task_id: str
    project_id: str
    title: str
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    created_at: str = ""   # ISO 8601
    started_at: str = ""
    completed_at: str = ""
    steps: list[TaskStep] = field(default_factory=list)
    result: Optional[str] = None   # human-readable summary of all steps
    verification: Optional[VerificationResult] = None
    error: Optional[str] = None    # fatal error (task itself failed to start)

    # ── Serialization ─────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        d["steps"] = [s.to_dict() for s in self.steps]
        d["verification"] = self.verification.to_dict() if self.verification else None
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Task":
        d = dict(d)
        d["status"] = TaskStatus(d["status"])
        d["steps"] = [TaskStep.from_dict(s) for s in d.get("steps", [])]
        v = d.get("verification")
        d["verification"] = VerificationResult.from_dict(v) if v else None
        return cls(**d)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    @classmethod
    def from_json(cls, text: str) -> "Task":
        return cls.from_dict(json.loads(text))

    # ── Lifecycle helpers ──────────────────────────────────────────────────

    def mark_running(self) -> None:
        self.status = TaskStatus.RUNNING
        self.started_at = _now()

    def mark_completed(self) -> None:
        self.status = TaskStatus.COMPLETED
        self.completed_at = _now()

    def mark_failed(self, error: str) -> None:
        self.status = TaskStatus.FAILED
        self.error = error
        self.completed_at = _now()

    def mark_cancelled(self) -> None:
        self.status = TaskStatus.CANCELLED
        self.completed_at = _now()

    def can_run(self) -> bool:
        return self.status == TaskStatus.PENDING

    def can_cancel(self) -> bool:
        return self.status in (TaskStatus.PENDING, TaskStatus.RUNNING)

    # ── Step helpers ──────────────────────────────────────────────────────

    def add_step(self, step: TaskStep) -> None:
        self.steps.append(step)

    def step_summary(self) -> str:
        if not self.steps:
            return "(no steps)"
        passed = 0
        failed = 0
        pending = 0
        for s in self.steps:
            if s.result is None:
                pending += 1
                continue
            ec = getattr(s.result, "exit_code", None)
            if ec is None and isinstance(s.result, dict):
                ec = s.result.get("exit_code")
            if ec == 0:
                passed += 1
            else:
                failed += 1
        return f"{passed} passed, {failed} failed, {pending} pending"

    def total_duration(self) -> float:
        total = 0.0
        for s in self.steps:
            if s.result is None:
                continue
            # Handle both dataclass and dict (post-deserialization edge cases)
            d = getattr(s.result, "duration_seconds", None)
            if d is None and isinstance(s.result, dict):
                d = s.result.get("duration_seconds", 0.0)
            if d is not None:
                total += float(d)
        return total


# ── Utilities ─────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_task_id(sequence: int) -> str:
    return f"TASK-{sequence:04d}"
