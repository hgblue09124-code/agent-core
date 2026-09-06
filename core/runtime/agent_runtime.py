# core/runtime/agent_runtime.py
"""AgentRuntime — v0.3 Personal Agent Runtime orchestrator.

Canonical loop:
    OBSERVE → UNDERSTAND → RETRIEVE → DECIDE → ACT → VERIFY → REMEMBER → WATCH/FINISH

The model provides intelligence. This Runtime provides agency.
AgentRuntime owns the loop and AgentState. Collaborators own their stages.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from core.capabilities.adapter import CapabilityRegistry
from core.capabilities.mock_adapter import MockEchoCapabilityAdapter
from core.events.bus import EventBus
from core.events.schema import AgentEvent, EventPhase, EventStatus, new_event
from core.kernel.policy import PolicyEngine
from core.memory.manager import MemoryManager
from core.runtime.action_executor import ActionExecutor
from core.runtime.classify import GoalIntent
from core.runtime.context_builder import ContextBuilder
from core.runtime.decide import DecisionEngine, ReasoningProvider
from core.runtime.decision import DecisionEngine as PolicyDecisionEngine
from core.runtime.memory_writer import MemoryWriter
from core.runtime.models import (
    Action,
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
from core.runtime.observe import Observer
from core.runtime.recovery import RecoveryPolicy
from core.runtime.state import VerificationResult
from core.runtime.verifier import Verifier


class AgentRuntime:
    """Persistent Personal Agent Runtime. Orchestrator, not a God Object.

    Owns: AgentState, bounded loop, event wake, persistence.
    Delegates: observe, objective lifecycle, context, decide, policy,
    execute, verify, recover, remember.
    """

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

        self._observer = Observer(self._objectives)
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
        relevance = self._observer.classify(event, previous_phase=previous_phase)
        idle = self._idle_if_irrelevant(event, relevance, previous_phase, stages)
        if idle is not None:
            return idle

        self._transition(AgentPhase.UNDERSTANDING)
        stages.append("UNDERSTAND")
        objective, intent = self._objectives.resolve(
            event, active_objective_id=self._state.active_objective_id or ""
        )
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
            decision, action, pending_retry = self._decide(
                event, objective, context, user_approved, pending_retry
            )

            blocked = self._authorize_or_block(
                event, objective, decision, action, context, stages, user_approved
            )
            if blocked is not None:
                return blocked

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

            outcome = self._recover(
                event, objective, intent, decision, action, execution, verification,
                context, stages, excluded,
            )
            recovery = outcome.recovery or recovery
            if outcome.kind == "retry":
                pending_retry = outcome.retry_action
                continue
            if outcome.kind == "replan":
                context = outcome.context or context
                continue
            return outcome.result  # type: ignore[return-value]

        if verification is None or verification.verdict != "PASS":
            if self._state.loop_iteration >= self._bounds.max_cycle_iterations:
                recovery = self._recovery.cycle_budget_exhausted(
                    self._bounds.max_cycle_iterations
                )
                return self._fail(
                    event, objective, decision, action, execution, verification,
                    recovery, context, stages, recovery.reason,
                )

        assert action is not None and execution is not None and verification is not None
        return self._remember_and_settle(
            event, objective, decision, action, execution, verification, recovery, context, stages
        )

    def _idle_if_irrelevant(
        self,
        event: RuntimeEvent,
        relevance: str,
        previous_phase: str,
        stages: list[str],
    ) -> Optional[CycleResult]:
        if relevance not in ("irrelevant", "informational"):
            return None
        if previous_phase == AgentPhase.WATCHING.value:
            self._settle(AgentPhase.WATCHING, last_outcome="WATCHING")
        elif previous_phase == AgentPhase.WAITING.value:
            self._settle(AgentPhase.WAITING, last_outcome="WAITING")
        else:
            self._settle(AgentPhase.IDLE, last_outcome="IDLE")
        watching = previous_phase in {AgentPhase.WATCHING.value, AgentPhase.WAITING.value}
        return CycleResult(
            event=event,
            objective=self._objectives.get(self._state.active_objective_id or "") if watching else None,
            agent_state=self._state,
            stages=stages,
        )

    def _decide(
        self,
        event: RuntimeEvent,
        objective: Objective,
        context: DecisionContext,
        user_approved: bool,
        pending_retry: Optional[Action],
    ) -> tuple[Decision, Action, Optional[Action]]:
        if pending_retry is not None:
            action = pending_retry
            decision = Decision(
                intent=objective.intent,
                action=action,
                reasoning_level="DETERMINISTIC",
                llm_called=False,
                reason="retry previously authorized action",
            )
            return decision, action, None
        if (
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
            return decision, action, None
        decision = self._decision_engine.decide(
            context, llm_calls_used=self._state.llm_calls
        )
        if decision.llm_called:
            self._state.llm_calls += 1
        return decision, decision.action, None

    def _authorize_or_block(
        self,
        event: RuntimeEvent,
        objective: Objective,
        decision: Decision,
        action: Action,
        context: DecisionContext,
        stages: list[str],
        user_approved: bool,
    ) -> Optional[CycleResult]:
        auth_status, auth_reason = self._policy_gate.authorize(
            action, user_approved=user_approved
        )
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
            recovery = self._recovery.deny(auth_reason)
            return self._fail(
                event, objective, decision, action, None, None, recovery, context, stages, auth_reason
            )
        return None

    def _recover(
        self,
        event: RuntimeEvent,
        objective: Objective,
        intent: GoalIntent,
        decision: Decision,
        action: Action,
        execution: ExecutionResult,
        verification: VerificationResult,
        context: DecisionContext,
        stages: list[str],
        excluded: list[str],
    ) -> "_RecoveryOutcome":
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
            self._objectives.save(objective)
            return _RecoveryOutcome(kind="retry", retry_action=action, recovery=recovery)
        if recovery.kind == RecoveryKind.REPLAN.value:
            objective.replan_count += 1
            if action.capability:
                excluded.append(action.capability)
            rebuilt = self._context_builder.build(
                event,
                objective,
                self._state,
                intent,
                excluded_actions=excluded,
                last_error=verification.reason or execution.error,
            )
            self._objectives.save(objective)
            return _RecoveryOutcome(kind="replan", context=rebuilt, recovery=recovery)
        if recovery.kind == RecoveryKind.ASK_USER.value:
            objective.pending_action = action.to_dict()
            objective.status = ObjectiveState.BLOCKED.value
            objective.last_error = recovery.reason
            self._objectives.save(objective)
            self._transition(AgentPhase.NEEDS_USER)
            self._state.last_outcome = "BLOCKED"
            return _RecoveryOutcome(
                kind="stop",
                recovery=recovery,
                result=CycleResult(
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
                ),
            )
        if recovery.kind == RecoveryKind.WAIT.value:
            objective.status = ObjectiveState.WAITING.value
            objective.last_error = recovery.reason
            self._objectives.save(objective)
            self._transition(AgentPhase.WAITING)
            self._state.last_outcome = "WAITING"
            return _RecoveryOutcome(
                kind="stop",
                recovery=recovery,
                result=CycleResult(
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
                ),
            )
        return _RecoveryOutcome(
            kind="stop",
            recovery=recovery,
            result=self._fail(
                event, objective, decision, action, execution, verification, recovery, context, stages,
                verification.reason or execution.error,
            ),
        )

    def _remember_and_settle(
        self,
        event: RuntimeEvent,
        objective: Objective,
        decision: Decision,
        action: Action,
        execution: ExecutionResult,
        verification: VerificationResult,
        recovery: Optional[RecoveryDecision],
        context: DecisionContext,
        stages: list[str],
    ) -> CycleResult:
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
        self._state.transition(AgentPhase.FAILED)
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


class _RecoveryOutcome:
    """Internal loop signal. Not a public type."""

    def __init__(
        self,
        *,
        kind: str,
        result: Optional[CycleResult] = None,
        retry_action: Optional[Action] = None,
        context: Optional[DecisionContext] = None,
        recovery: Optional[RecoveryDecision] = None,
    ):
        self.kind = kind
        self.result = result
        self.retry_action = retry_action
        self.context = context
        self.recovery = recovery
