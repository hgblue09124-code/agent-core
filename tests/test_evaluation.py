#!/usr/bin/env python3
# tests/test_evaluation.py
"""Evaluation Engine v0.9 tests."""

import json
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))


def _ev(eid: str = "e1", type_: str = "TEST", result: str = "PASS",
         source: str = "test_x", run_id: str = "R1", task_id: str = "T1"):
    from core.evaluation.schema import Evidence
    return Evidence(
        evidence_id=eid, type=type_, source=source, result=result,
        run_id=run_id, task_id=task_id,
    )


# ── Schema ───────────────────────────────────────────────────────────

class TestSchema(unittest.TestCase):

    def test_evidence_roundtrip(self):
        from core.evaluation.schema import Evidence
        e = _ev()
        d = e.to_dict()
        e2 = Evidence.from_dict(d)
        self.assertEqual(e.evidence_id, e2.evidence_id)
        self.assertEqual(e.type, e2.type)
        self.assertEqual(e.is_pass(), e2.is_pass())

    def test_evidence_pass_detection(self):
        for r, expected in [("PASS", True), ("passed", True), ("ok", True),
                            ("ERROR", False), ("FAIL", False), ("fail", False)]:
            e = _ev(result=r)
            self.assertEqual(e.is_pass(), expected,
                             f"result={r!r} should be pass={expected}")

    def test_evidence_fail_detection(self):
        for r in ["FAIL", "failed", "error", "false", "0"]:
            self.assertTrue(_ev(result=r).is_fail(), f"result={r!r} should be fail")

    def test_evaluation_total_score(self):
        from core.evaluation.schema import Evaluation, LayerScore, Verdict
        e = Evaluation(
            evaluation_id="E1",
            target_id="T1",
            achievement="GOAL_ACHIEVED",
            verdict=Verdict.PASS.value,
            scores=[
                LayerScore(layer="correctness", score=1.0, weight=0.5),
                LayerScore(layer="efficiency", score=0.5, weight=0.5),
            ],
        )
        self.assertAlmostEqual(e.total_score(), 0.75)

    def test_evaluation_roundtrip(self):
        from core.evaluation.schema import Evaluation
        e = Evaluation(
            evaluation_id="E1",
            target_id="T1",
            achievement="SOLUTION_VALID",
            verdict="PASS",
        )
        d = e.to_dict()
        e2 = Evaluation.from_dict(d)
        self.assertEqual(e.evaluation_id, e2.evaluation_id)
        self.assertEqual(e.achievement, e2.achievement)

    def test_achievement_state_distinct(self):
        """The 4 states must be distinct values."""
        from core.evaluation.schema import AchievementState
        states = {
            AchievementState.TASK_COMPLETED,
            AchievementState.GOAL_ACHIEVED,
            AchievementState.SOLUTION_VALID,
            AchievementState.SOLUTION_OPTIMAL,
        }
        self.assertEqual(len(states), 4)


# ── Scorer ───────────────────────────────────────────────────────────

class TestScorer(unittest.TestCase):

    def test_correctness_all_pass(self):
        from core.evaluation.scorer import Scorer
        s = Scorer()
        r = s.score_correctness([_ev(eid="e1", result="PASS"),
                                  _ev(eid="e2", result="PASS")])
        self.assertEqual(r.score, 1.0)

    def test_correctness_all_fail(self):
        from core.evaluation.scorer import Scorer
        s = Scorer()
        r = s.score_correctness([_ev(eid="e1", result="FAIL"),
                                  _ev(eid="e2", result="FAIL")])
        self.assertEqual(r.score, 0.0)

    def test_correctness_mixed(self):
        from core.evaluation.scorer import Scorer
        s = Scorer()
        r = s.score_correctness([_ev(eid="e1", result="PASS"),
                                  _ev(eid="e2", result="FAIL")])
        self.assertEqual(r.score, 0.5)

    def test_empty_evidence(self):
        from core.evaluation.scorer import Scorer
        s = Scorer()
        r = s.score_correctness([])
        self.assertEqual(r.score, 0.0)

    def test_regression_severe(self):
        """Any regression → score *= 0.5."""
        from core.evaluation.scorer import Scorer
        s = Scorer()
        r = s.score_regression_safety([_ev(result="PASS"),
                                        _ev(eid="e2", result="FAIL")])
        # 1 pass + 1 fail = 0.5 * 0.5 = 0.25
        self.assertLessEqual(r.score, 0.5)

    def test_weighted_total(self):
        from core.evaluation.scorer import Scorer
        from core.evaluation.schema import LayerScore
        s = Scorer()
        scores = [
            LayerScore(layer="correctness", score=1.0, weight=0.5),
            LayerScore(layer="efficiency", score=0.0, weight=0.5),
        ]
        self.assertAlmostEqual(s.weighted_total(scores), 0.5)


