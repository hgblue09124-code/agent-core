# core/tasks/schema.py
"""Task schema — stable dataclass definitions with JSON serialization.

Task Engine v0.1. No LLM. Stdlib only.

Deep Task Prompt Primitive
===========================
A DeepTaskPrompt captures how GPT (Director) structurally specifies a coding
task for NanoBot. It is NOT a prompt template — it is a structured contract
representing the decision structure behind a high-quality task.

Lifecycle:
    GPT Reasoning → DeepTaskPrompt → Task → Execution → Evidence
                → Evaluation → Lesson → Reusable Primitive

A generated prompt is NOT automatically knowledge. The lifecycle enforces
that evaluation evidence is required before any learning claim.
"""

from __future__ import annotations

import json
import re
import time as _time
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


# ── Task Construction Contract ──────────────────────────────────────────
# First-class kernel capability: define WHAT is built before execution.

_VALID_ACTIONS = frozenset({"inspect", "reason", "modify", "test", "verify",
                             "report", "retry", "replan", "stop"})


@dataclass
class TaskConstructionContract:
    """Structured contract defining WHAT must be built before execution.

    Task Construction is a first-class kernel capability. This contract
    is authored by Administrator/GPT before the Task Engine runs.

    Architecture:
        Administrator/GPT
               ↓
        Task Construction (this contract)
               ↓
        Structured Task Contract
               ↓
        Task Engine
               ↓
        NanoBot Execution
               ↓
        Verification
               ↓
        Experience / Knowledge

    The contract is purely declarative. It does NOT execute, does NOT
    call LLM, does NOT dispatch NanoBot. It is a kernel primitive.

    Lifecycle: authored -> validated -> attached to Task -> executed
    -> verified -> experience/knowledge captured.

    Compatible with existing Evaluation evidence model.
    """
    # ── Identity ─────────────────────────────────────────────────────────
    contract_id: str = ""              # unique stable id (e.g. "TCC-00001")
    title: str = ""                    # short human-readable title

    # ── Objective ───────────────────────────────────────────────────────
    objective: str = ""                 # fundamental goal of this task
    rationale: str = ""               # why this objective matters

    # ── Context ─────────────────────────────────────────────────────────
    context: list[str] = field(default_factory=list)   # relevant files / state
    prerequisites: list[str] = field(default_factory=list)  # preconditions

    # ── Scope ───────────────────────────────────────────────────────────
    scope: list[str] = field(default_factory=list)     # explicit boundaries
    files_in_scope: list[str] = field(default_factory=list)  # files to modify
    files_not_in_scope: list[str] = field(default_factory=list)  # off-limits

    # ── Constraints ──────────────────────────────────────────────────────
    must: list[str] = field(default_factory=list)      # required actions
    must_not: list[str] = field(default_factory=list)  # forbidden actions
    constraints: list[str] = field(default_factory=list)  # general constraints

    # ── Execution Guidance ──────────────────────────────────────────────
    guidance: str = ""                 # recommended approach / strategy
    reasoning_steps: list[str] = field(
        default_factory=list
    )                                  # e.g. ["inspect", "reason", "modify", "test"]

    # ── Acceptance Criteria ──────────────────────────────────────────────
    acceptance_criteria: list[str] = field(default_factory=list)
    done_when: str = ""               # natural-language finish condition

    # ── Verification Requirements ───────────────────────────────────────
    verification_requirements: list[str] = field(default_factory=list)
    verify_with: list[str] = field(default_factory=list)  # commands / tools
    expected_evidence_types: list[str] = field(
        default_factory=list
    )                                  # e.g. TEST, COMMAND_RESULT, FILE_STATE

    # ── Evidence Requirements ────────────────────────────────────────────
    required_evidence: list[str] = field(default_factory=list)
    evidence_after_success: list[str] = field(default_factory=list)
    evidence_after_failure: list[str] = field(default_factory=list)

    # ── Failure Handling ─────────────────────────────────────────────────
    failure_protocol: str = ""          # what to do on failure
    failure_actions: list[str] = field(default_factory=list)  # inspect → retry → replan
    max_retries: int = 3             # bounded retry count
    recovery_strategy: str = ""        # how to recover from failure

    # ── Expected Outcome ────────────────────────────────────────────────
    expected_outcome: str = ""         # explicit outcome description
    expected_changed_files: list[str] = field(default_factory=list)
    expected_verification: str = ""    # what verification should demonstrate

    # ── Provenance ──────────────────────────────────────────────────────
    authored_by: str = "gpt-administrator"
    authored_at: str = ""
    schema_version: int = 1

    # ── Validation ──────────────────────────────────────────────────────

    def validate(self) -> tuple[bool, str]:
        """Deterministic validation. Returns (valid, reason)."""
        if not self.contract_id or not _ID_RE.match(self.contract_id):
            return False, f"contract_id must match {_ID_RE.pattern}"
        if not self.objective or not self.objective.strip():
            return False, "objective is required"
        if not self.acceptance_criteria and not self.done_when:
            return False, "Either acceptance_criteria or done_when is required"
        if not self.expected_evidence_types:
            return False, "expected_evidence_types is required"
        for et in self.expected_evidence_types:
            if et not in DTP_EVIDENCE_TYPES:
                return False, f"Unknown evidence type: {et}"
        for fa in self.failure_actions:
            if fa not in _VALID_ACTIONS:
                return False, f"Unknown failure_action: {fa!r}"
        if self.max_retries < 0:
            return False, "max_retries must be non-negative"
        return True, ""

    # ── Serialization ───────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "TaskConstructionContract":
        return cls(**d)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    @classmethod
    def from_json(cls, text: str) -> "TaskConstructionContract":
        return cls.from_dict(json.loads(text))

    # ── Helpers ─────────────────────────────────────────────────────────

    def is_valid(self) -> bool:
        valid, _ = self.validate()
        return valid

    def construction_summary(self) -> str:
        """Human-readable summary for logging."""
        return (
            f"TaskConstructionContract[{self.contract_id}] "
            f"objective={self.objective[:60]!r} "
            f"scope={len(self.scope)} files "
            f"acceptance_criteria={len(self.acceptance_criteria)} "
            f"max_retries={self.max_retries}"
        )


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
    # Optional structured construction contract (Task Construction layer).
    # When present, this defines WHAT must be built before execution begins.
    # It does NOT change existing Task semantics — purely additive.
    construction: Optional["TaskConstructionContract"] = None

    # ── Serialization ─────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        d["steps"] = [s.to_dict() for s in self.steps]
        d["verification"] = self.verification.to_dict() if self.verification else None
        # asdict() already recursively converts nested dataclasses to dicts,
        # so construction is already a dict here. Leave it as-is.
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Task":
        d = dict(d)
        d["status"] = TaskStatus(d["status"])
        d["steps"] = [TaskStep.from_dict(s) for s in d.get("steps", [])]
        v = d.get("verification")
        d["verification"] = VerificationResult.from_dict(v) if v else None
        c = d.get("construction")
        d["construction"] = (
            TaskConstructionContract.from_dict(c) if isinstance(c, dict) else None
        )
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


