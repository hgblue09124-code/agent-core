# core/runtime/state.py
"""Agent Loop State Machine & Data Models — closed-loop Personal Agent runtime state.

Phases:
    BOOTSTRAP → OBSERVE → RETRIEVE → REASON → PLAN → DECIDE → AUTHORIZE →
    EXECUTE → OBSERVE_RESULT → VERIFY → LEARN → REPLAN / WAITING_FOR_USER / CONTINUE / COMPLETE / FAILED
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


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
    BLOCKED          = "BLOCKED"
    BUDGET_EXCEEDED  = "BUDGET_EXCEEDED"


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

    def now_str(self) -> str:
        return datetime.now(timezone.utc).isoformat()

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
        )