# ── Evidence ledger ──────────────────────────────────────────────────

class TestEvidenceLedger(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(self.tmpdir, ignore_errors=True))

    def test_record_and_get(self):
        from core.evaluation.evidence import EvidenceLedger
        l = EvidenceLedger(str(Path(self.tmpdir) / "ev.json"))
        l.record(_ev())
        self.assertEqual(l.count(), 1)
        self.assertIsNotNone(l.get("e1"))

    def test_idempotent(self):
        from core.evaluation.evidence import EvidenceLedger
        l = EvidenceLedger(str(Path(self.tmpdir) / "ev.json"))
        l.record(_ev())
        l.record(_ev())  # same id
        self.assertEqual(l.count(), 1)

    def test_secret_rejected(self):
        from core.evaluation.evidence import EvidenceLedger
        l = EvidenceLedger(str(Path(self.tmpdir) / "ev.json"))
        with self.assertRaises(ValueError):
            l.record(_ev(source="leak: sk-abcdefghijklmnopqrstuvwxyz12345"))

    def test_filter(self):
        from core.evaluation.evidence import EvidenceLedger
        l = EvidenceLedger(str(Path(self.tmpdir) / "ev.json"))
        l.record(_ev(eid="e1", type_="TEST"))
        l.record(_ev(eid="e2", type_="BENCHMARK"))
        tests = l.filter(evidence_type="TEST")
        self.assertEqual(len(tests), 1)


# ── Evaluator ────────────────────────────────────────────────────────

class TestEvaluator(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(self.tmpdir, ignore_errors=True))

    def _full_evidence(self):
        """Evidence for all 5 layers."""
        return [
            _ev(eid="e1", type_="TEST"),
            _ev(eid="e2", type_="ASSERTION"),
            _ev(eid="e3", type_="FILE_STATE"),
            _ev(eid="e4", type_="CHECKPOINT"),
            _ev(eid="e5", type_="REGRESSION"),
            _ev(eid="e6", type_="BENCHMARK"),
        ]

    def test_pass_with_good_evidence(self):
        from core.evaluation.engine import EvaluationEngine
        e = EvaluationEngine()
        ev = e.evaluate("T1", self._full_evidence(), "SOLUTION_VALID")
        self.assertEqual(ev.verdict, "PASS")

    def test_fail_when_no_evidence(self):
        from core.evaluation.engine import EvaluationEngine
        e = EvaluationEngine()
        ev = e.evaluate("T1", [_ev(result="FAIL")], "SOLUTION_VALID")
        self.assertEqual(ev.verdict, "FAIL")

    def test_fail_with_failed_criteria(self):
        from core.evaluation.engine import EvaluationEngine
        e = EvaluationEngine()
        ev = e.evaluate("T1", self._full_evidence(), "GOAL_ACHIEVED",
                        failed_criteria=["REQ_OUTPUT"])
        self.assertEqual(ev.verdict, "FAIL")
        self.assertIn("REQ_OUTPUT", ev.failed_criteria)

    def test_pass_when_failed_criteria_none(self):
        from core.evaluation.engine import EvaluationEngine
        e = EvaluationEngine()
        ev = e.evaluate("T1", self._full_evidence(), "GOAL_ACHIEVED",
                        failed_criteria=[])
        self.assertEqual(ev.verdict, "PASS")

    def test_evidence_grouped_by_layer(self):
        from core.evaluation.engine import EvaluationEngine
        e = EvaluationEngine()
        ev = e.evaluate("T1", [
            _ev(eid="e1", type_="TEST"),
            _ev(eid="e2", type_="BENCHMARK"),
        ], "SOLUTION_VALID")
        # Both layers should be scored
        layers = {s.layer for s in ev.scores}
        self.assertIn("correctness", layers)
        self.assertIn("efficiency", layers)


# ── Comparator ───────────────────────────────────────────────────────

