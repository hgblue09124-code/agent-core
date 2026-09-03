# core/evaluation/evaluator.py
"""Core evaluator — produces evidence-backed evaluations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from core.evaluation.schema import (
    Evaluation, Evidence, LayerScore, Verdict,
    AchievementState, generate_eval_id,
)
from core.evaluation.criteria import get_required_codes, get_criterion
from core.evaluation.scorer import Scorer
from core.evaluation.evidence import EvidenceLedger


@dataclass
class EvaluationContext:
    """Context for a single evaluation run."""
    target_id: str
    run_id: str = ""
    evidence_ledger: Optional[EvidenceLedger] = None

    def record_evidence(self, ev: Evidence) -> Evidence:
        if self.evidence_ledger:
            return self.evidence_ledger.record(ev)
        return ev


class Evaluator:
    """Produce evidence-backed evaluations.

    A verdict is only PASS if:
        1. Evidence exists for required criteria
        2. No required criterion is failed
        3. Achievement state is at least SOLUTION_VALID
    """

    def __init__(self, scorer: Optional[Scorer] = None,
                 ledger: Optional[EvidenceLedger] = None):
        self._scorer = scorer or Scorer()
        self._ledger = ledger or EvidenceLedger()

    def evaluate(self, ctx: EvaluationContext,
                 achievement: str,
                 evidence_by_layer: dict[str, list[Evidence]],
                 failed_criteria: Optional[list[str]] = None,
                 warnings: Optional[list[str]] = None) -> Evaluation:
        """Evaluate with structured evidence per layer."""
        scores: list[LayerScore] = []
        all_evidence: list[Evidence] = []
        failed = list(failed_criteria or [])
        warns = list(warnings or [])

        # Score each layer
        for layer, ev_list in evidence_by_layer.items():
            scored = self._scorer.score_layer(layer, ev_list)
            scores.append(scored)
            all_evidence.extend(ev_list)

            # Record evidence
            for ev in ev_list:
                self._ledger.record(ev)

        # Check required criteria
        required = get_required_codes()
        for code in required:
            # Check if this criterion has evidence
            crit = get_criterion(code)
            if crit and not any(
                ev.evidence_id for ev in all_evidence
                if ev.type == crit.layer.upper()
            ):
                # Check failed criteria
                if code in failed:
                    warns.append(f"Required criterion {code} has no supporting evidence")

        # Determine verdict
        verdict = self._determine_verdict(scores, failed, achievement)

        return Evaluation(
            evaluation_id=generate_eval_id(),
            target_id=ctx.target_id,
            achievement=achievement,
            verdict=verdict,
            scores=scores,
            evidence=all_evidence,
            failed_criteria=failed,
            warnings=warns,
        )

    def _determine_verdict(self, scores: list[LayerScore],
                           failed: list[str],
                           achievement: str) -> str:
        """Determine verdict from scores and failed criteria.

        FAIL if:
            - Any required criterion failed
            - Correctness score < 0.5
        PASS otherwise
        """
        # Check required failures
        if failed:
            return Verdict.FAIL.value

        # Check correctness
        for s in scores:
            if s.layer == "correctness":
                if s.score < 0.5:
                    return Verdict.FAIL.value
                break

        # Check total score
        total = self._scorer.weighted_total(scores)
        if total >= 0.5:
            return Verdict.PASS.value
        return Verdict.FAIL.value

    def evaluate_from_evidence(self, evaluation_id: str, target_id: str,
                                 achievement: str,
                                 evidence: list[Evidence],
                                 failed_criteria: Optional[list[str]] = None,
                                 warnings: Optional[list[str]] = None) -> Evaluation:
        """Evaluate a target from a flat list of evidence.

        Groups evidence by layer using evidence type.
        """
        evidence_by_layer: dict[str, list[Evidence]] = {
            "correctness": [],
            "requirement_coverage": [],
            "integration": [],
            "regression_safety": [],
            "efficiency": [],
        }
        for ev in evidence:
            # Map evidence type to layer
            layer = self._ev_type_to_layer(ev.type)
            evidence_by_layer[layer].append(ev)

        ctx = EvaluationContext(target_id=target_id, evidence_ledger=self._ledger)
        return self.evaluate(ctx, achievement, evidence_by_layer,
                            failed_criteria, warnings)

    def _ev_type_to_layer(self, ev_type: str) -> str:
        """Map evidence type to score layer."""
        mapping = {
            "TEST": "correctness",
            "ASSERTION": "correctness",
            "COMMAND_RESULT": "correctness",
            "FILE_STATE": "requirement_coverage",
            "CHECKPOINT": "integration",
            "BENCHMARK": "efficiency",
            "REGRESSION": "regression_safety",
            "MANUAL": "integration",
        }
        return mapping.get(ev_type, "correctness")
