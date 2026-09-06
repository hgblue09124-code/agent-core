# core/runtime/models.py
"""v0.3 Personal Agent Runtime — source-of-truth models.

The Runtime owns these types. The LLM may propose a Decision; it must not
mutate AgentState or Objective status directly.
"""

from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


class InvalidAgentTransitionError(Exception):
    """Raised when the Runtime rejects an illegal AgentState phase change."""


class ObjectiveState(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"


class ObjectiveKind(str, Enum):
    ONE_SHOT = "ONE_SHOT"
    PERSISTENT = "PERSISTENT"


class AgentPhase(str, Enum):
    IDLE = "IDLE"
    OBSERVING = "OBSERVING"
    UNDERSTANDING = "UNDERSTANDING"
    RETRIEVING = "RETRIEVING"
    DECIDING = "DECIDING"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    REMEMBERING = "REMEMBERING"
    WAITING = "WAITING"
    NEEDS_USER = "NEEDS_USER"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PAUSED = "PAUSED"
    WATCHING = "WATCHING"


class RuntimeEventKind(str, Enum):
    USER_INPUT = "USER_INPUT"
    OBJECTIVE_CREATED = "OBJECTIVE_CREATED"
    TASK_COMPLETED = "TASK_COMPLETED"
    EXTERNAL_RESULT = "EXTERNAL_RESULT"
    SCHEDULED = "SCHEDULED"
    INTEGRATION = "INTEGRATION"
    APPROVAL = "APPROVAL"
    STATE_CHANGED = "STATE_CHANGED"


class ActionType(str, Enum):
    NONE = "none"
    REMEMBER = "remember"
    FORGET = "forget"
    RETRIEVE_MEMORY = "retrieve_memory"
    INVOKE_CAPABILITY = "invoke_capability"
    ASK_USER = "ask_user"
    WAIT = "wait"
    FINISH = "finish"
    WATCH = "watch"
    ECHO = "echo"


class ReasoningLevel(str, Enum):
    DETERMINISTIC = "DETERMINISTIC"
    CHEAP = "CHEAP"
    NORMAL = "NORMAL"
    DEEP = "DEEP"


class RecoveryKind(str, Enum):
    RETRY = "RETRY"
    REPLAN = "REPLAN"
    WAIT = "WAIT"
    ASK_USER = "ASK_USER"
    FAIL = "FAIL"


class FailureClass(str, Enum):
    TRANSIENT = "TRANSIENT"
    PERMANENT = "PERMANENT"
    INVALID_ACTION = "INVALID_ACTION"
    MISSING_CONTEXT = "MISSING_CONTEXT"
    MISSING_AUTHORIZATION = "MISSING_AUTHORIZATION"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    VERIFICATION_FAILURE = "VERIFICATION_FAILURE"


OPEN_OBJECTIVE_STATES = {
    ObjectiveState.PENDING.value,
    ObjectiveState.RUNNING.value,
    ObjectiveState.WAITING.value,
    ObjectiveState.BLOCKED.value,
}

TERMINAL_OBJECTIVE_STATES = {
    ObjectiveState.COMPLETED.value,
    ObjectiveState.FAILED.value,
}

# Runtime-owned FSM. LLM output is never an input to this table.
AGENT_PHASE_TRANSITIONS: dict[str, set[str]] = {
    AgentPhase.IDLE.value: {
        AgentPhase.OBSERVING.value,
        AgentPhase.PAUSED.value,
        AgentPhase.IDLE.value,
    },
    AgentPhase.OBSERVING.value: {
        AgentPhase.UNDERSTANDING.value,
        AgentPhase.IDLE.value,
        AgentPhase.WATCHING.value,
        AgentPhase.WAITING.value,
        AgentPhase.FAILED.value,
    },
    AgentPhase.UNDERSTANDING.value: {
        AgentPhase.RETRIEVING.value,
        AgentPhase.IDLE.value,
        AgentPhase.NEEDS_USER.value,
        AgentPhase.FAILED.value,
    },
    AgentPhase.RETRIEVING.value: {
        AgentPhase.DECIDING.value,
        AgentPhase.FAILED.value,
    },
    AgentPhase.DECIDING.value: {
        AgentPhase.EXECUTING.value,
        AgentPhase.NEEDS_USER.value,
        AgentPhase.WAITING.value,
        AgentPhase.WATCHING.value,
        AgentPhase.IDLE.value,
        AgentPhase.FAILED.value,
    },
    AgentPhase.EXECUTING.value: {
        AgentPhase.VERIFYING.value,
        AgentPhase.NEEDS_USER.value,
        AgentPhase.FAILED.value,
    },
    AgentPhase.VERIFYING.value: {
        AgentPhase.REMEMBERING.value,
        AgentPhase.EXECUTING.value,
        AgentPhase.DECIDING.value,
        AgentPhase.NEEDS_USER.value,
        AgentPhase.WAITING.value,
        AgentPhase.FAILED.value,
    },
    AgentPhase.REMEMBERING.value: {
        AgentPhase.IDLE.value,
        AgentPhase.WATCHING.value,
        AgentPhase.WAITING.value,
        AgentPhase.COMPLETED.value,
        AgentPhase.FAILED.value,
    },
    AgentPhase.WAITING.value: {
        AgentPhase.OBSERVING.value,
        AgentPhase.DECIDING.value,
        AgentPhase.IDLE.value,
        AgentPhase.FAILED.value,
    },
    AgentPhase.NEEDS_USER.value: {
        AgentPhase.OBSERVING.value,
        AgentPhase.DECIDING.value,
        AgentPhase.EXECUTING.value,
        AgentPhase.IDLE.value,
        AgentPhase.FAILED.value,
    },
    AgentPhase.WATCHING.value: {
        AgentPhase.OBSERVING.value,
        AgentPhase.IDLE.value,
        AgentPhase.PAUSED.value,
        AgentPhase.WATCHING.value,
    },
    AgentPhase.COMPLETED.value: {
        AgentPhase.IDLE.value,
        AgentPhase.OBSERVING.value,
    },
    AgentPhase.FAILED.value: {
        AgentPhase.IDLE.value,
        AgentPhase.OBSERVING.value,
        AgentPhase.FAILED.value,
    },
    AgentPhase.PAUSED.value: {
        AgentPhase.IDLE.value,
        AgentPhase.OBSERVING.value,
    },
}


@dataclass
class RuntimeBounds:
    """Hard caps for one autonomous cycle. No unbounded loops."""

    max_cycle_iterations: int = 8
    max_retries: int = 2
    max_replans: int = 2
    max_llm_calls: int = 3
    max_context_memories: int = 3
    max_context_chars: int = 1200


@dataclass
class RuntimeEvent:
    """Something the agent may need to react to. Events drive work."""

    event_id: str
    kind: str
    payload: dict[str, Any] = field(default_factory=dict)
    objective_id: str = ""
    timestamp: str = ""
    source: str = "user"

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = utc_now()

    def text(self) -> str:
        payload = self.payload or {}
        return str(payload.get("text") or payload.get("message") or payload.get("action") or "")

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "kind": self.kind,
            "payload": copy.deepcopy(self.payload),
            "objective_id": self.objective_id,
            "timestamp": self.timestamp,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "RuntimeEvent":
        return cls(
            event_id=d["event_id"],
            kind=d.get("kind", RuntimeEventKind.USER_INPUT.value),
            payload=dict(d.get("payload") or {}),
            objective_id=d.get("objective_id", ""),
            timestamp=d.get("timestamp", ""),
            source=d.get("source", "user"),
        )

    @classmethod
    def user_input(cls, text: str, *, source: str = "user") -> "RuntimeEvent":
        return cls(
            event_id=new_id("REV"),
            kind=RuntimeEventKind.USER_INPUT.value,
            payload={"text": text},
            source=source,
        )


@dataclass
class Objective:
    """A durable thing the user wants accomplished or monitored."""

    objective_id: str
    intent: str
    desired_outcome: str = ""
    status: str = ObjectiveState.PENDING.value
    kind: str = ObjectiveKind.ONE_SHOT.value
    constraints: dict[str, Any] = field(default_factory=dict)
    success_criteria: list[str] = field(default_factory=list)
    retry_count: int = 0
    replan_count: int = 0
    last_event_id: str = ""
    last_error: str = ""
    pending_action: Optional[dict[str, Any]] = None
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = utc_now()
        if not self.updated_at:
            self.updated_at = self.created_at
        if not self.desired_outcome:
            self.desired_outcome = self.intent

    @property
    def is_open(self) -> bool:
        return self.status in OPEN_OBJECTIVE_STATES

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_OBJECTIVE_STATES

    def touch(self) -> None:
        self.updated_at = utc_now()

    def to_dict(self) -> dict:
        return {
            "objective_id": self.objective_id,
            "intent": self.intent,
            "desired_outcome": self.desired_outcome,
            "status": self.status,
            "kind": self.kind,
            "constraints": copy.deepcopy(self.constraints),
            "success_criteria": list(self.success_criteria),
            "retry_count": self.retry_count,
            "replan_count": self.replan_count,
            "last_event_id": self.last_event_id,
            "last_error": self.last_error,
            "pending_action": copy.deepcopy(self.pending_action),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Objective":
        return cls(
            objective_id=d["objective_id"],
            intent=d.get("intent", ""),
            desired_outcome=d.get("desired_outcome", ""),
            status=d.get("status", ObjectiveState.PENDING.value),
            kind=d.get("kind", ObjectiveKind.ONE_SHOT.value),
            constraints=dict(d.get("constraints") or {}),
            success_criteria=list(d.get("success_criteria") or []),
            retry_count=int(d.get("retry_count", 0)),
            replan_count=int(d.get("replan_count", 0)),
            last_event_id=d.get("last_event_id", ""),
            last_error=d.get("last_error", ""),
            pending_action=d.get("pending_action"),
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
        )


@dataclass
class AgentState:
    """Persistent agent entity state. Owned exclusively by the Runtime."""

    phase: str = AgentPhase.IDLE.value
    active_objective_id: Optional[str] = None
    last_outcome: str = ""
    loop_iteration: int = 0
    llm_calls: int = 0
    last_event_id: str = ""
    last_error: str = ""
    autonomy_enabled: bool = True
    updated_at: str = ""

    def __post_init__(self) -> None:
        if not self.updated_at:
            self.updated_at = utc_now()

    @property
    def idle(self) -> bool:
        return self.phase in {
            AgentPhase.IDLE.value,
            AgentPhase.WATCHING.value,
            AgentPhase.WAITING.value,
            AgentPhase.PAUSED.value,
        }

    def transition(self, new_phase: AgentPhase | str) -> None:
        target = new_phase.value if isinstance(new_phase, AgentPhase) else new_phase
        allowed = AGENT_PHASE_TRANSITIONS.get(self.phase, set())
        if target != self.phase and target not in allowed:
            raise InvalidAgentTransitionError(
                f"Invalid agent phase transition from '{self.phase}' to '{target}'"
            )
        self.phase = target
        self.updated_at = utc_now()

    def to_dict(self) -> dict:
        return {
            "phase": self.phase,
            "active_objective_id": self.active_objective_id,
            "last_outcome": self.last_outcome,
            "loop_iteration": self.loop_iteration,
            "llm_calls": self.llm_calls,
            "last_event_id": self.last_event_id,
            "last_error": self.last_error,
            "autonomy_enabled": self.autonomy_enabled,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "AgentState":
        return cls(
            phase=d.get("phase", AgentPhase.IDLE.value),
            active_objective_id=d.get("active_objective_id"),
            last_outcome=d.get("last_outcome", ""),
            loop_iteration=int(d.get("loop_iteration", 0)),
            llm_calls=int(d.get("llm_calls", 0)),
            last_event_id=d.get("last_event_id", ""),
            last_error=d.get("last_error", ""),
            autonomy_enabled=bool(d.get("autonomy_enabled", True)),
            updated_at=d.get("updated_at", ""),
        )


@dataclass
class Action:
    """Explicit, observable action. Natural-language model output is not an action."""

    identifier: str
    type: str
    arguments: dict[str, Any] = field(default_factory=dict)
    authorization_state: str = "ALLOW"
    execution_state: str = "PENDING"
    capability: str = ""
    operation: str = ""
    result: Any = None
    risk: str = "LOW"
    expected_outcome: str = ""

    def to_dict(self) -> dict:
        return {
            "identifier": self.identifier,
            "type": self.type,
            "arguments": copy.deepcopy(self.arguments),
            "authorization_state": self.authorization_state,
            "execution_state": self.execution_state,
            "capability": self.capability,
            "operation": self.operation,
            "result": copy.deepcopy(self.result),
            "risk": self.risk,
            "expected_outcome": self.expected_outcome,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Action":
        return cls(
            identifier=d.get("identifier") or new_id("ACT"),
            type=d.get("type", ActionType.NONE.value),
            arguments=dict(d.get("arguments") or {}),
            authorization_state=d.get("authorization_state", "ALLOW"),
            execution_state=d.get("execution_state", "PENDING"),
            capability=d.get("capability", ""),
            operation=d.get("operation", ""),
            result=d.get("result"),
            risk=d.get("risk", "LOW"),
            expected_outcome=d.get("expected_outcome", ""),
        )


@dataclass
class Decision:
    """Structured internal decision produced before policy check and execution."""

    intent: str
    action: Action
    confidence: float = 1.0
    risk: str = "LOW"
    verification: str = ""
    reasoning_level: str = ReasoningLevel.DETERMINISTIC.value
    llm_called: bool = False
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "intent": self.intent,
            "action": self.action.to_dict(),
            "confidence": self.confidence,
            "risk": self.risk,
            "verification": self.verification,
            "reasoning_level": self.reasoning_level,
            "llm_called": self.llm_called,
            "reason": self.reason,
        }


@dataclass
class ExecutionResult:
    """Outcome of ActionExecutor. Requested ≠ succeeded."""

    success: bool
    status: str
    output: Any = None
    error: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)
    action_id: str = ""

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "status": self.status,
            "output": copy.deepcopy(self.output),
            "error": self.error,
            "evidence": copy.deepcopy(self.evidence),
            "action_id": self.action_id,
        }


@dataclass
class RecoveryDecision:
    """Explicit recovery choice. Never hidden, never unbounded."""

    kind: str
    reason: str
    failure_class: str
    bounded: bool = True

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "reason": self.reason,
            "failure_class": self.failure_class,
            "bounded": self.bounded,
        }


