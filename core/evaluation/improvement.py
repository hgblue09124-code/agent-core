# core/evaluation/improvement.py
"""Improvement candidate lifecycle — PROPOSED → TESTING → ACCEPTED/REJECTED."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from core.evaluation.schema import (
    ImprovementCandidate, ImprovementStatus, generate_improvement_id,
)
from core.evaluation.comparator import Comparator, ComparisonResult
from core.evaluation.evaluator import Evaluator


class ImprovementError(ValueError):
    pass


class ImprovementEngine:
    """Manage improvement candidates through their lifecycle.

    Rules:
        - PROPOSED → TESTING: requires hypothesis and target
        - TESTING → ACCEPTED: requires comparator evidence + non-regression
        - TESTING → REJECTED: any regression or insufficient evidence
        - ACCEPTED/REJECTED are terminal
        - LLM may NOT mark its own improvement as ACCEPTED
        - Improvement to the improvement engine itself is REJECTED
    """

    def __init__(self, comparator: Optional[Comparator] = None,
                 evaluator: Optional[Evaluator] = None):
        self._comparator = comparator or Comparator()
        self._evaluator = evaluator or Evaluator()
        self._candidates: dict[str, ImprovementCandidate] = {}
        self._results: list[ComparisonResult] = []

    def propose(self, target: str, hypothesis: str,
               baseline_eval_id: str,
               proposed_change: str,
               expected_benefit: str,
               risk: str,
               tests_required: Optional[list[str]] = None,
               benchmark_required: bool = False,
               proposed_by: str = "agent-core") -> ImprovementCandidate:
        """Propose a new improvement candidate."""
        cand = ImprovementCandidate(
            candidate_id=generate_improvement_id(),
            target=target,
            hypothesis=hypothesis,
            baseline_evaluation_id=baseline_eval_id,
            proposed_change=proposed_change,
            expected_benefit=expected_benefit,
            risk=risk,
            tests_required=list(tests_required or []),
            benchmark_required=benchmark_required,
            verdict=ImprovementStatus.PROPOSED.value,
            created_by=proposed_by,
        )
        self._candidates[cand.candidate_id] = cand
        return cand

    def start_testing(self, candidate_id: str) -> ImprovementCandidate:
        """Move from PROPOSED to TESTING."""
        cand = self._get(candidate_id)
        if cand.verdict != ImprovementStatus.PROPOSED.value:
            raise ImprovementError(
                f"Cannot start testing from {cand.verdict}"
            )
        cand.verdict = ImprovementStatus.TESTING.value
        return cand

    def decide(self, candidate_id: str,
               comparison: ComparisonResult,
               evidence_ids: Optional[list[str]] = None) -> tuple[ImprovementCandidate, str]:
        """Decide whether to ACCEPT or REJECT based on comparator evidence.

        This method uses the comparator's deterministic logic.
        The LLM may NOT override this.
        """
        cand = self._get(candidate_id)
        if cand.verdict != ImprovementStatus.TESTING.value:
            raise ImprovementError(f"Must be TESTING, got {cand.verdict}")

        can_accept, reason = self._comparator.accept_improvement(
            cand, comparison, required_evidence=True
        )

        if can_accept:
            cand.verdict = ImprovementStatus.ACCEPTED.value
            cand.verdict_reason = reason
            cand.evidence_ids = list(evidence_ids or [])
        else:
            cand.verdict = ImprovementStatus.REJECTED.value
            cand.verdict_reason = reason

        cand.candidate_evaluation_id = comparison.candidate_score  # store for record
        self._results.append(comparison)
        return cand, reason

    def reject(self, candidate_id: str, reason: str) -> ImprovementCandidate:
        """Manually reject a candidate."""
        cand = self._get(candidate_id)
        if cand.verdict in (ImprovementStatus.ACCEPTED.value,
                            ImprovementStatus.REJECTED.value):
            raise ImprovementError(f"Cannot reject terminal state: {cand.verdict}")
        cand.verdict = ImprovementStatus.REJECTED.value
        cand.verdict_reason = reason
        return cand

    def get(self, candidate_id: str) -> Optional[ImprovementCandidate]:
        return self._candidates.get(candidate_id)

    def list_all(self) -> list[ImprovementCandidate]:
        return list(self._candidates.values())

    def list_by_status(self, status: str) -> list[ImprovementCandidate]:
        return [c for c in self._candidates.values() if c.verdict == status]

    def _get(self, candidate_id: str) -> ImprovementCandidate:
        if candidate_id not in self._candidates:
            raise ImprovementError(f"Candidate not found: {candidate_id}")
        return self._candidates[candidate_id]
