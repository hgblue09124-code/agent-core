# core/runtime/state.py
"""Agent Loop State Machine & Data Models — closed-loop Personal Agent runtime state.

Phases:
    BOOTSTRAP → OBSERVE → RETRIEVE → REASON → PLAN → DECIDE → AUTHORIZE →
    EXECUTE → OBSERVE_RESULT → VERIFY → LEARN → REPLAN / WAITING_FOR_USER / CONTINUE / COMPLETE / FAILED / TIMEOUT / CANCELLED
"""

from __future__ import annotations

import copy
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class InvalidStateTransitionError(Exception):
    """Raised when an illegal state transition is attempted from a terminal state."""
    pass


class AgentLoopPhase(str, Enum):
    """Lifecycle phases for closed-loop execution."""
    BOOTSTRAP       = "BOOTSTRAP"
    OBSERVE         = "OBSERVE"
    RETRIEVE        = "RETRIEVE"
    REASON          = "REASON"
    PLAN            = "PLAN"
    DECIDE          = "DECIDE"
    AUTHORIZE       = "AUTHORIZE"
    EXECUTE         = "EXECUTE"
    OBSERVE_RESULT  = "OBSERVE_RESULT"
    VERIFY          = "VERIFY"
    LEARN           = "LEARN"
    REPLAN          = "REPLAN"
    WAITING_FOR_USER = "WAITING_FOR_USER"
    COMPLETE        = "COMPLETE"
    FAILED          = "FAILED"


class AgentLoopStatus(str, Enum):
    """Terminal and non-terminal execution status."""
    PENDING          = "PENDING"
    RUNNING          = "RUNNING"
    WAITING_FOR_USER = "WAITING_FOR_USER"
    COMPLETED        = "COMPLETED"
    FAILED           = "FAILED"
    CANCELLED        = "CANCELLED"
    TIMEOUT          = "TIMEOUT"
    BLOCKED          = "BLOCKED"
    BUDGET_EXCEEDED  = "BUDGET_EXCEEDED"


TERMINAL_STATUSES = {
    AgentLoopStatus.COMPLETED.value,
    AgentLoopStatus.FAILED.value,
    AgentLoopStatus.CANCELLED.value,
    AgentLoopStatus.TIMEOUT.value,
    AgentLoopStatus.BUDGET_EXCEEDED.value,
}


@dataclass
class TimeBudget:
    """Explicit runtime time budget with deadline and expiration tracking."""
    timeout_seconds: float = 600.0
    start_time: float = field(default_factory=time.time)

    @property
    def deadline(self) -> float:
        return self.start_time + self.timeout_seconds

    def remaining_seconds(self) -> float:
        return max(0.0, self.deadline - time.time())

    def elapsed_seconds(self) -> float:
        return max(0.0, time.time() - self.start_time)

    def is_expired(self) -> bool:
        return time.time() >= self.deadline


@dataclass
class AgentAction:
    """Explicit abstraction for proposed and executed agent actions."""
    action_id: str
    capability: str
    operation: str
    arguments: dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    risk_level: str = "LOW"
    requires_approval: bool = False
    expected_outcome: str = ""

    def to_dict(self) -> dict:
        return {
            "action_id": self.action_id,
            "capability": self.capability,
            "operation": self.operation,
            "arguments": copy.deepcopy(self.arguments),
            "reason": self.reason,
            "risk_level": self.risk_level,
            "requires_approval": self.requires_approval,
            "expected_outcome": self.expected_outcome,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "AgentAction":
        return cls(
            action_id=d["action_id"],
            capability=d["capability"],
            operation=d["operation"],
            arguments=d.get("arguments", {}),
            reason=d.get("reason", ""),
            risk_level=d.get("risk_level", "LOW"),
            requires_approval=d.get("requires_approval", False),
            expected_outcome=d.get("expected_outcome", ""),
        )


@dataclass
class Observation:
    """Structured record of action execution outcome."""
    action_id: str
    timestamp: str
    status: str
    output: Any = None
    error: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "action_id": self.action_id,
            "timestamp": self.timestamp,
            "status": self.status,
            "output": copy.deepcopy(self.output),
            "error": self.error,
            "evidence": copy.deepcopy(self.evidence),
        }


@dataclass
class VerificationResult:
    """Independent verification result for an executed action or goal."""
    verdict: str  # PASS | FAIL | INCONCLUSIVE
    reason: str = ""
    evidence_valid: bool = False
    goal_satisfied: bool = False

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            "reason": self.reason,
            "evidence_valid": self.evidence_valid,
            "goal_satisfied": self.goal_satisfied,
        }


