# core/evaluation/schema.py
"""Evaluation Engine v0.9 — schemas.

The evaluation engine produces evidence-backed verdicts.
A verdict is NEVER just text like "PASS" — it has structured evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


# ── Goal-level achievement states ─────────────────────────────────────

class AchievementState(str, Enum):
    """Explicit achievement states.

    These are DIFFERENT states and must not be conflated:
        TASK_COMPLETED  — a task was finished, regardless of correctness
        GOAL_ACHIEVED   — the original goal is satisfied
        SOLUTION_VALID  — output is valid against verification
        SOLUTION_OPTIMAL — valid AND meets efficiency criteria
    """
    TASK_COMPLETED = "TASK_COMPLETED"
    GOAL_ACHIEVED  = "GOAL_ACHIEVED"
    SOLUTION_VALID = "SOLUTION_VALID"
    SOLUTION_OPTIMAL = "SOLUTION_OPTIMAL"


# ── Evidence ──────────────────────────────────────────────────────────

class EvidenceType(str, Enum):
    TEST = "TEST"
    ASSERTION = "ASSERTION"
    COMMAND_RESULT = "COMMAND_RESULT"
    FILE_STATE = "FILE_STATE"
    CHECKPOINT = "CHECKPOINT"
    BENCHMARK = "BENCHMARK"
    REGRESSION = "REGRESSION"
    MANUAL = "MANUAL"


@dataclass
class Evidence:
    """A single piece of evidence for a verdict.

    `result` is "PASS" / "FAIL" / numeric / structured.
    `fingerprint` is an optional short hash to detect duplicates.
    """
    evidence_id: str
    type: str
    source: str
    result: str
    timestamp: str = ""
    fingerprint: str = ""
    run_id: str = ""
    task_id: str = ""

    def to_dict(self) -> dict:
        return {
            "evidence_id": self.evidence_id,
            "type": self.type,
            "source": self.source,
            "result": self.result,
            "timestamp": self.timestamp,
            "fingerprint": self.fingerprint,
            "run_id": self.run_id,
            "task_id": self.task_id,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Evidence":
        return cls(
            evidence_id=d["evidence_id"],
            type=d.get("type", EvidenceType.MANUAL.value),
            source=d.get("source", ""),
            result=d.get("result", ""),
            timestamp=d.get("timestamp", ""),
            fingerprint=d.get("fingerprint", ""),
            run_id=d.get("run_id", ""),
            task_id=d.get("task_id", ""),
        )

    def is_pass(self) -> bool:
        s = str(self.result).strip().lower()
        return s in ("pass", "passed", "ok", "success", "true", "1")

    def is_fail(self) -> bool:
        s = str(self.result).strip().lower()
        return s in ("fail", "failed", "error", "false", "0")


# ── Verdict ───────────────────────────────────────────────────────────

class Verdict(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"


# ── Score layers ──────────────────────────────────────────────────────

class ScoreLayer(str, Enum):
    CORRECTNESS = "correctness"
    REQUIREMENT_COVERAGE = "requirement_coverage"
    INTEGRATION = "integration"
    REGRESSION_SAFETY = "regression_safety"
    EFFICIENCY = "efficiency"


@dataclass
class LayerScore:
    """A single layer's score."""
    layer: str
    score: float   # 0.0 .. 1.0
    weight: float
    evidence_ids: list[str] = field(default_factory=list)
    notes: str = ""

    def weighted(self) -> float:
        return self.score * self.weight

    def to_dict(self) -> dict:
        return {
            "layer": self.layer,
            "score": self.score,
            "weight": self.weight,
            "evidence_ids": list(self.evidence_ids),
            "notes": self.notes,
        }


# ── Evaluation ────────────────────────────────────────────────────────

