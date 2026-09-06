# core/runtime/verifier.py
"""Verifier — meaningful actions require outcome verification. Requested ≠ succeeded."""

from __future__ import annotations

from typing import Optional

from core.capabilities.schema import CapabilityResult
from core.memory.manager import MemoryManager
from core.memory.schema import MemoryQuery
from core.runtime.models import Action, ActionType, ExecutionResult, Objective
from core.runtime.state import AgentAction, Observation, VerificationResult
from core.runtime.verification import VerificationEngine


class Verifier:
    """Independent of the executor. LLM cannot self-certify."""

    def __init__(self, memory: Optional[MemoryManager] = None):
        self._memory = memory
        self._engine = VerificationEngine()

    def verify(
        self,
        action: Action,
        execution: ExecutionResult,
        objective: Objective,
    ) -> VerificationResult:
        kind = action.type

        if kind in {
            ActionType.ASK_USER.value,
            ActionType.WAIT.value,
            ActionType.WATCH.value,
            ActionType.FINISH.value,
            ActionType.NONE.value,
        }:
            return VerificationResult(
                verdict="PASS",
                reason=f"Control action '{kind}' has no side effect to verify",
                evidence_valid=True,
                goal_satisfied=kind in {ActionType.FINISH.value, ActionType.WATCH.value},
            )

        if not execution.success or execution.status not in ("SUCCESS", "OK", "PASS", "SKIPPED"):
            return VerificationResult(
                verdict="FAIL",
                reason=execution.error or f"Execution status '{execution.status}'",
                evidence_valid=False,
                goal_satisfied=False,
            )

        if kind == ActionType.REMEMBER.value:
            return self._verify_remember(action, execution)
        if kind == ActionType.FORGET.value:
            return self._verify_forget(action)
        if kind == ActionType.ECHO.value:
            output = execution.output
            if output is None or output == "":
                return VerificationResult(
                    verdict="INCONCLUSIVE",
                    reason="Echo succeeded without output",
                    evidence_valid=False,
                    goal_satisfied=False,
                )
            return VerificationResult(
                verdict="PASS",
                reason="Echo output present",
                evidence_valid=True,
                goal_satisfied=True,
            )
        if kind == ActionType.INVOKE_CAPABILITY.value:
            return self._verify_capability(action, execution, objective)
        if kind == ActionType.RETRIEVE_MEMORY.value:
            return VerificationResult(
                verdict="PASS",
                reason="Memory retrieve returned",
                evidence_valid=True,
                goal_satisfied=True,
            )

        return VerificationResult(
            verdict="FAIL",
            reason=f"No verifier for action type '{kind}'",
            evidence_valid=False,
            goal_satisfied=False,
        )

    def _verify_remember(self, action: Action, execution: ExecutionResult) -> VerificationResult:
        if self._memory is None:
            return VerificationResult(
                verdict="PASS" if execution.success else "FAIL",
                reason="Remember executed (memory store not injected for verify)",
                evidence_valid=execution.success,
                goal_satisfied=execution.success,
            )
        args = action.arguments or {}
        query = str(args.get("value") or args.get("key") or args.get("content") or "")
        hits = self._memory.retrieve(MemoryQuery(query=query, limit=5)) if query else []
        if not hits:
            # Fall back to memory_id evidence from execution.
            memory_id = (execution.evidence or {}).get("memory_id")
            if memory_id and self._memory.store.get(str(memory_id)):
                hits = [self._memory.store.get(str(memory_id))]
        if not hits:
            return VerificationResult(
                verdict="FAIL",
                reason="Remember reported success but memory does not exist",
                evidence_valid=False,
                goal_satisfied=False,
            )
        return VerificationResult(
            verdict="PASS",
            reason="Memory item exists after remember",
            evidence_valid=True,
            goal_satisfied=True,
        )

    def _verify_forget(self, action: Action) -> VerificationResult:
        if self._memory is None:
            return VerificationResult(
                verdict="PASS",
                reason="Forget executed",
                evidence_valid=True,
                goal_satisfied=True,
            )
        args = action.arguments or {}
        query = str(args.get("query") or args.get("key") or "")
        if not query:
            return VerificationResult(
                verdict="PASS",
                reason="Forget executed without query remainder",
                evidence_valid=True,
                goal_satisfied=True,
            )
        hits = self._memory.retrieve(MemoryQuery(query=query, limit=5))
        remaining = [
            h
            for h in hits
            if query.lower() in (h.content or "").lower()
            or query.lower() in str((h.metadata or {}).get("key", "")).lower()
        ]
        if remaining:
            return VerificationResult(
                verdict="FAIL",
                reason="Forget reported success but matching memory still exists",
                evidence_valid=False,
                goal_satisfied=False,
            )
        return VerificationResult(
            verdict="PASS",
            reason="Matching memory no longer exists",
            evidence_valid=True,
            goal_satisfied=True,
        )

    def _verify_capability(
        self,
        action: Action,
        execution: ExecutionResult,
        objective: Objective,
    ) -> VerificationResult:
        cap_result = CapabilityResult(
            capability_id=action.capability,
            status=execution.status,
            output=execution.output,
            error=execution.error,
            metadata=dict(execution.evidence or {}),
        )
        agent_action = AgentAction(
            action_id=action.identifier,
            capability=action.capability or "unknown",
            operation=action.operation or "execute",
            arguments=dict(action.arguments or {}),
            expected_outcome=action.expected_outcome or objective.desired_outcome,
        )
        observation = Observation(
            action_id=action.identifier,
            timestamp="",
            status=execution.status,
            output=execution.output,
            error=execution.error,
            evidence=dict(execution.evidence or {}),
        )
        return self._engine.verify_execution(
            goal=objective.intent,
            action=agent_action,
            result=cap_result,
            observation=observation,
        )