@dataclass
class AgentLoopTelemetry:
    """Runtime instrumentation telemetry for an agent loop run."""
    iterations: int = 0
    actions_executed: int = 0
    llm_calls: int = 0
    tool_calls: int = 0
    retrieval_calls: int = 0
    verification_calls: int = 0
    replans: int = 0
    retries: int = 0
    elapsed_seconds: float = 0.0
    remaining_seconds: float = 0.0
    final_state: str = AgentLoopStatus.PENDING.value

    def to_dict(self) -> dict:
        return {
            "iterations": self.iterations,
            "actions_executed": self.actions_executed,
            "llm_calls": self.llm_calls,
            "tool_calls": self.tool_calls,
            "retrieval_calls": self.retrieval_calls,
            "verification_calls": self.verification_calls,
            "replans": self.replans,
            "retries": self.retries,
            "elapsed_seconds": round(self.elapsed_seconds, 3),
            "remaining_seconds": round(self.remaining_seconds, 3),
            "final_state": self.final_state,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "AgentLoopTelemetry":
        return cls(
            iterations=d.get("iterations", 0),
            actions_executed=d.get("actions_executed", 0),
            llm_calls=d.get("llm_calls", 0),
            tool_calls=d.get("tool_calls", 0),
            retrieval_calls=d.get("retrieval_calls", 0),
            verification_calls=d.get("verification_calls", 0),
            replans=d.get("replans", 0),
            retries=d.get("retries", 0),
            elapsed_seconds=d.get("elapsed_seconds", 0.0),
            remaining_seconds=d.get("remaining_seconds", 0.0),
            final_state=d.get("final_state", AgentLoopStatus.PENDING.value),
        )


@dataclass
class AgentLoopState:
    """Serializable, durable state machine model for Agent Loop."""
    run_id: str
    task_id: str
    goal: str
    project_id: str
    iteration: int = 0
    phase: str = AgentLoopPhase.BOOTSTRAP.value
    status: str = AgentLoopStatus.PENDING.value
    plan: list[str] = field(default_factory=list)
    current_action: Optional[AgentAction] = None
    pending_action: Optional[AgentAction] = None
    observations: list[Observation] = field(default_factory=list)
    verifications: list[VerificationResult] = field(default_factory=list)
    completed_actions: list[AgentAction] = field(default_factory=list)
    failed_actions: list[AgentAction] = field(default_factory=list)
    error: str = ""
    user_approval_state: dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    replan_count: int = 0
    max_iterations: int = 10
    max_retries: int = 2
    max_replans: int = 2
    started_at: str = ""
    updated_at: str = ""
    finished_at: str = ""
    telemetry: AgentLoopTelemetry = field(default_factory=AgentLoopTelemetry)

    def now_str(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_STATUSES

    def transition_to(self, new_status: Union[AgentLoopStatus, str], new_phase: Union[AgentLoopPhase, str], error: str = "") -> None:
        """Safely transition state machine, preventing illegal transitions out of terminal states."""
        target_status = new_status.value if isinstance(new_status, AgentLoopStatus) else new_status
        target_phase = new_phase.value if isinstance(new_phase, AgentLoopPhase) else new_phase

        if self.is_terminal:
            raise InvalidStateTransitionError(
                f"Cannot transition state '{self.run_id}' out of terminal status '{self.status}' to '{target_status}'"
            )

        self.status = target_status
        self.phase = target_phase
        if error:
            self.error = error
        self.updated_at = self.now_str()
        if self.is_terminal and not self.finished_at:
            self.finished_at = self.now_str()

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "task_id": self.task_id,
            "goal": self.goal,
            "project_id": self.project_id,
            "iteration": self.iteration,
            "phase": self.phase,
            "status": self.status,
            "plan": list(self.plan),
            "current_action": self.current_action.to_dict() if self.current_action else None,
            "pending_action": self.pending_action.to_dict() if self.pending_action else None,
            "observations": [o.to_dict() for o in self.observations],
            "verifications": [v.to_dict() for v in self.verifications],
            "completed_actions": [a.to_dict() for a in self.completed_actions],
            "failed_actions": [a.to_dict() for a in self.failed_actions],
            "error": self.error,
            "user_approval_state": copy.deepcopy(self.user_approval_state),
            "retry_count": self.retry_count,
            "replan_count": self.replan_count,
            "max_iterations": self.max_iterations,
            "max_retries": self.max_retries,
            "max_replans": self.max_replans,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
            "finished_at": self.finished_at,
            "telemetry": self.telemetry.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "AgentLoopState":
        d = copy.deepcopy(d)
        curr_act = AgentAction.from_dict(d["current_action"]) if d.get("current_action") else None
        pend_act = AgentAction.from_dict(d["pending_action"]) if d.get("pending_action") else None
        obs_list = [
            Observation(
                action_id=o["action_id"],
                timestamp=o["timestamp"],
                status=o["status"],
                output=o.get("output"),
                error=o.get("error", ""),
                evidence=o.get("evidence", {}),
            )
            for o in d.get("observations", [])
        ]
        verif_list = [
            VerificationResult(
                verdict=v["verdict"],
                reason=v.get("reason", ""),
                evidence_valid=v.get("evidence_valid", False),
                goal_satisfied=v.get("goal_satisfied", False),
            )
            for v in d.get("verifications", [])
        ]
        comp_acts = [AgentAction.from_dict(a) for a in d.get("completed_actions", [])]
        fail_acts = [AgentAction.from_dict(a) for a in d.get("failed_actions", [])]
        telem = AgentLoopTelemetry.from_dict(d.get("telemetry", {}))

        return cls(
            run_id=d["run_id"],
            task_id=d.get("task_id", d["run_id"]),
            goal=d["goal"],
            project_id=d.get("project_id", "default"),
            iteration=d.get("iteration", 0),
            phase=d.get("phase", AgentLoopPhase.BOOTSTRAP.value),
            status=d.get("status", AgentLoopStatus.PENDING.value),
            plan=d.get("plan", []),
            current_action=curr_act,
            pending_action=pend_act,
            observations=obs_list,
            verifications=verif_list,
            completed_actions=comp_acts,
            failed_actions=fail_acts,
            error=d.get("error", ""),
            user_approval_state=d.get("user_approval_state", {}),
            retry_count=d.get("retry_count", 0),
            replan_count=d.get("replan_count", 0),
            max_iterations=d.get("max_iterations", 10),
            max_retries=d.get("max_retries", 2),
            max_replans=d.get("max_replans", 2),
            started_at=d.get("started_at", ""),
            updated_at=d.get("updated_at", ""),
            finished_at=d.get("finished_at", ""),
            telemetry=telem,
        )
