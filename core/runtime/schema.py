# core/runtime/schema.py
"""Runtime v0.6 — autonomous execution state & persistence schemas."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


# ── Runtime status ───────────────────────────────────────────────────────

class RunStatus(str, Enum):
    """Explicit terminal states for a runtime run."""
    PENDING     = "PENDING"
    RUNNING     = "RUNNING"
    COMPLETED   = "COMPLETED"
    FAILED      = "FAILED"
    BLOCKED     = "BLOCKED"
    TIMEOUT     = "TIMEOUT"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    INTERRUPTED = "INTERRUPTED"
    UNSAFE      = "UNSAFE"


class RunPhase(str, Enum):
    """Pipeline phases for observability."""
    BOOTSTRAP    = "BOOTSTRAP"
    PLANNING     = "PLANNING"
    REFINING     = "REFINING"
    VALIDATING   = "VALIDATING"
    EXECUTING    = "EXECUTING"
    VERIFYING    = "VERIFYING"
    CHECKPOINT   = "CHECKPOINT"
    RETRY        = "RETRY"
    ESCALATING   = "ESCALATING"
    STOPPED      = "STOPPED"


# ── Checkpoint data ──────────────────────────────────────────────────────

@dataclass
class PhaseMetrics:
    """Token/call budget tracking."""
    llm_calls: int = 0
    estimated_tokens: int = 0
    plan_refinements: int = 0
    retries: int = 0
    checkpoints: int = 0
    internet_calls: int = 0

    def to_dict(self) -> dict:
        return dict(
            llm_calls=self.llm_calls,
            estimated_tokens=self.estimated_tokens,
            plan_refinements=self.plan_refinements,
            retries=self.retries,
            checkpoints=self.checkpoints,
            internet_calls=self.internet_calls,
        )

    @classmethod
    def from_dict(cls, d: dict) -> PhaseMetrics:
        return cls(**{k: d[k] for k in ["llm_calls","estimated_tokens",
                                         "plan_refinements","retries",
                                         "checkpoints","internet_calls"]})


@dataclass
class RunState:
    """Durable checkpoint — the authoritative source of truth for a run.

    All secrets (API keys) are NEVER stored here.
    """
    # Identity
    run_id: str
    goal: str
    project_id: str

    # Plan tracking
    plan_version: int = 0
    plan_json: str = ""       # JSON-serialised Plan (not the Plan object)

    # Execution phase
    phase: str = RunPhase.BOOTSTRAP.value
    current_task_index: int = 0
    completed_task_ids: list[str] = field(default_factory=list)
    failed_task_ids: list[str] = field(default_factory=list)

    # Recovery
    attempt_count: int = 0
    retry_count: int = 0
    retry_reason: str = ""
    recovery_point: str = ""   # human-readable resume hint

    # Observability
    started_at: str = ""
    last_checkpoint_at: str = ""
    finished_at: str = ""
    last_observation: str = ""  # last non-empty stdout/stderr snippet

    # Metrics
    metrics: PhaseMetrics = field(default_factory=PhaseMetrics)

    # Status
    status: str = RunStatus.PENDING.value
    error: str = ""

    # Budget constraints (copied from RuntimeConfig at start)
    max_llm_calls: int = 100
    max_token_budget: int = 100_000
    max_plan_refinements: int = 2
    max_retries: int = 3
    max_runtime_seconds: int = 28800
    internet_policy: str = "off"  # off | on | required

    # Serialisation helpers
    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "goal": self.goal,
            "project_id": self.project_id,
            "plan_version": self.plan_version,
            "plan_json": self.plan_json,
            "phase": self.phase,
            "current_task_index": self.current_task_index,
            "completed_task_ids": self.completed_task_ids,
            "failed_task_ids": self.failed_task_ids,
            "attempt_count": self.attempt_count,
            "retry_count": self.retry_count,
            "retry_reason": self.retry_reason,
            "recovery_point": self.recovery_point,
            "started_at": self.started_at,
            "last_checkpoint_at": self.last_checkpoint_at,
            "finished_at": self.finished_at,
            "last_observation": self.last_observation,
            "metrics": self.metrics.to_dict(),
            "status": self.status,
            "error": self.error,
            "max_llm_calls": self.max_llm_calls,
            "max_token_budget": self.max_token_budget,
            "max_plan_refinements": self.max_plan_refinements,
            "max_retries": self.max_retries,
            "max_runtime_seconds": self.max_runtime_seconds,
            "internet_policy": self.internet_policy,
        }

    @classmethod
    def from_dict(cls, d: dict) -> RunState:
        d = dict(d)
        d["metrics"] = PhaseMetrics.from_dict(d.get("metrics", {}))
        return cls(**d)

    # ── Convenience helpers ──────────────────────────────────────────

    def now_str(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def new_checkpoint(self) -> RunState:
        """Return a copy with updated checkpoint timestamp."""
        import copy
        s = copy.deepcopy(self)
        s.last_checkpoint_at = self.now_str()
        s.metrics.checkpoints += 1
        return s

    def transition(self, status: RunStatus, phase: RunPhase,
                   error: str = "", observation: str = "") -> RunState:
        """Return a copy with updated status/phase."""
        import copy
        s = copy.deepcopy(self)
        s.status = status.value
        s.phase = phase.value
        if error:
            s.error = error
        if observation and len(observation) > len(s.last_observation):
            s.last_observation = observation[-500:]
        return s
