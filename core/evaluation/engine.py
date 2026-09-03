# core/evaluation/engine.py
"""EvaluationEngine — high-level orchestrator."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from core.evaluation.schema import (
    Evaluation, Evidence, ImprovementCandidate,
    Verdict, AchievementState,
)
from core.evaluation.criteria import get_required_codes
from core.evaluation.evidence import EvidenceLedger
from core.evaluation.evaluator import Evaluator, EvaluationContext
from core.evaluation.scorer import Scorer
from core.evaluation.comparator import Comparator, ComparisonResult
from core.evaluation.improvement import ImprovementEngine, ImprovementStatus
from core.evaluation.benchmark import Benchmark, BenchmarkResult, BenchmarkReport


@dataclass
class EvaluationEngineStats:
    total_evaluations: int = 0
    pass_count: int = 0
    fail_count: int = 0
    improvement_candidates: int = 0
    improvements_accepted: int = 0
    improvements_rejected: int = 0


class EvaluationEngine:
    """Public API for the evaluation subsystem.

    Usage:
        engine = EvaluationEngine()
        ev = engine.evaluate(target_id, evidence_list, achievement)
        comparison = engine.compare(baseline_ev, candidate_ev)
        ok, reason = engine.decide(candidate, comparison)
    """

    def __init__(self):
        self._ledger = EvidenceLedger()
        self._evaluator = Evaluator(ledger=self._ledger)
        self._scorer = Scorer()
        self._comparator = Comparator(scorer=self._scorer)
        self._improver = ImprovementEngine(
            comparator=self._comparator,
            evaluator=self._evaluator,
        )
        self._benchmark = Benchmark()

    # ── Evaluation ────────────────────────────────────────────────────

    def evaluate(self, target_id: str, evidence: list[Evidence],
                 achievement: str,
                 failed_criteria: Optional[list[str]] = None,
                 warnings: Optional[list[str]] = None) -> Evaluation:
        return self._evaluator.evaluate_from_evidence(
            evaluation_id="",
            target_id=target_id,
            achievement=achievement,
            evidence=evidence,
            failed_criteria=failed_criteria,
            warnings=warnings,
        )

    def evaluate_run(self, run_id: str, evidence: list[Evidence]) -> Evaluation:
        """Evaluate a run with evidence."""
        failed = []
        warns = []
        # Check if any evidence is a failure
        fail_ev = [e for e in evidence if e.is_fail()]
        if fail_ev:
            failed.append("EXEC_FAILURE")
            warns.append(f"{len(fail_ev)} failure evidence items")
        achievement = AchievementState.GOAL_ACHIEVED.value
        if failed:
            achievement = AchievementState.TASK_COMPLETED.value
        return self.evaluate(run_id, evidence, achievement, failed, warns)

    # ── Comparison ─────────────────────────────────────────────────────

    def compare(self, baseline: Evaluation,
                candidate: Evaluation) -> ComparisonResult:
        return self._comparator.compare(baseline, candidate)

    def decide(self, candidate: ImprovementCandidate,
               comparison: ComparisonResult,
               evidence_ids: Optional[list[str]] = None) -> tuple[bool, str]:
        """Decide improvement acceptance. Returns (accepted, reason)."""
        result, reason = self._improver.decide(
            candidate.candidate_id, comparison, evidence_ids
        )
        return result.verdict == ImprovementStatus.ACCEPTED.value, reason

    # ── Evidence ──────────────────────────────────────────────────────

    def record_evidence(self, evidence: Evidence) -> Evidence:
        return self._ledger.record(evidence)

    def get_evidence(self, evidence_id: str) -> Optional[Evidence]:
        return self._ledger.get(evidence_id)

    def list_evidence(self, evidence_type: Optional[str] = None) -> list[Evidence]:
        return self._ledger.filter(evidence_type=evidence_type)

    # ── Improvement ───────────────────────────────────────────────────

    def propose_improvement(self, **kwargs) -> ImprovementCandidate:
        return self._improver.propose(**kwargs)

    def start_testing(self, candidate_id: str) -> ImprovementCandidate:
        return self._improver.start_testing(candidate_id)

    def get_candidate(self, candidate_id: str) -> Optional[ImprovementCandidate]:
        return self._improver.get(candidate_id)

    def list_candidates(self) -> list[ImprovementCandidate]:
        return self._improver.list_all()

    # ── Benchmark ─────────────────────────────────────────────────────

    def benchmark_knowledge_retrieval(self, query: str, n_prims: int = 50) -> BenchmarkResult:
        """Benchmark knowledge retrieval time."""
        # Lazy import to avoid circular
        from core.knowledge.engine import KnowledgeEngine
        import tempfile, shutil

        d = tempfile.mkdtemp()
        ke = KnowledgeEngine(d)
        for i in range(n_prims):
            ke.create_primitive(
                domain=f"d{i%5}",
                concept=f"concept-{i}",
                description=f"description {i}",
            )

        def fn():
            ke.retrieve(query, top_k=5)

        r = self._benchmark.run("knowledge_retrieval", fn, iterations=50)
        shutil.rmtree(d, ignore_errors=True)
        return r

    def benchmark_experience_recording(self, n: int = 100) -> BenchmarkResult:
        """Benchmark experience recording overhead."""
        from core.experience.engine import ExperienceEngine
        import tempfile, shutil

        d = tempfile.mkdtemp()
        ee = ExperienceEngine(d)

        def fn():
            from core.experience.schema import Experience
            import time
            e = Experience(
                run_id=f"RUN-{time.time_ns() % 100000:05d}",
                goal="test",
                project_id="bench",
                action="x",
                outcome="success",
            )
            try:
                ee.record_experience(e)
            except Exception:
                pass

        r = self._benchmark.run("experience_recording", fn, iterations=n)
        shutil.rmtree(d, ignore_errors=True)
        return r

    def benchmark_evaluation(self, n_ev: int = 20) -> BenchmarkResult:
        """Benchmark evaluation overhead."""
        from core.evaluation.schema import Evidence, EvidenceType

        ev_list = [
            Evidence(
                evidence_id=f"ev-{i}",
                type=EvidenceType.TEST.value,
                source=f"test-{i}",
                result="PASS",
            )
            for i in range(n_ev)
        ]

        def fn():
            self.evaluate(f"bench-{id(fn)}", ev_list, "SOLUTION_VALID")

        return self._benchmark.run("evaluation", fn, iterations=50, warmup=5)

    def run_benchmarks(self) -> BenchmarkReport:
        report = BenchmarkReport()
        from datetime import datetime, timezone
        report.timestamp = datetime.now(timezone.utc).isoformat()
        try:
            report.add(self.benchmark_knowledge_retrieval("concept", n_prims=50))
        except Exception:
            pass
        try:
            report.add(self.benchmark_experience_recording(n=50))
        except Exception:
            pass
        try:
            report.add(self.benchmark_evaluation(n_ev=20))
        except Exception:
            pass
        return report

    # ── Stats ────────────────────────────────────────────────────────

    def stats(self) -> EvaluationEngineStats:
        cands = self._improver.list_all()
        return EvaluationEngineStats(
            total_evaluations=self._ledger.count(),
            improvement_candidates=len(cands),
            improvements_accepted=sum(
                1 for c in cands if c.verdict == ImprovementStatus.ACCEPTED.value
            ),
            improvements_rejected=sum(
                1 for c in cands if c.verdict == ImprovementStatus.REJECTED.value
            ),
        )
