#!/usr/bin/env python3
# tests/test_adversarial_spec.py
"""Adversarial tests against the Kernel Specification and Constitution.

The objective of these tests is NOT to prove the system works.
The objective is to discover how it can fail.

Each test corresponds to an adversarial case enumerated in the
SPECIFICATION.md (Section 13) and CONSTITUTION.md.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))


# ── Adversarial: Malformed Inputs ─────────────────────────────────────────────

class TestAdversarialMalformedInputs(unittest.TestCase):
    """Adversarial: Malformed task contracts and inputs."""

    def test_adv01_malformed_task_contract_rejected(self):
        """ADV-01: Malformed Task Contract must be rejected."""
        from core.tasks.schema import TaskConstructionContract
        # Missing objective
        c = TaskConstructionContract(
            contract_id="TCC-BAD-01",
            objective="",  # Empty
            expected_evidence_types=["TEST"],
            acceptance_criteria=["x"],
        )
        valid, reason = c.validate()
        self.assertFalse(valid, "Malformed contract must fail validation")
        self.assertIn("objective", reason)

    def test_adv02_malformed_contract_id_rejected(self):
        """ADV-02: Contract ID with special chars must be rejected."""
        from core.tasks.schema import TaskConstructionContract
        c = TaskConstructionContract(
            contract_id="bad id with spaces!",
            objective="x",
            expected_evidence_types=["TEST"],
            acceptance_criteria=["x"],
        )
        valid, reason = c.validate()
        self.assertFalse(valid, "Bad contract_id must fail")
        self.assertIn("contract_id", reason)

    def test_adv03_malformed_evidence_type_rejected(self):
        """ADV-03: Unknown evidence type must be rejected."""
        from core.tasks.schema import TaskConstructionContract
        c = TaskConstructionContract(
            contract_id="TCC-BAD-03",
            objective="x",
            expected_evidence_types=["UNKNOWN_TYPE"],
            acceptance_criteria=["x"],
        )
        valid, reason = c.validate()
        self.assertFalse(valid)
        self.assertIn("evidence type", reason)

    def test_adv04_malformed_failure_action_rejected(self):
        """ADV-04: Unknown failure action must be rejected."""
        from core.tasks.schema import TaskConstructionContract
        c = TaskConstructionContract(
            contract_id="TCC-BAD-04",
            objective="x",
            expected_evidence_types=["TEST"],
            acceptance_criteria=["x"],
            failure_actions=["INVALID_ACTION"],
        )
        valid, reason = c.validate()
        self.assertFalse(valid)
        self.assertIn("failure_action", reason)

    def test_adv05_negative_max_retries_rejected(self):
        """ADV-05: Negative max_retries must be rejected."""
        from core.tasks.schema import TaskConstructionContract
        c = TaskConstructionContract(
            contract_id="TCC-BAD-05",
            objective="x",
            expected_evidence_types=["TEST"],
            acceptance_criteria=["x"],
            max_retries=-1,
        )
        valid, reason = c.validate()
        self.assertFalse(valid)
        self.assertIn("max_retries", reason)

    def test_adv06_corrupt_knowledge_file_returns_none(self):
        """ADV-06: Corrupt knowledge file must return None, not crash."""
        from core.knowledge.store import PrimitiveStore
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(d, ignore_errors=True))
        s = PrimitiveStore(d)
        (Path(d) / "CORRUPT.json").write_text("{ bad")
        self.assertIsNone(s.get("CORRUPT"))
        # list_all must not crash
        all_prims = s.list_all()
        self.assertEqual(len(all_prims), 0)

    def test_adv07_corrupt_experience_file_returns_none(self):
        """ADV-07: Corrupt experience file must return None, not crash."""
        from core.experience.store import ExperienceStore
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(d, ignore_errors=True))
        s = ExperienceStore(d)
        (Path(d) / "RUN-BAD.json").write_text("garbage")
        self.assertIsNone(s.get("RUN-BAD"))

    def test_adv08_corrupt_evidence_file_handled(self):
        """ADV-08: Corrupt evidence file must not crash ledger."""
        from core.evaluation.evidence import EvidenceLedger
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(d, ignore_errors=True))
        path = str(Path(d) / "ev.json")
        (Path(d) / "ev.json").write_text("{ not valid")
        l = EvidenceLedger(path)
        self.assertEqual(l.count(), 0)


# ── Adversarial: Missing / Fabricated Evidence ────────────────────────────────

class TestAdversarialEvidence(unittest.TestCase):
    """Adversarial: Evidence-related attacks."""

    def test_adv09_no_evidence_returns_fail(self):
        """ADV-09: No evidence → verdict FAIL (no fabricated pass)."""
        from core.evaluation.engine import EvaluationEngine
        e = EvaluationEngine()
        ev = e.evaluate("T1", [], "GOAL_ACHIEVED")
        self.assertEqual(ev.verdict, "FAIL",
                        "Empty evidence must not produce PASS")

    def test_adv10_evidence_with_secrets_refused(self):
        """ADV-10: Evidence with secret content must be refused."""
        from core.evaluation.evidence import EvidenceLedger
        from core.evaluation.schema import Evidence
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(d, ignore_errors=True))
        l = EvidenceLedger(str(Path(d) / "ev.json"))
        with self.assertRaises(ValueError):
            l.record(Evidence(
                evidence_id="e1", type="MANUAL",
                source="leak", result="sk-abcdefghijklmnopqrstuvwxyz12345",
            ))

    def test_adv11_experience_action_with_secrets_scrubbed(self):
        """ADV-11: Secret in experience action must be scrubbed."""
        from core.experience.recorder import ExperienceRecorder
        r = ExperienceRecorder()
        r.start(run_id="R1", goal="x", project_id="p")
        r.record_action("login sk-abcdefghijklmnopqrstuvwxyz12345")
        r.set_outcome("success")
        exp = r.finalize().to_experience()
        self.assertNotIn("abcdefghijklmnopqrstuvwxyz", exp.action)

    def test_adv12_knowledge_with_secrets_rejected(self):
        """ADV-12: Secret in knowledge must be rejected."""
        import tempfile, shutil
        from core.knowledge.engine import KnowledgeEngine
        from core.knowledge.store import StoreError
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(d, ignore_errors=True))
        ke = KnowledgeEngine(d)
        p = ke.create_primitive(domain="d", concept="x", description="y")
        p.provenance.notes = "sk-abcdefghijklmnopqrstuvwxyz12345"
        with self.assertRaises(StoreError):
            ke.update_primitive(p)


# ── Adversarial: Authority / Boundary Violations ──────────────────────────────

class TestAdversarialAuthority(unittest.TestCase):
    """Adversarial: Authority boundary violations."""

    def test_adv13_llm_cannot_declare_verification(self):
        """ADV-13: LLM cannot declare its own verification."""
        from core.kernel.policy import PolicyEngine
        p = PolicyEngine()
        self.assertFalse(p.can_llm_declare_verification())

    def test_adv14_llm_cannot_promote_knowledge(self):
        """ADV-14: LLM cannot promote knowledge."""
        from core.kernel.policy import PolicyEngine
        p = PolicyEngine()
        self.assertFalse(p.can_llm_promote_knowledge())

    def test_adv15_llm_cannot_accept_improvement(self):
        """ADV-15: LLM cannot accept improvement."""
        from core.kernel.policy import PolicyEngine
        p = PolicyEngine()
        self.assertFalse(p.can_llm_accept_improvement())

    def test_adv16_llm_cannot_bypass_validator(self):
        """ADV-16: LLM cannot bypass validator."""
        from core.kernel.policy import PolicyEngine
        p = PolicyEngine()
        self.assertFalse(p.can_llm_bypass_validator())

    def test_adv17_kernel_does_not_execute_subprocess_directly(self):
        """ADV-17: Kernel does not execute subprocess directly."""
        from core.kernel.orchestrator import KernelOrchestrator
        o = KernelOrchestrator()
        # No direct subprocess access in kernel
        self.assertFalse(hasattr(o, "subprocess"))
        self.assertFalse(hasattr(o, "run_shell"))
        self.assertFalse(hasattr(o, "execute_command"))
        # It delegates to RuntimeEngine
        import inspect
        src = inspect.getsource(KernelOrchestrator)
        # No subprocess.run or os.system calls in kernel
        self.assertNotIn("subprocess.run", src)
        self.assertNotIn("os.system", src)

    def test_adv18_taskrunner_cannot_skip_verification(self):
        """ADV-18: TaskRunner cannot skip verification."""
        from core.tasks.runner import TaskRunner
        # TaskRunner.run() must call verify after execute
        # This is structural — implemented in run() method
        import inspect
        src = inspect.getsource(TaskRunner)
        self.assertIn("_verify", src,
                     "TaskRunner.run() must call _verify after execute")
        self.assertIn("execute_step", src,
                     "TaskRunner.run() must call execute_step")

    def test_adv19_kernel_cannot_self_construct_tasks(self):
        """ADV-19: Kernel cannot self-construct tasks in EARLY mode."""
        from core.kernel.orchestrator import KernelOrchestrator
        o = KernelOrchestrator()
        # Kernel.run() takes a goal, not a task
        import inspect
        src = inspect.getsource(KernelOrchestrator)
        # No task construction method in orchestrator
        self.assertNotIn("construct_task", src)
        self.assertNotIn("create_task", src)


# ── Adversarial: Knowledge Promotion Violations ───────────────────────────────

class TestAdversarialKnowledgePromotion(unittest.TestCase):
    """Adversarial: Knowledge promotion boundary violations."""

    def test_adv20_generated_primitive_cannot_be_active(self):
        """ADV-20: GENERATED primitive cannot be ACTIVE."""
        import tempfile, shutil
        from core.knowledge.engine import KnowledgeEngine
        from core.knowledge.schema import SourceType
        from core.knowledge.lifecycle import LifecycleError
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(d, ignore_errors=True))
        ke = KnowledgeEngine(d)
        p = ke.create_primitive(
            domain="d", concept="x", description="y",
            source_type=SourceType.GENERATED.value
        )
        p, _ = ke.validate_primitive(p)
        p, _ = ke.verify_primitive(p, evidence_id="e1")
        p.confidence = 0.8
        p2 = ke.promotion.record_observation(p, "obs", "e2")
        ke.update_primitive(p2)
        latest = ke.list_primitives()[0]
        with self.assertRaises(LifecycleError):
            ke.activate_primitive(latest, evidence_ids=["e1", "e2"], reason="test")

    def test_adv21_skip_validated_illegal(self):
        """ADV-21: Cannot skip VALIDATED to reach VERIFIED."""
        import tempfile, shutil
        from core.knowledge.engine import KnowledgeEngine
        from core.knowledge.lifecycle import LifecycleError
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(d, ignore_errors=True))
        ke = KnowledgeEngine(d)
        p = ke.create_primitive(domain="d", concept="x", description="y")
        with self.assertRaises(LifecycleError):
            ke.verify_primitive(p, evidence_id="e1")

    def test_adv22_activate_requires_evidence(self):
        """ADV-22: ACTIVE requires evidence (no empty evidence_ids)."""
        import tempfile, shutil
        from core.knowledge.engine import KnowledgeEngine
        from core.knowledge.schema import SourceType
        from core.knowledge.lifecycle import LifecycleError
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(d, ignore_errors=True))
        ke = KnowledgeEngine(d)
        p = ke.create_primitive(
            domain="d", concept="x", description="y",
            source_type=SourceType.MANUAL.value
        )
        p, _ = ke.validate_primitive(p)
        p, _ = ke.verify_primitive(p, evidence_id="e1")
        p.confidence = 0.8
        ke.update_primitive(p)
        with self.assertRaises(LifecycleError):
            ke.activate_primitive(p, evidence_ids=[], reason="test")

    def test_adv23_low_confidence_cannot_be_active(self):
        """ADV-23: ACTIVE requires confidence >= 0.5."""
        import tempfile, shutil
        from core.knowledge.engine import KnowledgeEngine
        from core.knowledge.schema import SourceType
        from core.knowledge.lifecycle import LifecycleError
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(d, ignore_errors=True))
        ke = KnowledgeEngine(d)
        p = ke.create_primitive(
            domain="d", concept="x", description="y",
            source_type=SourceType.MANUAL.value
        )
        p, _ = ke.validate_primitive(p)
        p, _ = ke.verify_primitive(p, evidence_id="e1")
        p.confidence = 0.1  # Low
        p2 = ke.promotion.record_observation(p, "obs", "e2")
        ke.update_primitive(p2)
        latest = ke.list_primitives()[0]
        with self.assertRaises(LifecycleError):
            ke.activate_primitive(latest, evidence_ids=["e1", "e2"], reason="test")


# ── Adversarial: Improvement Without Baseline ────────────────────────────────

class TestAdversarialImprovement(unittest.TestCase):
    """Adversarial: Improvement without proper baseline."""

    def test_adv24_regression_always_rejected(self):
        """ADV-24: Regression in improvement must be rejected."""
        from core.evaluation.improvement import ImprovementEngine
        from core.evaluation.comparator import ComparisonResult
        from core.evaluation.schema import ImprovementStatus
        ie = ImprovementEngine()
        cand = ie.propose(
            target="x", hypothesis="h",
            baseline_eval_id="b",
            proposed_change="c", expected_benefit="e", risk="r"
        )
        ie.start_testing(cand.candidate_id)
        comp = ComparisonResult(
            baseline_score=0.9, candidate_score=0.1, delta=-0.8,
            improvement_detected=False, regression_detected=True,
            details=[], verdict="REGRESSED"
        )
        result, _ = ie.decide(cand.candidate_id, comp, evidence_ids=["ev1"])
        self.assertEqual(result.verdict, ImprovementStatus.REJECTED.value)

    def test_adv25_improvement_without_evidence_rejected(self):
        """ADV-25: Improvement without evidence_ids must be rejected."""
        from core.evaluation.improvement import ImprovementEngine
        from core.evaluation.comparator import ComparisonResult
        from core.evaluation.schema import ImprovementStatus
        ie = ImprovementEngine()
        cand = ie.propose(
            target="x", hypothesis="h",
            baseline_eval_id="b",
            proposed_change="c", expected_benefit="e", risk="r"
        )
        ie.start_testing(cand.candidate_id)
        comp = ComparisonResult(
            baseline_score=0.5, candidate_score=0.9, delta=0.4,
            improvement_detected=True, regression_detected=False,
            details=[], verdict="IMPROVED"
        )
        result, _ = ie.decide(cand.candidate_id, comp, evidence_ids=[])
        self.assertEqual(result.verdict, ImprovementStatus.REJECTED.value)

    def test_adv26_neutral_comparison_rejected(self):
        """ADV-26: Neutral comparison (no improvement) is rejected."""
        from core.evaluation.improvement import ImprovementEngine
        from core.evaluation.comparator import ComparisonResult
        from core.evaluation.schema import ImprovementStatus
        ie = ImprovementEngine()
        cand = ie.propose(
            target="x", hypothesis="h",
            baseline_eval_id="b",
            proposed_change="c", expected_benefit="e", risk="r"
        )
        ie.start_testing(cand.candidate_id)
        comp = ComparisonResult(
            baseline_score=0.5, candidate_score=0.5, delta=0.0,
            improvement_detected=False, regression_detected=False,
            details=[], verdict="NEUTRAL"
        )
        result, _ = ie.decide(cand.candidate_id, comp, evidence_ids=["ev1"])
        self.assertEqual(result.verdict, ImprovementStatus.REJECTED.value)


# ── Adversarial: Inconsistent State ────────────────────────────────────────────

class TestAdversarialStateConsistency(unittest.TestCase):
    """Adversarial: State consistency violations."""

    def test_adv27_duplicate_run_id_rejected(self):
        """ADV-27: Duplicate run_id must be rejected."""
        from core.experience.store import ExperienceStore, ExperienceStoreError
        from core.experience.schema import Experience
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(d, ignore_errors=True))
        s = ExperienceStore(d)
        s.create(Experience(run_id="R1", goal="x", project_id="p"))
        with self.assertRaises(ExperienceStoreError):
            s.create(Experience(run_id="R1", goal="y", project_id="p"))

    def test_adv28_duplicate_primitive_id_rejected(self):
        """ADV-28: Duplicate primitive id must be rejected."""
        import tempfile, shutil
        from core.knowledge.engine import KnowledgeEngine
        from core.knowledge.store import StoreError
        from core.knowledge.schema import Primitive
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(d, ignore_errors=True))
        ke = KnowledgeEngine(d)
        # create_primitive auto-generates id, so we create the first and try to overwrite
        ke.create_primitive(domain="d", concept="x", description="y")
        prims = ke.list_primitives()
        self.assertEqual(len(prims), 1)
        first_id = prims[0].id
        # Now try to create another with the same id via store
        p2 = Primitive(id=first_id, domain="d", concept="x", description="y")
        with self.assertRaises(StoreError):
            ke.store.create(p2)

    def test_adv29_missing_run_id_rejected(self):
        """ADV-29: Empty run_id must be rejected."""
        from core.experience.store import ExperienceStore, ExperienceStoreError
        from core.experience.schema import Experience
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(d, ignore_errors=True))
        s = ExperienceStore(d)
        with self.assertRaises(ExperienceStoreError):
            s.create(Experience(run_id="", goal="x", project_id="p"))

    def test_adv30_kernel_resume_missing_run_raises(self):
        """ADV-30: Resume of missing run must raise."""
        from core.kernel.kernel import Kernel, KernelError
        k = Kernel()
        with self.assertRaises(KernelError):
            k.run("test", resume_id="NONEXISTENT")


# ── Adversarial: Relation Graph Violations ─────────────────────────────────────

class TestAdversarialRelations(unittest.TestCase):
    """Adversarial: Knowledge relation graph violations."""

    def test_adv31_self_loop_rejected(self):
        """ADV-31: Self-loop relation must be rejected."""
        from core.knowledge.relations import RelationGraph, Relation, RelationError
        g = RelationGraph()
        g.add_primitive(_test_prim("A"))
        with self.assertRaises(RelationError):
            g.add_relation("A", Relation(target_id="A", relation_type="REQUIRES"))

    def test_adv32_invalid_relation_type_rejected(self):
        """ADV-32: Invalid relation type must be rejected."""
        from core.knowledge.relations import RelationGraph, Relation, RelationError
        g = RelationGraph()
        g.add_primitive(_test_prim("A"))
        g.add_primitive(_test_prim("B"))
        with self.assertRaises(RelationError):
            g.add_relation("A", Relation(target_id="B", relation_type="INVALID_TYPE"))

    def test_adv33_target_must_exist(self):
        """ADV-33: Relation target must exist."""
        from core.knowledge.relations import RelationGraph, Relation, RelationError
        g = RelationGraph()
        g.add_primitive(_test_prim("A"))
        with self.assertRaises(RelationError):
            g.add_relation("A", Relation(target_id="NOPE", relation_type="REQUIRES"))

    def test_adv34_duplicate_relation_rejected(self):
        """ADV-34: Duplicate relation must be rejected."""
        from core.knowledge.relations import RelationGraph, Relation, RelationError
        g = RelationGraph()
        g.add_primitive(_test_prim("A"))
        g.add_primitive(_test_prim("B"))
        g.add_relation("A", Relation(target_id="B", relation_type="REQUIRES"))
        with self.assertRaises(RelationError):
            g.add_relation("A", Relation(target_id="B", relation_type="REQUIRES"))


def _test_prim(pid: str):
    from core.knowledge.schema import Primitive
    return Primitive(id=pid, domain="d", concept="x", description="y")


# ── Adversarial: Verification Independence ────────────────────────────────────

class TestAdversarialVerificationIndependence(unittest.TestCase):
    """Adversarial: Verification must remain independent of executor."""

    def test_adv35_evaluator_can_return_fail_with_pass_evidence(self):
        """ADV-35: Evaluator can return FAIL even with some passing evidence."""
        from core.evaluation.engine import EvaluationEngine
        from core.evaluation.schema import Evidence
        e = EvaluationEngine()
        # All pass, but failed criteria present
        evidence = [
            Evidence(evidence_id=f"e{i}", type="TEST", source="x",
                     result="PASS", run_id="R1")
            for i in range(5)
        ]
        ev = e.evaluate("T1", evidence, "GOAL_ACHIEVED",
                        failed_criteria=["REQ_OUTPUT"])
        self.assertEqual(ev.verdict, "FAIL",
                        "Failed criteria override evidence PASS")
        self.assertIn("REQ_OUTPUT", ev.failed_criteria)

    def test_adv36_evaluator_does_not_trust_source_field(self):
        """ADV-36: Evaluator does not trust source field for verdict."""
        from core.evaluation.engine import EvaluationEngine
        from core.evaluation.schema import Evidence
        e = EvaluationEngine()
        # Source claims "TaskRunner" but result is FAIL
        ev = e.evaluate("T1", [
            Evidence(evidence_id="e1", type="TEST", source="TaskRunner",
                     result="FAIL", run_id="R1"),
            Evidence(evidence_id="e2", type="COMMAND_RESULT", source="TaskRunner",
                     result="FAIL", run_id="R1"),
        ], "GOAL_ACHIEVED")
        # Even with executor-reported results, the verdict must be FAIL
        self.assertEqual(ev.verdict, "FAIL")


# ── Adversarial: Schema Invariants ─────────────────────────────────────────────

class TestAdversarialSchemas(unittest.TestCase):
    """Adversarial: Schema validation must catch malformed data."""

    def test_adv37_primitive_missing_required_field_rejected(self):
        """ADV-37: Primitive missing concept must fail validation."""
        from core.knowledge.validator import KnowledgeValidator
        v = KnowledgeValidator()
        p = _test_prim("P1")
        p.concept = ""
        r = v.validate(p)
        self.assertFalse(r.valid)
        self.assertTrue(any(e.code == "SCHEMA_MISSING_CONCEPT" for e in r.errors))

    def test_adv38_primitive_bad_confidence_rejected(self):
        """ADV-38: Confidence out of range must fail validation."""
        from core.knowledge.validator import KnowledgeValidator
        v = KnowledgeValidator()
        p = _test_prim("P1")
        p.confidence = 1.5
        r = v.validate(p)
        self.assertFalse(r.valid)

    def test_adv39_primitive_negative_usage_count_rejected(self):
        """ADV-39: Negative usage_count must fail validation."""
        from core.knowledge.validator import KnowledgeValidator
        v = KnowledgeValidator()
        p = _test_prim("P1")
        p.usage_count = -1
        r = v.validate(p)
        self.assertFalse(r.valid)

    def test_adv40_primitive_count_inconsistency_rejected(self):
        """ADV-40: success+failure > usage must fail validation."""
        from core.knowledge.validator import KnowledgeValidator
        v = KnowledgeValidator()
        p = _test_prim("P1")
        p.usage_count = 5
        p.success_count = 4
        p.failure_count = 4  # 8 > 5
        r = v.validate(p)
        self.assertFalse(r.valid)


if __name__ == "__main__":
    unittest.main()