class TestComparator(unittest.TestCase):

    def _make_eval(self, scores_dict: dict):
        from core.evaluation.schema import Evaluation, LayerScore
        from core.evaluation.scorer import DEFAULT_WEIGHTS
        scores = [
            LayerScore(layer=k, score=v, weight=DEFAULT_WEIGHTS.get(k, 0.2))
            for k, v in scores_dict.items()
        ]
        return Evaluation(
            evaluation_id="E1",
            target_id="T1",
            achievement="GOAL_ACHIEVED",
            verdict="PASS",
            scores=scores,
        )

    def test_neutral(self):
        from core.evaluation.comparator import Comparator
        c = Comparator()
        b = self._make_eval({"correctness": 0.8, "efficiency": 0.8})
        x = self._make_eval({"correctness": 0.8, "efficiency": 0.8})
        r = c.compare(b, x)
        self.assertEqual(r.verdict, "NEUTRAL")
        self.assertFalse(r.regression_detected)

    def test_improvement(self):
        from core.evaluation.comparator import Comparator
        c = Comparator()
        b = self._make_eval({"correctness": 0.5, "efficiency": 0.5})
        x = self._make_eval({"correctness": 0.9, "efficiency": 0.9})
        r = c.compare(b, x)
        self.assertEqual(r.verdict, "IMPROVED")
        self.assertTrue(r.improvement_detected)
        self.assertGreater(r.delta, 0.05)

    def test_regression(self):
        from core.evaluation.comparator import Comparator
        c = Comparator()
        b = self._make_eval({"correctness": 0.9, "efficiency": 0.9})
        x = self._make_eval({"correctness": 0.5, "efficiency": 0.5})
        r = c.compare(b, x)
        self.assertEqual(r.verdict, "REGRESSED")
        self.assertTrue(r.regression_detected)

    def test_llm_cannot_override(self):
        """Even if LLM says 'this is good', regression must reject."""
        from core.evaluation.comparator import Comparator
        from core.evaluation.improvement import ImprovementEngine
        from core.evaluation.schema import ImprovementStatus, Evaluation, LayerScore
        from core.evaluation.scorer import DEFAULT_WEIGHTS

        c = Comparator()
        ie = ImprovementEngine(comparator=c)
        cand = ie.propose(
            target="x", hypothesis="make it better",
            baseline_eval_id="b", proposed_change="x",
            expected_benefit="+1", risk="low",
        )
        ie.start_testing(cand.candidate_id)
        b = Evaluation(
            evaluation_id="E-BASE",
            target_id="T1",
            achievement="GOAL_ACHIEVED",
            verdict="PASS",
            scores=[LayerScore(layer="correctness", score=0.9,
                               weight=DEFAULT_WEIGHTS["correctness"])],
        )
        x = Evaluation(
            evaluation_id="E-CAND",
            target_id="T1",
            achievement="GOAL_ACHIEVED",
            verdict="PASS",
            scores=[LayerScore(layer="correctness", score=0.3,
                               weight=DEFAULT_WEIGHTS["correctness"])],
        )
        comp = c.compare(b, x)
        result, reason = ie.decide(cand.candidate_id, comp, evidence_ids=["ev1"])
        self.assertEqual(result.verdict, ImprovementStatus.REJECTED.value)


# ── Improvement lifecycle ────────────────────────────────────────────

class TestImprovement(unittest.TestCase):

    def test_propose_to_testing(self):
        from core.evaluation.improvement import ImprovementEngine, ImprovementStatus
        ie = ImprovementEngine()
        cand = ie.propose(target="x", hypothesis="h", baseline_eval_id="b",
                          proposed_change="c", expected_benefit="e", risk="r")
        self.assertEqual(cand.verdict, ImprovementStatus.PROPOSED.value)
        ie.start_testing(cand.candidate_id)
        cand2 = ie.get(cand.candidate_id)
        self.assertEqual(cand2.verdict, ImprovementStatus.TESTING.value)

    def test_cannot_start_testing_from_terminal(self):
        from core.evaluation.improvement import ImprovementEngine, ImprovementError
        ie = ImprovementEngine()
        cand = ie.propose(target="x", hypothesis="h", baseline_eval_id="b",
                          proposed_change="c", expected_benefit="e", risk="r")
        ie.start_testing(cand.candidate_id)
        ie.decide(cand.candidate_id,
                  type('Mock', (), {
                      'baseline_score': 0.5, 'candidate_score': 0.9,
                      'delta': 0.4, 'improvement_detected': True,
                      'regression_detected': False, 'details': [],
                      'verdict': 'IMPROVED', 'summary': lambda self: 'mock'
                  })(),
                  evidence_ids=["ev1"])
        with self.assertRaises(ImprovementError):
            ie.start_testing(cand.candidate_id)

    def test_manual_reject(self):
        from core.evaluation.improvement import ImprovementEngine, ImprovementStatus
        ie = ImprovementEngine()
        cand = ie.propose(target="x", hypothesis="h", baseline_eval_id="b",
                          proposed_change="c", expected_benefit="e", risk="r")
        ie.reject(cand.candidate_id, "just no")
        c2 = ie.get(cand.candidate_id)
        self.assertEqual(c2.verdict, ImprovementStatus.REJECTED.value)
        self.assertEqual(c2.verdict_reason, "just no")

    def test_accepted_requires_evidence(self):
        """ACCEPTED must require evidence_ids."""
        from core.evaluation.improvement import ImprovementEngine, ImprovementStatus
        from core.evaluation.schema import LayerScore
        from core.evaluation.comparator import ComparisonResult
        ie = ImprovementEngine()
        cand = ie.propose(target="x", hypothesis="h", baseline_eval_id="b",
                          proposed_change="c", expected_benefit="e", risk="r")
        ie.start_testing(cand.candidate_id)
        comp = ComparisonResult(
            baseline_score=0.5, candidate_score=0.9, delta=0.4,
            improvement_detected=True, regression_detected=False,
            details=[], verdict="IMPROVED"
        )
        # No evidence
        result, reason = ie.decide(cand.candidate_id, comp, evidence_ids=[])
        self.assertEqual(result.verdict, ImprovementStatus.REJECTED.value)


