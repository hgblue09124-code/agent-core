# core/runtime/agent_runtime.py
"""AgentRuntime — v0.3 Personal Agent Runtime.

Canonical loop:
    OBSERVE → UNDERSTAND → RETRIEVE → DECIDE → ACT → VERIFY → REMEMBER → WATCH/FINISH

The model provides intelligence. This Runtime provides agency.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from core.capabilities.adapter import CapabilityRegistry
from core.capabilities.mock_adapter import MockEchoCapabilityAdapter
from core.events.bus import EventBus
from core.events.schema import AgentEvent, EventPhase, EventStatus, new_event
from core.kernel.policy import PolicyEngine
from core.memory.manager import MemoryManager
from core.runtime.action_executor import ActionExecutor
from core.runtime.classify import GoalIntent, classify_goal
from core.runtime.context_builder import ContextBuilder
from core.runtime.decide import DecisionEngine, ReasoningProvider
from core.runtime.decision import DecisionEngine as PolicyDecisionEngine
from core.runtime.memory_writer import MemoryWriter
from core.runtime.models import (
    Action,
    ActionType,
    AgentPhase,
    AgentState,
    CycleResult,
    Decision,
    DecisionContext,
    ExecutionResult,
    Objective,
    ObjectiveKind,
    ObjectiveState,
    RecoveryDecision,
    RecoveryKind,
    RuntimeBounds,
    RuntimeEvent,
    RuntimeEventKind,
    new_id,
)
from core.runtime.objective_store import ObjectiveStore, atomic_write_json, load_json
from core.runtime.recovery import RecoveryPolicy
from core.runtime.state import AgentAction, VerificationResult
from core.runtime.verifier import Verifier


_PERSISTENT_RE = re.compile(
    r"\b(monitor|watch|track|keep an eye|alert me|notify me|whenever)\b",
    re.IGNORECASE,
)
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOP = {
    "the", "a", "an", "to", "and", "or", "for", "of", "my", "please",
    "that", "this", "with", "on", "in", "at", "is", "be", "it",
}


class AgentRuntime:
    """Persistent Personal Agent Runtime. Single source of truth for agent/objective state."""

    def __init__(
        self,
        *,
        storage_dir: Optional[str | Path] = None,
        capabilities: Optional[CapabilityRegistry] = None,
        memory: Optional[MemoryManager] = None,
        event_bus: Optional[EventBus] = None,
        policy: Optional[PolicyEngine] = None,
        provider: Optional[ReasoningProvider] = None,
        bounds: Optional[RuntimeBounds] = None,
    ):
        root = Path(storage_dir) if storage_dir is not None else None
        obj_dir = (root / "objectives") if root is not None else None
        mem_dir = str(root / "memory") if root is not None else None
        self._state_path = (root / "agent_state.json") if root is not None else None

        self._bounds = bounds or RuntimeBounds()
        self._objectives = ObjectiveStore(obj_dir)
        self._memory = memory or MemoryManager(store_dir=mem_dir)
        self._bus = event_bus or EventBus()
        self._capabilities = capabilities or CapabilityRegistry()
        if not self._capabilities.get("mock.echo"):
            self._capabilities.register(MockEchoCapabilityAdapter())
        self._policy = policy or PolicyEngine()
        self._provider = provider

        self._context_builder = ContextBuilder(self._memory, self._bounds)
        self._decision_engine = DecisionEngine(
            registry=self._capabilities,
            provider=provider,
            bounds=self._bounds,
        )
        self._policy_gate = PolicyDecisionEngine(
            registry=self._capabilities,
            policy=self._policy,
        )
        self._executor = ActionExecutor(self._capabilities, self._memory)
        self._verifier = Verifier(self._memory)
        self._recovery = RecoveryPolicy(self._bounds)
        self._memory_writer = MemoryWriter(self._memory)

        self._state = self._load_state()
        self._in_cycle = False
        self._bus.subscribe(self._on_bus_event)

    # ── Public API ───────────────────────────────────────────────────

    @property
    def state(self) -> AgentState:
        return self._state

    @property
    def event_bus(self) -> EventBus:
        return self._bus

    @property
    def memory(self) -> MemoryManager:
        return self._memory

    def idle(self) -> bool:
        return self._state.idle and not self._in_cycle

    def get_objective(self, objective_id: str) -> Optional[Objective]:
        return self._objectives.get(objective_id)

    def list_objectives(self, *, open_only: bool = False) -> list[Objective]:
        return self._objectives.list_open() if open_only else self._objectives.list_all()

    def submit(self, text: str, *, user_approved: bool = False) -> CycleResult:
        """User input → RuntimeEvent → one bounded cycle."""
        return self.handle_event(RuntimeEvent.user_input(text), user_approved=user_approved)

    def approve(self, objective_id: str) -> CycleResult:
        event = RuntimeEvent(
            event_id=new_id("REV"),
            kind=RuntimeEventKind.APPROVAL.value,
            payload={"objective_id": objective_id},
            objective_id=objective_id,
            source="user",
        )
        return self.handle_event(event, user_approved=True)

    def handle_event(self, event: RuntimeEvent, *, user_approved: bool = False) -> CycleResult:
        """Event-driven entry. Idle when there is nothing meaningful to do."""
        if self._in_cycle:
            return CycleResult(
                event=event,
                objective=self._objectives.get(self._state.active_objective_id or ""),
                agent_state=self._state,
                error="cycle already in progress",
            )
        self._in_cycle = True
        try:
            result = self._run_cycle(event, user_approved=user_approved)
            self._persist()
            return result
        finally:
            self._in_cycle = False

    # ── Canonical loop ───────────────────────────────────────────────

    def _run_cycle(self, event: RuntimeEvent, *, user_approved: bool) -> CycleResult:
        self._state.loop_iteration = 0
        self._state.llm_calls = 0
        self._state.last_event_id = event.event_id
        self._state.last_error = ""
        stages: list[str] = []

        previous_phase = self._state.phase
        self._transition(AgentPhase.OBSERVING)
        stages.append("OBSERVE")
        relevance = self._observe(event, previous_phase=previous_phase)
        if relevance in ("irrelevant", "informational"):
            if previous_phase == AgentPhase.WATCHING.value:
                self._settle(AgentPhase.WATCHING, last_outcome="WATCHING")
            elif previous_phase == AgentPhase.WAITING.value:
                self._settle(AgentPhase.WAITING, last_outcome="WAITING")
            else:
                self._settle(AgentPhase.IDLE, last_outcome="IDLE")
            return CycleResult(
                event=event,
                objective=self._objectives.get(self._state.active_objective_id or "") if previous_phase in {
                    AgentPhase.WATCHING.value, AgentPhase.WAITING.value
                } else None,
                agent_state=self._state,
                stages=stages,
            )

        self._transition(AgentPhase.UNDERSTANDING)
        stages.append("UNDERSTAND")
        objective, intent = self._understand(event)
        objective.status = ObjectiveState.RUNNING.value
        objective.last_event_id = event.event_id
        event.objective_id = objective.objective_id
        self._state.active_objective_id = objective.objective_id
        self._objectives.save(objective)
        self._emit(
            objective.objective_id,
            EventPhase.TASK_STARTED.value,
            f"Objective '{objective.intent}' understood",
        )

        self._transition(AgentPhase.RETRIEVING)
        stages.append("RETRIEVE")
        excluded: list[str] = []
        context = self._context_builder.build(
            event, objective, self._state, intent, excluded_actions=excluded
        )

        decision: Optional[Decision] = None
        action: Optional[Action] = None
        execution: Optional[ExecutionResult] = None
        verification: Optional[VerificationResult] = None
        recovery: Optional[RecoveryDecision] = None
        pending_retry: Optional[Action] = None

        while self._state.loop_iteration < self._bounds.max_cycle_iterations:
            self._state.loop_iteration += 1

            self._transition(AgentPhase.DECIDING)
            stages.append("DECIDE")
            if pending_retry is not None:
                action = pending_retry
                pending_retry = None
                decision = Decision(
                    intent=objective.intent,
                    action=action,
                    reasoning_level="DETERMINISTIC",
                    llm_called=False,
                    reason="retry previously authorized action",
                )
            elif (
                event.kind == RuntimeEventKind.APPROVAL.value
                and objective.pending_action
                and user_approved
            ):
                action = Action.from_dict(objective.pending_action)
                decision = Decision(
                    intent=objective.intent,
                    action=action,
                    reasoning_level="DETERMINISTIC",
                    llm_called=False,
                    reason="approved pending action",
                )
            else:
                decision = self._decision_engine.decide(
                    context, llm_calls_used=self._state.llm_calls
                )
                if decision.llm_called:
                    self._state.llm_calls += 1
                action = decision.action

            assert action is not None and decision is not None

            auth_status, auth_reason = self._authorize(action, user_approved=user_approved)
            action.authorization_state = auth_status
            if auth_status == "ASK_USER":
                objective.pending_action = action.to_dict()
                objective.status = ObjectiveState.BLOCKED.value
                objective.last_error = auth_reason
                self._objectives.save(objective)
                self._transition(AgentPhase.NEEDS_USER)
                self._state.last_outcome = "BLOCKED"
                self._state.last_error = auth_reason
                self._emit(
                    objective.objective_id,
                    EventPhase.ACTION_COMPLETED.value,
                    auth_reason,
                    status=EventStatus.PENDING.value,
                )
                return CycleResult(
                    event=event,
                    objective=objective,
                    agent_state=self._state,
                    decision=decision,
                    action=action,
                    context=context,
                    llm_calls=self._state.llm_calls,
                    stages=stages,
                    error=auth_reason,
                )
            if auth_status == "DENY":
                recovery = RecoveryDecision(
                    kind=RecoveryKind.FAIL.value,
                    reason=auth_reason,
                    failure_class="MISSING_AUTHORIZATION",
                    bounded=True,
                )
                return self._fail(
                    event, objective, decision, action, None, None, recovery, context, stages, auth_reason
                )

            self._transition(AgentPhase.EXECUTING)
            stages.append("ACT")
            self._emit(
                objective.objective_id,
                EventPhase.EXECUTE.value,
                f"Executing {action.type}",
            )
            execution = self._executor.execute(action)
            action.result = execution.output

            self._transition(AgentPhase.VERIFYING)
            stages.append("VERIFY")
            verification = self._verifier.verify(action, execution, objective)
            self._emit(
                objective.objective_id,
                EventPhase.VERIFY.value,
                f"Verification {verification.verdict}",
                status=EventStatus.PASS.value if verification.verdict == "PASS" else EventStatus.FAIL.value,
            )

            if verification.verdict == "PASS":
                break

            failure = self._recovery.classify(execution, verification)
            recovery = self._recovery.decide(
                failure,
                retry_count=objective.retry_count,
                replan_count=objective.replan_count,
                bounds=self._bounds,
            )
            self._emit(
                objective.objective_id,
                EventPhase.RECOVERY.value,
                f"{recovery.kind}: {recovery.reason}",
            )
            if recovery.kind == RecoveryKind.RETRY.value:
                objective.retry_count += 1
                pending_retry = action
                self._objectives.save(objective)
                continue
            if recovery.kind == RecoveryKind.REPLAN.value:
                objective.replan_count += 1
                if action.capability:
                    excluded.append(action.capability)
                context = self._context_builder.build(
                    event,
                    objective,
                    self._state,
                    intent,
                    excluded_actions=excluded,
                    last_error=verification.reason or execution.error,
                )
                self._objectives.save(objective)
                continue
            if recovery.kind == RecoveryKind.ASK_USER.value:
                objective.pending_action = action.to_dict()
                objective.status = ObjectiveState.BLOCKED.value
                objective.last_error = recovery.reason
                self._objectives.save(objective)
                self._transition(AgentPhase.NEEDS_USER)
                self._state.last_outcome = "BLOCKED"
                return CycleResult(
                    event=event,
                    objective=objective,
                    agent_state=self._state,
                    decision=decision,
                    action=action,
                    execution=execution,
                    verification=verification,
                    recovery=recovery,
                    context=context,
                    llm_calls=self._state.llm_calls,
                    stages=stages,
                    error=recovery.reason,
                )
            if recovery.kind == RecoveryKind.WAIT.value:
                objective.status = ObjectiveState.WAITING.value
                objective.last_error = recovery.reason
                self._objectives.save(objective)
                self._transition(AgentPhase.WAITING)
                self._state.last_outcome = "WAITING"
                return CycleResult(
                    event=event,
                    objective=objective,
                    agent_state=self._state,
                    decision=decision,
                    action=action,
                    execution=execution,
                    verification=verification,
                    recovery=recovery,
                    context=context,
                    llm_calls=self._state.llm_calls,
                    stages=stages,
                    error=recovery.reason,
                )
            return self._fail(
                event, objective, decision, action, execution, verification, recovery, context, stages,
                verification.reason or execution.error,
            )

        if verification is None or verification.verdict != "PASS":
            if self._state.loop_iteration >= self._bounds.max_cycle_iterations:
                reason = f"Cycle iteration budget ({self._bounds.max_cycle_iterations}) exhausted"
                recovery = RecoveryDecision(
                    kind=RecoveryKind.FAIL.value,
                    reason=reason,
                    failure_class="PERMANENT",
                    bounded=True,
                )
                return self._fail(
                    event, objective, decision, action, execution, verification, recovery, context, stages, reason
                )

        assert action is not None and execution is not None and verification is not None

        self._transition(AgentPhase.REMEMBERING)
        stages.append("REMEMBER")
        # Persist durable result only after verification. One-shot completions only.
        if objective.kind == ObjectiveKind.ONE_SHOT.value:
            objective.status = ObjectiveState.COMPLETED.value
        else:
            objective.status = ObjectiveState.WAITING.value
        self._memory_writer.maybe_write(
            action=action,
            execution=execution,
            verification=verification,
            objective=objective,
        )
        objective.last_error = ""
        objective.pending_action = None
        self._objectives.save(objective)

        if objective.kind == ObjectiveKind.PERSISTENT.value:
            stages.append("WATCH")
            self._settle(AgentPhase.WATCHING, last_outcome="WATCHING")
            self._emit(
                objective.objective_id,
                EventPhase.RESULT.value,
                "Persistent objective watching",
            )
        else:
            stages.append("FINISH")
            self._settle(AgentPhase.IDLE, last_outcome="COMPLETED")
            self._emit(
                objective.objective_id,
                EventPhase.TASK_COMPLETED.value,
                f"Objective '{objective.intent}' completed",
                status=EventStatus.PASS.value,
            )

        return CycleResult(
            event=event,
            objective=objective,
            agent_state=self._state,
            decision=decision,
            action=action,
            execution=execution,
            verification=verification,
            recovery=recovery,
            context=context,
            llm_calls=self._state.llm_calls,
            stages=stages,
        )

    # ── Stages ───────────────────────────────────────────────────────

    def _observe(self, event: RuntimeEvent, previous_phase: str = "") -> str:
        """irrelevant | informational | associated | actionable | requiring_user."""
        if event.kind == RuntimeEventKind.APPROVAL.value:
            return "requiring_user"
        text = event.text().strip()
        if event.kind == RuntimeEventKind.USER_INPUT.value and not text:
            return "irrelevant"
        if event.kind in {
            RuntimeEventKind.EXTERNAL_RESULT.value,
            RuntimeEventKind.SCHEDULED.value,
            RuntimeEventKind.TASK_COMPLETED.value,
            RuntimeEventKind.INTEGRATION.value,
        }:
            if previous_phase in {AgentPhase.WATCHING.value, AgentPhase.WAITING.value}:
                return "associated"
            if self._match_objective(text or str(event.payload)):
                return "associated"
            return "informational"
        if event.kind == RuntimeEventKind.USER_INPUT.value:
            return "actionable"
        return "informational"

    def _understand(self, event: RuntimeEvent) -> tuple[Objective, GoalIntent]:
        if event.kind == RuntimeEventKind.APPROVAL.value and event.objective_id:
            existing = self._objectives.get(event.objective_id)
            if existing:
                return existing, classify_goal(existing.intent)

        if event.objective_id:
            existing = self._objectives.get(event.objective_id)
            if existing and existing.is_open:
                return existing, classify_goal(existing.intent)

        if self._state.active_objective_id and event.kind in {
            RuntimeEventKind.EXTERNAL_RESULT.value,
            RuntimeEventKind.SCHEDULED.value,
            RuntimeEventKind.TASK_COMPLETED.value,
            RuntimeEventKind.INTEGRATION.value,
        }:
            existing = self._objectives.get(self._state.active_objective_id)
            if existing and existing.is_open:
                return existing, classify_goal(existing.intent)

        text = event.text().strip()
        intent = classify_goal(text)
        matched = self._match_objective(text)
        if matched is not None:
            return matched, intent

        kind = ObjectiveKind.PERSISTENT.value if _PERSISTENT_RE.search(text) else ObjectiveKind.ONE_SHOT.value
        criteria = []
        if intent.kind == "remember":
            criteria = ["memory item exists"]
        elif intent.kind == "forget":
            criteria = ["matching memory removed"]
        elif kind == ObjectiveKind.PERSISTENT.value:
            criteria = ["continue observing relevant events"]
        else:
            criteria = ["verified action result"]

        objective = Objective(
            objective_id=new_id("OBJ"),
            intent=text,
            desired_outcome=text,
            status=ObjectiveState.PENDING.value,
            kind=kind,
            success_criteria=criteria,
        )
        return objective, intent

    def _match_objective(self, text: str) -> Optional[Objective]:
        tokens = set(_TOKEN_RE.findall((text or "").lower())) - _STOP
        if not tokens:
            return None
        best: Optional[Objective] = None
        best_score = 0
        for obj in self._objectives.list_open():
            ot = set(_TOKEN_RE.findall(obj.intent.lower())) - _STOP
            score = len(tokens & ot)
            if score >= 2 and score > best_score:
                best = obj
                best_score = score
        return best

    def _authorize(self, action: Action, *, user_approved: bool) -> tuple[str, str]:
        if action.type in {
            ActionType.ECHO.value,
            ActionType.WATCH.value,
            ActionType.WAIT.value,
            ActionType.FINISH.value,
            ActionType.NONE.value,
            ActionType.ASK_USER.value,
        }:
            return "ALLOW", "internal control action"
        if action.type in {
            ActionType.REMEMBER.value,
            ActionType.FORGET.value,
            ActionType.RETRIEVE_MEMORY.value,
        }:
            agent_action = AgentAction(
                action_id=action.identifier,
                capability="core.memory",
                operation=action.type,
                arguments=dict(action.arguments or {}),
            )
            result = self._policy_gate.evaluate_action(agent_action, user_approved=user_approved)
            return result.authorization_status, result.reason
        if action.type == ActionType.INVOKE_CAPABILITY.value:
            agent_action = AgentAction(
                action_id=action.identifier,
                capability=action.capability,
                operation=action.operation or str((action.arguments or {}).get("action") or "execute"),
                arguments=dict(action.arguments or {}),
            )
            result = self._policy_gate.evaluate_action(agent_action, user_approved=user_approved)
            return result.authorization_status, result.reason
        return "DENY", f"Unauthorized action type '{action.type}'"

    # ── State ownership ──────────────────────────────────────────────

    def _transition(self, phase: AgentPhase) -> None:
        # LLM never calls this. Only the Runtime.
        if self._state.phase == AgentPhase.IDLE.value and phase == AgentPhase.OBSERVING:
            self._state.transition(phase)
            return
        if self._state.phase in {
            AgentPhase.WATCHING.value,
            AgentPhase.WAITING.value,
            AgentPhase.NEEDS_USER.value,
            AgentPhase.FAILED.value,
            AgentPhase.COMPLETED.value,
            AgentPhase.PAUSED.value,
        } and phase == AgentPhase.OBSERVING:
            self._state.transition(AgentPhase.OBSERVING)
            return
        self._state.transition(phase)

    def _settle(self, phase: AgentPhase, *, last_outcome: str) -> None:
        if phase == AgentPhase.IDLE:
            # REMEMBERING → COMPLETED is allowed; then COMPLETED → IDLE.
            if self._state.phase == AgentPhase.REMEMBERING.value:
                self._state.transition(AgentPhase.COMPLETED)
            self._state.transition(AgentPhase.IDLE)
            self._state.active_objective_id = None
        else:
            self._state.transition(phase)
        self._state.last_outcome = last_outcome
        self._persist()

    def _fail(
        self,
        event: RuntimeEvent,
        objective: Objective,
        decision: Optional[Decision],
        action: Optional[Action],
        execution: Optional[ExecutionResult],
        verification: Optional[VerificationResult],
        recovery: Optional[RecoveryDecision],
        context: Optional[DecisionContext],
        stages: list[str],
        error: str,
    ) -> CycleResult:
        objective.status = ObjectiveState.FAILED.value
        objective.last_error = error
        self._objectives.save(objective)
        try:
            if self._state.phase != AgentPhase.FAILED.value:
                self._state.transition(AgentPhase.FAILED)
        except Exception:
            self._state.phase = AgentPhase.FAILED.value
        self._state.last_outcome = "FAILED"
        self._state.last_error = error
        self._emit(
            objective.objective_id,
            EventPhase.TASK_FAILED.value,
            error,
            status=EventStatus.FAIL.value,
        )
        self._persist()
        return CycleResult(
            event=event,
            objective=objective,
            agent_state=self._state,
            decision=decision,
            action=action,
            execution=execution,
            verification=verification,
            recovery=recovery,
            context=context,
            llm_calls=self._state.llm_calls,
            stages=stages,
            error=error,
        )

    def _emit(self, run_id: str, phase: str, action: str, status: str = EventStatus.OK.value) -> None:
        self._bus.publish(new_event(run_id=run_id, phase=phase, action=action, status=status))

    def _on_bus_event(self, event: AgentEvent) -> None:
        if self._in_cycle:
            return
        if self._state.phase not in {AgentPhase.WATCHING.value, AgentPhase.WAITING.value}:
            return
        if event.phase not in {
            EventPhase.TASK_COMPLETED.value,
            EventPhase.ACTION_COMPLETED.value,
            EventPhase.RESULT.value,
            EventPhase.OBSERVE.value,
        }:
            return
        rt = RuntimeEvent(
            event_id=new_id("REV"),
            kind=RuntimeEventKind.EXTERNAL_RESULT.value,
            payload={"phase": event.phase, "action": event.action, "message": event.message, "text": event.action},
            objective_id=self._state.active_objective_id or "",
            source="event_bus",
        )
        self.handle_event(rt)

    def _load_state(self) -> AgentState:
        if self._state_path is None:
            return AgentState()
        data = load_json(self._state_path)
        if not data:
            return AgentState()
        try:
            return AgentState.from_dict(data)
        except (KeyError, TypeError, ValueError):
            return AgentState()

    def _persist(self) -> None:
        if self._state_path is None:
            return
        atomic_write_json(self._state_path, self._state.to_dict())
