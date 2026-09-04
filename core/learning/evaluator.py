# core/learning/evaluator.py
"""Strategy Evaluator — manages deterministic confidence updates, status transitions, and strategy versioning."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from core.learning.strategy import Strategy, StrategyStatus, StrategyApplication
from core.learning.store import StrategyStore, StrategyApplicationStore


class StrategyEvaluator:
    """Evaluates strategy application outcomes with deterministic, explainable confidence adjustments."""

    # Confidence boundaries and thresholds
    MIN_CONFIDENCE = 0.05
    MAX_CONFIDENCE = 0.99
    SUCCESS_BOOST = 0.15
    FAILURE_PENALTY = 0.25

    VALIDATED_CONFIDENCE_THRESHOLD = 0.50
    SUPPORTED_CONFIDENCE_THRESHOLD = 0.75
    WEAKENED_CONFIDENCE_THRESHOLD = 0.35
    RETIRED_CONFIDENCE_THRESHOLD = 0.15

    def __init__(
        self,
        store: Optional[StrategyStore] = None,
        app_store: Optional[StrategyApplicationStore] = None,
    ):
        self.store = store or StrategyStore()
        self.app_store = app_store or StrategyApplicationStore()

    def evaluate_application(
        self,
        strategy_id: str,
        run_id: str,
        task_id: str,
        verification_result: str,  # PASS | FAIL | INCONCLUSIVE
        actual_outcome: str = "",
    ) -> Optional[Strategy]:
        """Record a strategy application outcome and update confidence and status deterministically."""
        strategy = self.store.get(strategy_id)
        if not strategy:
            return None

        now = datetime.now(timezone.utc).isoformat()
        app = StrategyApplication(
            application_id=f"APP-{uuid.uuid4().hex[:10]}",
            strategy_id=strategy_id,
            run_id=run_id,
            task_id=task_id,
            context={"strategy_rule": strategy.rule},
            expected_outcome=strategy.expected_outcome,
            actual_outcome=actual_outcome,
            verification_result=verification_result,
            applied_at=now,
        )
        self.app_store.create(app)

        # 1. Update evidence counts
        if verification_result == "PASS":
            strategy.success_count += 1
            strategy.confidence = min(self.MAX_CONFIDENCE, strategy.confidence + self.SUCCESS_BOOST)
            strategy.evidence.append(f"Run {run_id} task {task_id}: PASS")
        elif verification_result == "FAIL":
            strategy.failure_count += 1
            strategy.confidence = max(self.MIN_CONFIDENCE, strategy.confidence - self.FAILURE_PENALTY)
            strategy.evidence.append(f"Run {run_id} task {task_id}: FAIL ({actual_outcome})")
        else:  # INCONCLUSIVE
            strategy.inconclusive_count += 1
            strategy.evidence.append(f"Run {run_id} task {task_id}: INCONCLUSIVE")

        # 2. Update status transitions deterministically
        self._update_status_transitions(strategy)

        return self.store.update(strategy)

    def _update_status_transitions(self, strategy: Strategy) -> None:
        """Deterministic state machine transitions based on confidence and evidence counts."""
        if strategy.status in (StrategyStatus.RETIRED.value, StrategyStatus.SUPERSEDED.value):
            return  # Terminal states

        c = strategy.confidence

        if strategy.failure_count >= 3 and c <= self.RETIRED_CONFIDENCE_THRESHOLD:
            strategy.status = StrategyStatus.RETIRED.value
        elif strategy.failure_count >= 2 and c <= self.WEAKENED_CONFIDENCE_THRESHOLD:
            strategy.status = StrategyStatus.WEAKENED.value
        elif c >= self.SUPPORTED_CONFIDENCE_THRESHOLD and strategy.success_count >= 2:
            strategy.status = StrategyStatus.SUPPORTED.value
        elif c >= self.VALIDATED_CONFIDENCE_THRESHOLD and strategy.success_count >= 1:
            strategy.status = StrategyStatus.VALIDATED.value

    def supersede_strategy(
        self,
        old_strategy_id: str,
        new_rule: str,
        new_name: Optional[str] = None,
    ) -> Optional[Strategy]:
        """Version and supersede an existing strategy with a newer rule while preserving history."""
        old_strat = self.store.get(old_strategy_id)
        if not old_strat:
            return None

        now = datetime.now(timezone.utc).isoformat()
        new_id = f"STRAT-{uuid.uuid4().hex[:10]}"

        new_strat = Strategy(
            strategy_id=new_id,
            name=new_name or f"{old_strat.name} (v{old_strat.version + 1})",
            description=f"Supersedes {old_strat.strategy_id}",
            rule=new_rule,
            applicable_context=old_strat.applicable_context,
            prerequisites=list(old_strat.prerequisites),
            expected_outcome=old_strat.expected_outcome,
            evidence=[f"Superseded {old_strat.strategy_id} v{old_strat.version}"],
            success_count=0,
            failure_count=0,
            confidence=0.35,
            status=StrategyStatus.CANDIDATE.value,
            version=old_strat.version + 1,
            provenance=old_strat.strategy_id,
            source_experiences=list(old_strat.source_experiences),
            supersedes=old_strat.strategy_id,
            created_at=now,
            updated_at=now,
        )

        old_strat.status = StrategyStatus.SUPERSEDED.value
        old_strat.superseded_by = new_id
        self.store.update(old_strat)

        return self.store.create(new_strat)