# ── Evidence types for Deep Task Prompt ─────────────────────────────────

# Reuse evidence type vocabulary from evaluation schema (avoid duplication).
# Values are strings so no import cycle is needed.
DTP_EVIDENCE_TYPES = (
    "TEST",
    "COMMAND_RESULT",
    "FILE_STATE",
    "RUNTIME_RESULT",
    "REGRESSION_RESULT",
    "COMMIT_STATE",
    "ASSERTION",
)


# ── Deep Task Prompt Primitive ──────────────────────────────────────────

_ID_RE = re.compile(r"^[A-Za-z0-9_\-]{3,64}$")


@dataclass
class DeepTaskPrompt:
    """Structured representation of a GPT-directed coding task.

    Models the full decision structure behind a high-quality NanoBot task:
    - What to achieve (intent + acceptance criteria)
    - Where to act (scope + files)
    - How to act (execution strategy + constraints)
    - What constitutes success (verification requirements)
    - What went wrong if it failed (failure protocol)
    - What was learned (learning capture)
    - What outcome is expected (expected outcome)

    NOT an LLM call. NOT an executor. Pure data with deterministic
    validation. Serializable. Extensible.

    A DeepTaskPrompt is NOT automatically knowledge. It becomes a candidate
    for learning only after evaluation produces evidence of success.
    """
    # ── Identity ──────────────────────────────────────────────────────
    prompt_id: str                  # unique stable id (e.g. "DTP-00001")
    task_id: str                   # associated task id
    project_id: str = ""           # project this prompt targets

    # ── Intent ─────────────────────────────────────────────────────────
    intent: str = ""               # What the task is fundamentally achieving
    goal: str = ""                 # Specific target outcome

    # ── Context ────────────────────────────────────────────────────────
    context: list[str] = field(default_factory=list)   # relevant project state / files
    prerequisites: list[str] = field(default_factory=list)  # preconditions

    # ── Scope ─────────────────────────────────────────────────────────
    scope: list[str] = field(default_factory=list)    # explicit boundaries (files/modules)
    files: list[str] = field(default_factory=list)    # files to touch

    # ── Constraints ────────────────────────────────────────────────────
    must_not: list[str] = field(default_factory=list)  # forbidden actions
    must: list[str] = field(default_factory=list)      # required actions
    constraints: list[str] = field(default_factory=list)  # general constraints

    # ── Execution Strategy ─────────────────────────────────────────────
    strategy: str = ""              # recommended reasoning/execution sequence
    reasoning_steps: list[str] = field(default_factory=list)  # inspect → reason → ...

    # ── Acceptance Criteria ────────────────────────────────────────────
    acceptance_criteria: list[str] = field(default_factory=list)
    done_when: str = ""            # natural-language finish condition

    # ── Verification Requirements ─────────────────────────────────────
    verification_requirements: list[str] = field(default_factory=list)
    verify_with: list[str] = field(default_factory=list)  # command / test names
    expected_evidence_types: list[str] = field(default_factory=list)
    # Reuse EvidenceType vocabulary: TEST, COMMAND_RESULT, FILE_STATE,
    # RUNTIME_RESULT, REGRESSION_RESULT, COMMIT_STATE

    # ── Failure Protocol ───────────────────────────────────────────────
    failure_protocol: str = ""      # what to do on failure
    failure_actions: list[str] = field(default_factory=list)  # inspect → retry → replan
    max_retries: int = 3           # bounded retries
    recovery_strategy: str = ""     # how to recover from failure

    # ── Evidence Requirements ─────────────────────────────────────────
    required_evidence: list[str] = field(default_factory=list)
    evidence_after_success: list[str] = field(default_factory=list)
    evidence_after_failure: list[str] = field(default_factory=list)

    # ── Learning Capture ──────────────────────────────────────────────
    # Filled after execution + evaluation
    observations: list[str] = field(default_factory=list)    # what was observed
    decisions: list[str] = field(default_factory=list)      # key decisions made
    actions_taken: list[str] = field(default_factory=list)  # actions executed
    failure_reason: str = ""       # root cause if failed
    recovery_applied: str = ""     # recovery that was applied
    lesson: str = ""              # reusable lesson / pattern
    reusable_pattern: str = ""     # pattern extracted for future use
    evaluation_id: str = ""       # links to Evaluation that verified this

    # ── Expected Outcome ───────────────────────────────────────────────
    expected_outcome: str = ""      # explicit outcome description
    expected_changed_files: list[str] = field(default_factory=list)
    expected_verification: str = ""  # what verification should show

    # ── Provenance ────────────────────────────────────────────────────
    created_by: str = "gpt-director"   # who authored this prompt
    created_at: str = ""
    schema_version: int = 1

    # ── Validation ────────────────────────────────────────────────────

    def validate(self) -> tuple[bool, str]:
        """Deterministic validation. Returns (valid, reason)."""
        if not self.prompt_id or not _ID_RE.match(self.prompt_id):
            return False, f"prompt_id must match {_ID_RE.pattern}"
        if not self.task_id or not _ID_RE.match(self.task_id):
            return False, f"task_id must match {_ID_RE.pattern}"
        if not self.intent or not self.intent.strip():
            return False, "intent is required"
        if not self.goal or not self.goal.strip():
            return False, "goal is required"
        if not self.acceptance_criteria and not self.done_when:
            return False, "Either acceptance_criteria or done_when is required"
        if not self.expected_evidence_types:
            return False, "expected_evidence_types is required"
        # Validate evidence type values
        for et in self.expected_evidence_types:
            if et not in DTP_EVIDENCE_TYPES:
                return False, f"Unknown evidence type: {et}"
        # Validate failure_actions values
        valid_actions = {"inspect", "reason", "modify", "test", "verify",
                         "report", "retry", "replan", "stop"}
        for fa in self.failure_actions:
            if fa not in valid_actions:
                return False, f"Unknown failure_action: {fa}"
        if self.max_retries < 0:
            return False, "max_retries must be non-negative"
        return True, ""

    # ── Serialization ─────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "DeepTaskPrompt":
        return cls(**d)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    @classmethod
    def from_json(cls, text: str) -> "DeepTaskPrompt":
        return cls.from_dict(json.loads(text))

    # ── Helpers ────────────────────────────────────────────────────────

    def now_str(self) -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def is_valid(self) -> bool:
        valid, _ = self.validate()
        return valid

    def learning_ready(self) -> bool:
        """True only after execution + evaluation produces evidence."""
        return (
            bool(self.lesson)
            and bool(self.evaluation_id)
            and bool(self.reusable_pattern)
        )


# ── ID generation ──────────────────────────────────────────────────────

def new_task_id(sequence: int) -> str:
    return f"TASK-{sequence:04d}"


def new_dtp_id() -> str:
    """Monotonic deep-task-prompt id."""
    return f"DTP-{int(_time.time() * 1000) % 100000:05d}"


# ── Utilities ─────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
