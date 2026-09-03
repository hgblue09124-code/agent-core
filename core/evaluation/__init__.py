# core/evaluation/__init__.py
"""Evaluation Engine v0.9 — evidence-backed verdicts and improvement lifecycle."""

from core.evaluation.schema import (
    Evidence, EvidenceType, AchievementState, Verdict,
    LayerScore, Evaluation, ScoreLayer,
    ImprovementCandidate, ImprovementStatus,
    generate_eval_id, generate_improvement_id,
)
from core.evaluation.criteria import (
    Criterion, get_criteria, get_criterion, get_required_codes,
    ALL_CRITERIA,
)
from core.evaluation.evidence import EvidenceLedger
from core.evaluation.scorer import Scorer, ScoreResult, DEFAULT_WEIGHTS
from core.evaluation.evaluator import Evaluator, EvaluationContext
from core.evaluation.comparator import Comparator, ComparisonResult
from core.evaluation.improvement import ImprovementEngine, ImprovementError
from core.evaluation.benchmark import Benchmark, BenchmarkResult, BenchmarkReport
from core.evaluation.engine import EvaluationEngine, EvaluationEngineStats

__all__ = [
    "Evidence", "EvidenceType", "AchievementState", "Verdict",
    "LayerScore", "Evaluation", "ScoreLayer",
    "ImprovementCandidate", "ImprovementStatus",
    "generate_eval_id", "generate_improvement_id",
    "Criterion", "get_criteria", "get_criterion", "get_required_codes", "ALL_CRITERIA",
    "EvidenceLedger",
    "Scorer", "ScoreResult", "DEFAULT_WEIGHTS",
    "Evaluator", "EvaluationContext",
    "Comparator", "ComparisonResult",
    "ImprovementEngine", "ImprovementError",
    "Benchmark", "BenchmarkResult", "BenchmarkReport",
    "EvaluationEngine", "EvaluationEngineStats",
]
