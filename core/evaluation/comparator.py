# core/evaluation/comparator.py
"""Baseline vs candidate comparison for regression and improvement evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from core.evaluation.schema import Evaluation, ImprovementCandidate, Evidence
from core.evaluation.scorer import Scorer


@dataclass
class ComparisonResult:
    baseline_score: float
    candidate_score: float
    delta: float                    # candidate - baseline
    improvement_detected: bool
    regression_detected: bool
    details: list[str] = field(default_factory=list)
    verdict: str = "INCONCLUSIVE"   # IMPROVED / REGRESSED / NEUTRAL / INCONCLUSIVE

    def summary(self) -> str:
        return (
            f"baseline={self.baseline_score:.3f} "
            f"candidate={self.candidate_score:.3f} "
            f"delta={self.delta:+.3f} "
            f"[{self.verdict}]"
        )


class Comparator:
    """Compare baseline vs candidate evaluations.

    The LLM may NOT override this decision. Acceptance requires evidence.
    """

    REGRESSION_THRESHOLD = -0.05   # 5% drop = regression
    IMPROVEMENT_THRESHOLD = 0.05   # 5% gain = improvement
    NEUTRAL_BAND = 0.05           # within ±5% = neutral

    def __init__(self, scorer: Optional[Scorer] = None):
        self._scorer = scorer or Scorer()

    def compare(self, baseline: Evaluation,
                candidate: Evaluation) -> ComparisonResult:
        """Compare two evaluations. Returns structured comparison."""
        baseline_score = baseline.total_score()
        candidate_score = candidate.total_score()
        delta = candidate_score - baseline_score

        details = []

        # Per-layer comparison
        baseline_map = {s.layer: s for s in baseline.scores}
        for cs in candidate.scores:
            bs = baseline_map.get(cs.layer)
            if bs:
                layer_delta = cs.score - bs.score
                if layer_delta < -self.IMPROVEMENT_THRESHOLD:
                    details.append(
                        f"REGRESSION in {cs.layer}: {bs.score:.2f} → {cs.score:.2f}"
                    )
                elif layer_delta > self.IMPROVEMENT_THRESHOLD:
                    details.append(
                        f"IMPROVEMENT in {cs.layer}: {bs.score:.2f} → {cs.score:.2f}"
                    )

        # Determine verdict
        if delta < -self.IMPROVEMENT_THRESHOLD:
            verdict = "REGRESSED"
            regression = True
            improvement = False
        elif delta > self.IMPROVEMENT_THRESHOLD:
            verdict = "IMPROVED"
            improvement = True
            regression = False
        else:
            verdict = "NEUTRAL"
            improvement = False
            regression = False

        return ComparisonResult(
            baseline_score=baseline_score,
            candidate_score=candidate_score,
            delta=delta,
            improvement_detected=improvement,
            regression_detected=regression,
            details=details,
            verdict=verdict,
        )

    def accept_improvement(self, candidate: ImprovementCandidate,
                           comparison: ComparisonResult,
                           required_evidence: bool = True) -> tuple[bool, str]:
        """Decide whether to accept an improvement candidate.

        Rules:
            1. Must NOT be REGRESSED
            2. Must have evidence
            3. LLM may NOT override this
        """
        if comparison.regression_detected:
            return False, "Regression detected — rejected"

        if comparison.verdict == "REGRESSED":
            return False, "Verdict REGRESSED — rejected"

        if required_evidence and not comparison.improvement_detected:
            return False, "No improvement detected — rejected"

        if not candidate.evidence_ids:
            return False, "No evidence — rejected"

        return True, f"Accepted: {comparison.summary()}"

    def can_accept(self, candidate: ImprovementCandidate,
                   comparison: ComparisonResult) -> bool:
        ok, _ = self.accept_improvement(candidate, comparison)
        return ok