# ── Engine integration ───────────────────────────────────────────────

class TestEngine(unittest.TestCase):

    def test_full_evaluate_run(self):
        from core.evaluation.engine import EvaluationEngine
        e = EvaluationEngine()
        evidence = [
            _ev(eid="e1", type_="TEST", result="PASS"),
            _ev(eid="e2", type_="TEST", result="PASS"),
            _ev(eid="e3", type_="BENCHMARK", result="PASS"),
            _ev(eid="e4", type_="FILE_STATE", result="PASS"),
            _ev(eid="e5", type_="CHECKPOINT", result="PASS"),
        ]
        ev = e.evaluate_run("R1", evidence)
        self.assertEqual(ev.verdict, "PASS")
        self.assertGreater(ev.total_score(), 0.5)

    def test_benchmarks_run(self):
        from core.evaluation.engine import EvaluationEngine
        e = EvaluationEngine()
        report = e.run_benchmarks()
        # Should have at least one result
        self.assertGreater(len(report.results), 0)

    def test_stats(self):
        from core.evaluation.engine import EvaluationEngine
        e = EvaluationEngine()
        e.record_evidence(_ev())
        s = e.stats()
        self.assertGreaterEqual(s.total_evaluations, 1)


# ── Adversarial ──────────────────────────────────────────────────────

class TestAdversarial(unittest.TestCase):

    def test_no_pass_without_evidence(self):
        from core.evaluation.engine import EvaluationEngine
        e = EvaluationEngine()
        # No evidence at all
        ev = e.evaluate("T1", [], "GOAL_ACHIEVED")
        # Should fail because no evidence
        self.assertEqual(ev.verdict, "FAIL")

    def test_secret_in_evidence(self):
        from core.evaluation.engine import EvaluationEngine
        e = EvaluationEngine()
        with self.assertRaises(ValueError):
            e.record_evidence(_ev(source="api_key=sk-abcdefghijklmnopqrstuvwxyz12345"))

    def test_regression_always_rejected(self):
        from core.evaluation.improvement import ImprovementEngine
        from core.evaluation.comparator import ComparisonResult
        from core.evaluation.schema import ImprovementStatus
        ie = ImprovementEngine()
        cand = ie.propose(target="x", hypothesis="h", baseline_eval_id="b",
                          proposed_change="c", expected_benefit="e", risk="r")
        ie.start_testing(cand.candidate_id)
        comp = ComparisonResult(
            baseline_score=0.9, candidate_score=0.1, delta=-0.8,
            improvement_detected=False, regression_detected=True,
            details=[], verdict="REGRESSED"
        )
        result, _ = ie.decide(cand.candidate_id, comp, evidence_ids=["ev1"])
        self.assertEqual(result.verdict, ImprovementStatus.REJECTED.value)


# ── Performance ─────────────────────────────────────────────────────

class TestPerformance(unittest.TestCase):

    def test_100_evaluations(self):
        from core.evaluation.engine import EvaluationEngine
        e = EvaluationEngine()
        ev = [_ev(eid=f"e-{i}") for i in range(100)]
        t0 = time.time()
        for i in range(50):
            e.evaluate(f"target-{i}", ev[:5], "SOLUTION_VALID")
        elapsed = time.time() - t0
        self.assertLess(elapsed, 3.0, f"took {elapsed:.2f}s")


if __name__ == "__main__":
    unittest.main()
