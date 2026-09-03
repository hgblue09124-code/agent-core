# core/evaluation/scorer.py
"""Deterministic scorer for evaluation layers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from core.evaluation.schema import Evidence, LayerScore, ScoreLayer


# Default layer weights (must sum to 1.0 for normalised scores)
DEFAULT_WEIGHTS = {
    ScoreLayer.CORRECTNESS.value: 0.30,
    ScoreLayer.REQUIREMENT_COVERAGE.value: 0.25,
    ScoreLayer.INTEGRATION.value: 0.15,
    ScoreLayer.REGRESSION_SAFETY.value: 0.20,
    ScoreLayer.EFFICIENCY.value: 0.10,
}


@dataclass
class ScoreResult:
    score: float
    notes: str
    evidence_ids: list[str] = field(default_factory=list)


class Scorer:
    """Deterministic multi-layer scorer.

    Each layer is scored 0.0..1.0 based on evidence.
    """

    def __init__(self, weights: Optional[dict[str, float]] = None):
        self.weights = weights or DEFAULT_WEIGHTS

    def score_correctness(self, evidence: list[Evidence]) -> ScoreResult:
        """Score: correctness.

        PASS evidence = +1.0 per criterion
        FAIL evidence = -1.0 per criterion
        """
        if not evidence:
            return ScoreResult(0.0, "No evidence for correctness")
        pass_count = sum(1 for e in evidence if e.is_pass())
        fail_count = sum(1 for e in evidence if e.is_fail())
        total = pass_count + fail_count
        if total == 0:
            return ScoreResult(0.0, "No pass/fail evidence")
        score = pass_count / total
        notes = f"pass={pass_count} fail={fail_count} of {total}"
        return ScoreResult(score, notes,
                          evidence_ids=[e.evidence_id for e in evidence])

    def score_requirement_coverage(self, evidence: list[Evidence]) -> ScoreResult:
        """Score: requirement coverage (fraction of required evidence present)."""
        if not evidence:
            return ScoreResult(0.0, "No requirement evidence")
        pass_count = sum(1 for e in evidence if e.is_pass())
        # Expect at least 3 key criteria
        expected = 3
        score = min(1.0, pass_count / expected)
        notes = f"covered={pass_count}/{expected}"
        return ScoreResult(score, notes,
                          evidence_ids=[e.evidence_id for e in evidence])

    def score_integration(self, evidence: list[Evidence]) -> ScoreResult:
        """Score: integration (knowledge used, experience recorded, etc)."""
        if not evidence:
            return ScoreResult(0.0, "No integration evidence")
        pass_count = sum(1 for e in evidence if e.is_pass())
        total = len(evidence)
        score = pass_count / total if total else 0.0
        return ScoreResult(score, f"pass={pass_count}/{total}",
                          evidence_ids=[e.evidence_id for e in evidence])

    def score_regression_safety(self, evidence: list[Evidence]) -> ScoreResult:
        """Score: regression safety (no existing functionality broken)."""
        if not evidence:
            return ScoreResult(0.5, "No regression evidence — assume safe")
        pass_count = sum(1 for e in evidence if e.is_pass())
        fail_count = sum(1 for e in evidence if e.is_fail())
        total = pass_count + fail_count
        if total == 0:
            return ScoreResult(0.5, "Neutral: no regression data")
        # Any failure is severe
        if fail_count > 0:
            score = pass_count / total * 0.5
            return ScoreResult(score,
                              f"REGRESSION: fail={fail_count} pass={pass_count}",
                              [e.evidence_id for e in evidence])
        return ScoreResult(pass_count / total,
                          f"no regression: pass={pass_count}",
                          [e.evidence_id for e in evidence])

    def score_efficiency(self, evidence: list[Evidence]) -> ScoreResult:
        """Score: efficiency (time, LLM calls, retries within budget)."""
        if not evidence:
            return ScoreResult(0.5, "No efficiency evidence — neutral")
        pass_count = sum(1 for e in evidence if e.is_pass())
        total = len(evidence)
        return ScoreResult(pass_count / total if total else 0.5,
                          f"efficiency: pass={pass_count}/{total}",
                          [e.evidence_id for e in evidence])

    def score_layer(self, layer: str, evidence: list[Evidence]) -> LayerScore:
        """Score a specific layer. Returns LayerScore."""
        if layer == ScoreLayer.CORRECTNESS.value:
            result = self.score_correctness(evidence)
        elif layer == ScoreLayer.REQUIREMENT_COVERAGE.value:
            result = self.score_requirement_coverage(evidence)
        elif layer == ScoreLayer.INTEGRATION.value:
            result = self.score_integration(evidence)
        elif layer == ScoreLayer.REGRESSION_SAFETY.value:
            result = self.score_regression_safety(evidence)
        elif layer == ScoreLayer.EFFICIENCY.value:
            result = self.score_efficiency(evidence)
        else:
            result = ScoreResult(0.0, f"Unknown layer: {layer}")

        return LayerScore(
            layer=layer,
            score=result.score,
            weight=self.weights.get(layer, 0.1),
            evidence_ids=result.evidence_ids,
            notes=result.notes,
        )

    def weighted_total(self, scores: list[LayerScore]) -> float:
        """Compute weighted total across all scored layers."""
        if not scores:
            return 0.0
        total_weight = sum(s.weight for s in scores)
        if total_weight == 0:
            return 0.0
        return sum(s.weighted() for s in scores) / total_weight