@dataclass
class Evaluation:
    """A full evaluation result."""
    evaluation_id: str
    target_id: str              # what we are evaluating (run, primitive, plan)
    achievement: str            # AchievementState
    verdict: str                # Verdict
    scores: list[LayerScore] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    failed_criteria: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    created_at: str = ""
    schema_version: int = 1

    def to_dict(self) -> dict:
        return {
            "evaluation_id": self.evaluation_id,
            "target_id": self.target_id,
            "achievement": self.achievement,
            "verdict": self.verdict,
            "scores": [s.to_dict() for s in self.scores],
            "evidence": [e.to_dict() for e in self.evidence],
            "failed_criteria": list(self.failed_criteria),
            "warnings": list(self.warnings),
            "created_at": self.created_at,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Evaluation":
        return cls(
            evaluation_id=d["evaluation_id"],
            target_id=d.get("target_id", ""),
            achievement=d.get("achievement", AchievementState.TASK_COMPLETED.value),
            verdict=d.get("verdict", Verdict.INCONCLUSIVE.value),
            scores=[LayerScore(**s) for s in d.get("scores", [])],
            evidence=[Evidence.from_dict(e) for e in d.get("evidence", [])],
            failed_criteria=list(d.get("failed_criteria", [])),
            warnings=list(d.get("warnings", [])),
            created_at=d.get("created_at", ""),
            schema_version=int(d.get("schema_version", 1)),
        )

    def total_score(self) -> float:
        if not self.scores:
            return 0.0
        total_weight = sum(s.weight for s in self.scores)
        if total_weight == 0:
            return 0.0
        return sum(s.weighted() for s in self.scores) / total_weight

    def is_valid(self) -> bool:
        return self.verdict == Verdict.PASS.value


# ── Improvement Candidate ─────────────────────────────────────────────

class ImprovementStatus(str, Enum):
    PROPOSED = "PROPOSED"
    TESTING = "TESTING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


@dataclass
class ImprovementCandidate:
    """A proposed improvement to the system."""
    candidate_id: str
    target: str                              # what to improve (e.g. "prim_id", "module:func")
    hypothesis: str
    baseline_evaluation_id: str
    proposed_change: str
    expected_benefit: str
    risk: str
    tests_required: list[str] = field(default_factory=list)
    benchmark_required: bool = False
    evidence_ids: list[str] = field(default_factory=list)
    verdict: str = ImprovementStatus.PROPOSED.value  # PROPOSED/TESTING/ACCEPTED/REJECTED
    verdict_reason: str = ""
    candidate_evaluation_id: str = ""
    created_by: str = "agent-core"
    created_at: str = ""
    schema_version: int = 1

    def to_dict(self) -> dict:
        return {
            "candidate_id": self.candidate_id,
            "target": self.target,
            "hypothesis": self.hypothesis,
            "baseline_evaluation_id": self.baseline_evaluation_id,
            "proposed_change": self.proposed_change,
            "expected_benefit": self.expected_benefit,
            "risk": self.risk,
            "tests_required": list(self.tests_required),
            "benchmark_required": self.benchmark_required,
            "evidence_ids": list(self.evidence_ids),
            "verdict": self.verdict,
            "verdict_reason": self.verdict_reason,
            "candidate_evaluation_id": self.candidate_evaluation_id,
            "created_at": self.created_at,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ImprovementCandidate":
        return cls(
            candidate_id=d["candidate_id"],
            target=d.get("target", ""),
            hypothesis=d.get("hypothesis", ""),
            baseline_evaluation_id=d.get("baseline_evaluation_id", ""),
            proposed_change=d.get("proposed_change", ""),
            expected_benefit=d.get("expected_benefit", ""),
            risk=d.get("risk", ""),
            tests_required=list(d.get("tests_required", [])),
            benchmark_required=bool(d.get("benchmark_required", False)),
            evidence_ids=list(d.get("evidence_ids", [])),
            verdict=d.get("verdict", ImprovementStatus.PROPOSED.value),
            verdict_reason=d.get("verdict_reason", ""),
            candidate_evaluation_id=d.get("candidate_evaluation_id", ""),
            created_at=d.get("created_at", ""),
            schema_version=int(d.get("schema_version", 1)),
        )


# ── ID generation ─────────────────────────────────────────────────────

import time as _time


def generate_eval_id() -> str:
    return f"EVAL-{int(_time.time() * 1000) % 100000:05d}"


def generate_improvement_id() -> str:
    return f"IMP-{int(_time.time() * 1000) % 100000:05d}"
