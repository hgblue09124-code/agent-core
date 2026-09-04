# core/learning/retrieval.py
"""Strategy Ranker & Retrieval — multi-factor ranking and selection of reusable strategies."""

from __future__ import annotations

from typing import Optional

from core.learning.strategy import Strategy, StrategyStatus
from core.learning.store import StrategyStore


class StrategyRanker:
    """Ranks and selects applicable strategies based on relevance, status, confidence, and historical success."""

    def __init__(self, store: Optional[StrategyStore] = None):
        self.store = store or StrategyStore()

    def select_applicable_strategies(
        self,
        goal: str,
        context: Optional[dict] = None,
        limit: int = 3,
        include_candidates: bool = False,
    ) -> list[Strategy]:
        """Retrieve and rank active strategies for a given goal/context.

        By default (include_candidates=False), only VALIDATED and SUPPORTED strategies
        are returned to ensure unvalidated CANDIDATE strategies do not influence default runtime.
        """
        all_strategies = self.store.list_all()
        allowed_statuses = {StrategyStatus.VALIDATED.value, StrategyStatus.SUPPORTED.value}
        if include_candidates:
            allowed_statuses.add(StrategyStatus.CANDIDATE.value)

        active_strategies = [
            s for s in all_strategies
            if s.status in allowed_statuses
        ]

        scored_strategies = []
        g_tokens = set(goal.lower().split()) if goal else set()

        for s in active_strategies:
            # 1. Status weight
            status_weight = {
                StrategyStatus.SUPPORTED.value: 1.0,
                StrategyStatus.VALIDATED.value: 0.8,
                StrategyStatus.CANDIDATE.value: 0.5,
            }.get(s.status, 0.1)

            # 2. Context relevance
            ctx_match = 0.1
            if s.applicable_context and g_tokens:
                app_tokens = set(s.applicable_context.lower().split())
                overlap = len(g_tokens.intersection(app_tokens))
                if overlap > 0:
                    ctx_match = min(1.0, 0.3 + (overlap * 0.2))

            # 3. Success rate
            total_evals = s.success_count + s.failure_count
            success_rate = (s.success_count / total_evals) if total_evals > 0 else 0.5

            # Combined score: confidence * status_weight * ctx_match * success_rate
            score = s.confidence * status_weight * ctx_match * (0.5 + 0.5 * success_rate)
            scored_strategies.append((score, s))

        scored_strategies.sort(key=lambda x: x[0], reverse=True)
        return [s for _, s in scored_strategies[:limit]]
