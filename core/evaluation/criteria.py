# core/evaluation/criteria.py
"""Evaluation criteria definitions — what must pass for each layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Criterion:
    """A single evaluation criterion."""
    code: str
    layer: str          # ScoreLayer value
    description: str
    required: bool = True
    weight: float = 1.0
    min_score: float = 0.0

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "layer": self.layer,
            "description": self.description,
            "required": self.required,
            "weight": self.weight,
            "min_score": self.min_score,
        }


# Default criteria set

CORRECTNESS_CRITERIA = [
    Criterion("CORR_EXEC", "correctness",
              "All tasks executed successfully"),
    Criterion("CORR_VERIFY", "correctness",
              "Verification passed for each task"),
    Criterion("CORR_NO_ERRORS", "correctness",
              "No runtime errors occurred"),
]

REQUIREMENT_COVERAGE_CRITERIA = [
    Criterion("REQ_COMPLETE", "requirement_coverage",
              "All required steps were executed"),
    Criterion("REQ_ORDER", "requirement_coverage",
              "Steps were executed in correct order"),
    Criterion("REQ_OUTPUT", "requirement_coverage",
              "Expected output was produced"),
]

INTEGRATION_CRITERIA = [
    Criterion("INT_KNOWLEDGE", "integration",
              "Knowledge retrieval was used when relevant"),
    Criterion("INT_EXPERIENCE", "integration",
              "Experience was recorded"),
    Criterion("INT_LIFECYCLE", "integration",
              "All lifecycle transitions are valid"),
]

REGRESSION_SAFETY_CRITERIA = [
    Criterion("REG_TESTS", "regression_safety",
              "Existing tests still pass"),
    Criterion("REG_BEHAVIOR", "regression_safety",
              "Existing behavior preserved"),
    Criterion("REG_NO_REGRESSION", "regression_safety",
              "No new failures in existing functionality"),
]

EFFICIENCY_CRITERIA = [
    Criterion("EFF_LLM", "efficiency",
              "LLM calls within budget"),
    Criterion("EFF_TIME", "efficiency",
              "Runtime within time limit"),
    Criterion("EFF_RETRY", "efficiency",
              "Retry count within limit"),
]

ALL_CRITERIA = (
    CORRECTNESS_CRITERIA
    + REQUIREMENT_COVERAGE_CRITERIA
    + INTEGRATION_CRITERIA
    + REGRESSION_SAFETY_CRITERIA
    + EFFICIENCY_CRITERIA
)


def get_criteria(layer: Optional[str] = None) -> list[Criterion]:
    """Get criteria for a layer, or all criteria."""
    if layer:
        return [c for c in ALL_CRITERIA if c.layer == layer]
    return list(ALL_CRITERIA)


def get_criterion(code: str) -> Optional[Criterion]:
    for c in ALL_CRITERIA:
        if c.code == code:
            return c
    return None


def get_required_codes(layer: Optional[str] = None) -> set[str]:
    """All required criterion codes."""
    return {c.code for c in get_criteria(layer) if c.required}