@dataclass
class DecisionContext:
    """Minimal context for the current objective/decision. Not a transcript."""

    event_kind: str
    event_payload: dict[str, Any]
    objective: dict[str, Any]
    memory: list[dict[str, Any]] = field(default_factory=list)
    state: dict[str, Any] = field(default_factory=dict)
    intent_kind: str = ""
    intent_cheap: bool = True
    intent_arguments: dict[str, Any] = field(default_factory=dict)
    excluded_actions: list[str] = field(default_factory=list)
    last_error: str = ""
    layers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "event_kind": self.event_kind,
            "event_payload": copy.deepcopy(self.event_payload),
            "objective": copy.deepcopy(self.objective),
            "memory": copy.deepcopy(self.memory),
            "state": copy.deepcopy(self.state),
            "intent_kind": self.intent_kind,
            "intent_cheap": self.intent_cheap,
            "intent_arguments": copy.deepcopy(self.intent_arguments),
            "excluded_actions": list(self.excluded_actions),
            "last_error": self.last_error,
            "layers": list(self.layers),
        }


@dataclass
class CycleResult:
    """Observable result of one bounded agent cycle."""

    event: RuntimeEvent
    objective: Optional[Objective]
    agent_state: AgentState
    decision: Optional[Decision] = None
    action: Optional[Action] = None
    execution: Optional[ExecutionResult] = None
    verification: Optional[Any] = None
    recovery: Optional[RecoveryDecision] = None
    context: Optional[DecisionContext] = None
    llm_calls: int = 0
    stages: list[str] = field(default_factory=list)
    error: str = ""

    @property
    def success(self) -> bool:
        if self.agent_state.phase == AgentPhase.NEEDS_USER.value:
            return False
        if self.objective and self.objective.status == ObjectiveState.FAILED.value:
            return False
        if self.verification is not None and getattr(self.verification, "verdict", "") not in ("PASS", ""):
            return False
        return True
