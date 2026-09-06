# core/runtime/recovery.py
"""RecoveryPolicy — explicit, bounded retry / replan / wait / ask / fail."""

from __future__ import annotations

from core.runtime.models import (
    ExecutionResult,
    FailureClass,
    RecoveryDecision,
    RecoveryKind,
    RuntimeBounds,
)
from core.runtime.state import VerificationResult


class RecoveryPolicy:
    """Classify failure and choose a bounded recovery. Never retries forever."""

    def __init__(self, bounds: RuntimeBounds | None = None):
        self._bounds = bounds or RuntimeBounds()

    def classify(
        self,
        execution: ExecutionResult | None,
        verification: VerificationResult | None,
        *,
        authorization_status: str = "ALLOW",
    ) -> FailureClass:
        if authorization_status in ("DENY", "ASK_USER"):
            return FailureClass.MISSING_AUTHORIZATION
        if execution is not None and not execution.success:
            err = (execution.error or "").lower()
            if "not found" in err or "unknown action" in err or "missing capability" in err:
                return FailureClass.INVALID_ACTION
            if "provider" in err or "unavailable" in err:
                return FailureClass.PROVIDER_UNAVAILABLE
            if "transient" in err or execution.status in ("TIMEOUT", "RETRY"):
                return FailureClass.TRANSIENT
            if verification is not None and verification.verdict != "PASS":
                return FailureClass.VERIFICATION_FAILURE
            return FailureClass.PERMANENT
        if verification is not None and verification.verdict != "PASS":
            return FailureClass.VERIFICATION_FAILURE
        return FailureClass.PERMANENT

    def decide(
        self,
        failure: FailureClass,
        *,
        retry_count: int,
        replan_count: int,
        bounds: RuntimeBounds | None = None,
    ) -> RecoveryDecision:
        caps = bounds or self._bounds
        if failure == FailureClass.MISSING_AUTHORIZATION:
            return RecoveryDecision(
                kind=RecoveryKind.ASK_USER.value,
                reason="Authorization missing; ask the user",
                failure_class=failure.value,
                bounded=True,
            )
        if failure == FailureClass.INVALID_ACTION:
            if replan_count < caps.max_replans:
                return RecoveryDecision(
                    kind=RecoveryKind.REPLAN.value,
                    reason="Invalid action; replan within bound",
                    failure_class=failure.value,
                    bounded=True,
                )
            return RecoveryDecision(
                kind=RecoveryKind.FAIL.value,
                reason="Invalid action and replan budget exhausted",
                failure_class=failure.value,
                bounded=True,
            )
        if failure == FailureClass.PROVIDER_UNAVAILABLE:
            if retry_count < 1:
                return RecoveryDecision(
                    kind=RecoveryKind.WAIT.value,
                    reason="Provider unavailable; wait once",
                    failure_class=failure.value,
                    bounded=True,
                )
            return RecoveryDecision(
                kind=RecoveryKind.FAIL.value,
                reason="Provider unavailable after wait",
                failure_class=failure.value,
                bounded=True,
            )
        if failure in (FailureClass.TRANSIENT, FailureClass.VERIFICATION_FAILURE):
            if retry_count < caps.max_retries:
                return RecoveryDecision(
                    kind=RecoveryKind.RETRY.value,
                    reason=f"Retry {retry_count + 1}/{caps.max_retries}",
                    failure_class=failure.value,
                    bounded=True,
                )
            if replan_count < caps.max_replans:
                return RecoveryDecision(
                    kind=RecoveryKind.REPLAN.value,
                    reason=f"Replan {replan_count + 1}/{caps.max_replans} after retry limit",
                    failure_class=failure.value,
                    bounded=True,
                )
            return RecoveryDecision(
                kind=RecoveryKind.FAIL.value,
                reason="Retry and replan budgets exhausted",
                failure_class=failure.value,
                bounded=True,
            )
        if failure == FailureClass.MISSING_CONTEXT:
            return RecoveryDecision(
                kind=RecoveryKind.ASK_USER.value,
                reason="Missing context required from user",
                failure_class=failure.value,
                bounded=True,
            )
        return RecoveryDecision(
            kind=RecoveryKind.FAIL.value,
            reason="Permanent failure; fail safely",
            failure_class=failure.value,
            bounded=True,
        )

    def deny(self, reason: str) -> RecoveryDecision:
        """Policy DENY is fail-closed. Distinct from ASK_USER missing approval."""
        return RecoveryDecision(
            kind=RecoveryKind.FAIL.value,
            reason=reason,
            failure_class=FailureClass.MISSING_AUTHORIZATION.value,
            bounded=True,
        )

    def cycle_budget_exhausted(self, max_cycle_iterations: int) -> RecoveryDecision:
        return RecoveryDecision(
            kind=RecoveryKind.FAIL.value,
            reason=f"Cycle iteration budget ({max_cycle_iterations}) exhausted",
            failure_class=FailureClass.PERMANENT.value,
            bounded=True,
        )
