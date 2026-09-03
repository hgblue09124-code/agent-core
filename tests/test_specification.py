#!/usr/bin/env python3
# tests/test_specification.py
"""Focused specification tests — verify the 15 mandatory sections are implemented.

Each test corresponds to one section in SPECIFICATION.md.
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


# ── Section 1: Kernel Identity ─────────────────────────────────────────────────

class TestSection01KernelIdentity(unittest.TestCase):
    """Section 1: Kernel Identity."""

    def test_kernel_module_exists(self):
        from core.kernel.kernel import Kernel
        k = Kernel()
        self.assertIsNotNone(k)

    def test_kernel_loop_phases_defined(self):
        from core.kernel.schema import KernelPhase
        expected = {"BOOTSTRAP", "KNOWLEDGE_RETRIEVAL", "REASONING",
                    "PLAN_VALIDATION", "EXECUTION", "OBSERVATION",
                    "VERIFICATION", "EXPERIENCE", "EVALUATION", "LESSON",
                    "KNOWLEDGE_PROMOTION", "IMPROVEMENT", "COMPLETE", "FAILED"}
        actual = {p.value for p in KernelPhase}
        self.assertEqual(actual, expected)

    def test_kernel_status_enum_distinct(self):
        from core.kernel.schema import KernelStatus
        values = {s.value for s in KernelStatus}
        self.assertGreaterEqual(len(values), 4)


# ── Section 2: Task Construction ───────────────────────────────────────────────

class TestSection02TaskConstruction(unittest.TestCase):
    """Section 2: Task Construction."""

    def test_task_construction_contract_required_fields(self):
        from core.tasks.schema import TaskConstructionContract
        c = TaskConstructionContract(
            contract_id="TCC-001",
            objective="test",
            expected_evidence_types=["TEST"],
            acceptance_criteria=["x"],
        )
        valid, reason = c.validate()
        self.assertTrue(valid, f"Minimal contract must validate: {reason}")

    def test_prompt_neq_contract(self):
        """Prompt (string) and Contract (structured) are distinct."""
        from core.tasks.schema import TaskConstructionContract
        # Prompt is just a string
        prompt = "Build a system that does X"
        # Contract is a structured object
        contract = TaskConstructionContract(
            contract_id="TCC-001",
            objective=prompt,
            expected_evidence_types=["TEST"],
            acceptance_criteria=["x"],
        )
        self.assertNotEqual(type(prompt), type(contract))

    def test_deep_task_prompt_primitive(self):
        from core.tasks.schema import DeepTaskPrompt
        p = DeepTaskPrompt(
            prompt_id="DTP-00001",
            task_id="TASK-00001",
            intent="build x",
            goal="test passes",
            expected_evidence_types=["TEST"],
            acceptance_criteria=["x"],
        )
        self.assertTrue(p.validate()[0])


# ── Section 3: Execution ───────────────────────────────────────────────────────

class TestSection03Execution(unittest.TestCase):
    """Section 3: Execution."""

    def test_step_types_defined(self):
        from core.tasks.schema import StepType
        self.assertEqual(StepType.SHELL.value, "shell")
        self.assertEqual(StepType.PYTHON.value, "python")
        self.assertEqual(StepType.INSPECT.value, "inspect")

    def test_step_result_fields(self):
        from core.tasks.schema import StepResult
        r = StepResult(
            stdout="out", stderr="err", exit_code=0,
            duration_seconds=1.0,
            started_at="2025-01-01T00:00:00Z",
            finished_at="2025-01-01T00:00:01Z",
        )
        self.assertEqual(r.exit_code, 0)
        self.assertEqual(r.duration_seconds, 1.0)

    def test_task_runner_can_run_step(self):
        """TaskRunner has run() method that returns a Task."""
        from core.tasks.runner import TaskRunner
        from core.tasks.schema import StepType
        # TaskRunner must have a run() method
        self.assertTrue(hasattr(TaskRunner, "run"))
        self.assertTrue(callable(getattr(TaskRunner, "run")))
        # TaskRunner must have _execute_step
        self.assertTrue(hasattr(TaskRunner, "_execute_step"))
        # StepType enum is defined
        self.assertIn("shell", {e.value for e in StepType})


# ── Section 4: Verification ────────────────────────────────────────────────────

class TestSection04Verification(unittest.TestCase):
    """Section 4: Verification."""

    def test_verification_layers_defined(self):
        from core.evaluation.schema import ScoreLayer
        layers = {l.value for l in ScoreLayer}
        self.assertIn("correctness", layers)
        self.assertIn("requirement_coverage", layers)
        self.assertIn("integration", layers)
        self.assertIn("regression_safety", layers)
        self.assertIn("efficiency", layers)

    def test_verification_gate_criteria(self):
        from core.evaluation.criteria import get_required_codes
        required = get_required_codes()
        self.assertGreater(len(required), 5)

    def test_llm_cannot_declare_verification(self):
        from core.kernel.policy import PolicyEngine
        p = PolicyEngine()
        self.assertFalse(p.can_llm_declare_verification())


# ── Section 5: Evidence ───────────────────────────────────────────────────────

class TestSection05Evidence(unittest.TestCase):
    """Section 5: Evidence."""

    def test_evidence_types_defined(self):
        from core.evaluation.schema import EvidenceType
        types = {t.value for t in EvidenceType}
        self.assertIn("TEST", types)
        self.assertIn("ASSERTION", types)
        self.assertIn("COMMAND_RESULT", types)
        self.assertIn("FILE_STATE", types)
        self.assertIn("CHECKPOINT", types)
        self.assertIn("BENCHMARK", types)
        self.assertIn("REGRESSION", types)
        self.assertIn("MANUAL", types)

    def test_evidence_ledger_secret_detection(self):
        from core.evaluation.evidence import EvidenceLedger
        from core.evaluation.schema import Evidence
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(d, ignore_errors=True))
        l = EvidenceLedger(str(Path(d) / "ev.json"))
        with self.assertRaises(ValueError):
            l.record(Evidence(
                evidence_id="e1", type="MANUAL",
                source="leak", result="sk-abcdefghijklmnopqrstuvwxyz12345"
            ))

    def test_evidence_ledger_idempotent(self):
        from core.evaluation.evidence import EvidenceLedger
        from core.evaluation.schema import Evidence
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(d, ignore_errors=True))
        l = EvidenceLedger(str(Path(d) / "ev.json"))
        e = Evidence(evidence_id="e1", type="TEST", source="x", result="PASS")
        l.record(e)
        l.record(e)  # same id
        self.assertEqual(l.count(), 1)


# ── Section 6: Evaluation ─────────────────────────────────────────────────────

class TestSection06Evaluation(unittest.TestCase):
    """Section 6: Evaluation."""

    def test_achievement_state_four_distinct_values(self):
        from core.evaluation.schema import AchievementState
        values = {s.value for s in AchievementState}
        self.assertEqual(len(values), 4)
        self.assertIn("TASK_COMPLETED", values)
        self.assertIn("GOAL_ACHIEVED", values)
        self.assertIn("SOLUTION_VALID", values)
        self.assertIn("SOLUTION_OPTIMAL", values)

    def test_evaluation_verdict_states(self):
        from core.evaluation.schema import Verdict
        values = {v.value for v in Verdict}
        self.assertIn("PASS", values)
        self.assertIn("FAIL", values)
        self.assertIn("INCONCLUSIVE", values)

    def test_comparator_thresholds(self):
        from core.evaluation.comparator import Comparator
        c = Comparator()
        self.assertEqual(c.REGRESSION_THRESHOLD, -0.05)
        self.assertEqual(c.IMPROVEMENT_THRESHOLD, 0.05)


# ── Section 7: Experience ─────────────────────────────────────────────────────

class TestSection07Experience(unittest.TestCase):
    """Section 7: Experience."""

    def test_experience_required_fields(self):
        from core.experience.schema import Experience
        e = Experience(run_id="R1", goal="x", project_id="p")
        self.assertEqual(e.run_id, "R1")
        self.assertEqual(e.goal, "x")
        self.assertEqual(e.project_id, "p")

    def test_experience_append_only_via_id(self):
        from core.experience.store import ExperienceStore, ExperienceStoreError
        from core.experience.schema import Experience
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(d, ignore_errors=True))
        s = ExperienceStore(d)
        s.create(Experience(run_id="R1", goal="x", project_id="p"))
        with self.assertRaises(ExperienceStoreError):
            s.create(Experience(run_id="R1", goal="y", project_id="p"))

    def test_failure_category_detection(self):
        from core.experience.recorder import FailureCategory
        cat = FailureCategory.detect("Connection refused")
        self.assertEqual(cat, FailureCategory.NETWORK)
        cat = FailureCategory.detect("SyntaxError: invalid syntax")
        self.assertEqual(cat, FailureCategory.SYNTAX)


# ── Section 8: Knowledge ──────────────────────────────────────────────────────

class TestSection08Knowledge(unittest.TestCase):
    """Section 8: Knowledge."""

    def test_knowledge_lifecycle_states(self):
        from core.knowledge.schema import KnowledgeStatus
        values = {s.value for s in KnowledgeStatus}
        self.assertEqual(values, {
            "CANDIDATE", "VALIDATED", "VERIFIED", "ACTIVE",
            "DEPRECATED", "REJECTED"
        })

    def test_lifecycle_transitions_legal(self):
        from core.knowledge.lifecycle import Lifecycle
        lc = Lifecycle()
        self.assertTrue(lc.can_transition("CANDIDATE", "VALIDATED"))
        self.assertTrue(lc.can_transition("VALIDATED", "VERIFIED"))
        self.assertTrue(lc.can_transition("VERIFIED", "ACTIVE"))
        # Illegal: skipping
        self.assertFalse(lc.can_transition("CANDIDATE", "ACTIVE"))

    def test_generated_cannot_promote_to_active(self):
        from core.knowledge.promotion import PromotionEngine
        from core.knowledge.schema import Primitive, SourceType, KnowledgeStatus
        pe = PromotionEngine()
        p = Primitive(
            id="P1", domain="d", concept="x", description="y",
            confidence=0.8,
        )
        p.provenance.source_type = SourceType.GENERATED.value
        p.status = KnowledgeStatus.VERIFIED.value
        # Add 2 evidence
        p.provenance.evidence_ids = ["e1", "e2"]
        can, _ = pe.can_promote(p, KnowledgeStatus.ACTIVE.value)
        self.assertFalse(can, "GENERATED cannot reach ACTIVE")


# ── Section 9: Learning ───────────────────────────────────────────────────────

class TestSection09Learning(unittest.TestCase):
    """Section 9: Learning."""

    def test_experience_to_lesson_pipeline(self):
        from core.experience.engine import ExperienceEngine
        from core.experience.schema import Experience
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(d, ignore_errors=True))
        e = ExperienceEngine(d)
        exp = Experience(run_id="R1", goal="x", project_id="p",
                         outcome="success")
        e.record_experience(exp)
        lessons = e.extract_lessons([exp])
        self.assertGreater(len(lessons), 0)

    def test_learner_requires_minimum_evidence(self):
        from core.experience.learner import ExperienceLearner
        from core.experience.schema import Experience
        l = ExperienceLearner()
        # 1 experience → no failure candidate (MIN_EVIDENCE_FOR_CANDIDATE = 2)
        exps = [Experience(run_id="R1", goal="x", project_id="p",
                         outcome="failure", failure="boom")]
        cands = l.learn(exps)
        failure_cands = [c for c in cands if c.primitive.concept.startswith("failure_")]
        self.assertEqual(len(failure_cands), 0)

    def test_saving_logs_not_learning(self):
        """Saving logs is not learning. Learning requires evidence of improvement."""
        from core.experience.schema import Experience
        e = Experience(run_id="R1", goal="x", project_id="p", outcome="success")
        d = e.to_dict()
        # Just saving an experience doesn't make it "learning"
        # Learning requires: pattern_candidate -> reinforced -> reused -> improvement
        self.assertFalse(e.lesson or "improved" in d.get("outcome", ""))


# ── Section 10: Capability ────────────────────────────────────────────────────

class TestSection10Capability(unittest.TestCase):
    """Section 10: Capability."""

    def test_capability_definitions_exist(self):
        """The 8 mandatory capabilities are defined in capability schema."""
        schema_path = _root / "constitution" / "schemas" / "capabilities.json"
        with open(schema_path) as f:
            schema = json.load(f)
        caps_prop = schema["properties"]["capabilities"]
        self.assertGreaterEqual(caps_prop.get("minItems", 0), 8)

    def test_capability_test_structure(self):
        """Each capability test has stages defined (6-stage promotion)."""
        # The schema requires stages to be defined for capabilities
        schema_path = _root / "constitution" / "schemas" / "capabilities.json"
        with open(schema_path) as f:
            schema = json.load(f)
        # Schema (top-level) requires both 'capabilities' and 'promotion_model'
        self.assertIn("promotion_model", schema.get("required", []))
        # Schema has properties for promotion_model
        self.assertIn("promotion_model", schema["properties"])
        promo = schema["properties"]["promotion_model"]
        # promotion_model requires 'stages' field (JSON schema style)
        self.assertIn("stages", promo.get("required", []))
        # Schema for individual capability items requires 6 stages
        cap_item_schema = schema["properties"]["capabilities"]["items"]
        stages_in_item = cap_item_schema["properties"]["stages"]
        self.assertEqual(stages_in_item["minItems"], 6)


# ── Section 11: Authority ─────────────────────────────────────────────────────

class TestSection11Authority(unittest.TestCase):
    """Section 11: Authority."""

    def test_authority_matrix_in_spec(self):
        spec = (_root / "SPECIFICATION.md").read_text()
        self.assertIn("Authority Matrix", spec)
        # All actors must be present
        for actor in ["Administrator", "Kernel", "TaskRunner", "EvaluationEngine"]:
            self.assertIn(actor, spec)

    def test_llm_boundary_in_policy(self):
        from core.kernel.policy import PolicyEngine
        p = PolicyEngine()
        # All LLM boundary checks must be False by default
        self.assertFalse(p.can_llm_declare_verification())
        self.assertFalse(p.can_llm_promote_knowledge())
        self.assertFalse(p.can_llm_accept_improvement())
        self.assertFalse(p.can_llm_bypass_validator())

    def test_early_mid_final_states_defined(self):
        spec = (_root / "SPECIFICATION.md").read_text()
        for stage in ["EARLY", "MID", "FINAL"]:
            self.assertIn(stage, spec)


# ── Section 12: Promotion Gate ────────────────────────────────────────────────

class TestSection12PromotionGate(unittest.TestCase):
    """Section 12: Promotion Gate."""

    def test_promotion_gates_schema_exists(self):
        schema_path = _root / "constitution" / "schemas" / "promotion_gates.json"
        self.assertTrue(schema_path.exists())

    def test_knowledge_promotion_gates(self):
        from core.knowledge.lifecycle import Lifecycle
        lc = Lifecycle()
        # All gates must be defined
        for src, dst in [
            ("CANDIDATE", "VALIDATED"),
            ("VALIDATED", "VERIFIED"),
            ("VERIFIED", "ACTIVE"),
            ("ACTIVE", "DEPRECATED"),
        ]:
            self.assertTrue(lc.can_transition(src, dst))

    def test_improvement_comparator_thresholds(self):
        from core.evaluation.comparator import Comparator
        c = Comparator()
        self.assertEqual(c.REGRESSION_THRESHOLD, -0.05)
        self.assertEqual(c.IMPROVEMENT_THRESHOLD, 0.05)
        self.assertEqual(c.NEUTRAL_BAND, 0.05)


# ── Section 13: Adversarial Verification ───────────────────────────────────────

class TestSection13Adversarial(unittest.TestCase):
    """Section 13: Adversarial Verification."""

    def test_adversarial_cases_in_spec(self):
        spec = (_root / "SPECIFICATION.md").read_text()
        # All 16 cases should be in spec
        for case in [
            "malformed Task Contract",
            "missing evidence",
            "fabricated success",
            "false verification",
            "incomplete execution",
            "wrong architectural placement",
            "forbidden authority escalation",
            "unauthorized architecture change",
            "regression",
            "repeated failure",
            "inconsistent persisted state",
            "misleading executor report",
            "improvement claim without baseline",
            "knowledge promotion without verification",
            "capability promotion without repeated evidence",
        ]:
            self.assertIn(case.lower(), spec.lower(),
                         f"Adversarial case missing: {case}")

    def test_adversarial_test_module_exists(self):
        adv_test = _root / "tests" / "test_adversarial_spec.py"
        self.assertTrue(adv_test.exists(),
                        "Adversarial test module must exist")

    def test_adversarial_test_has_40_cases(self):
        adv_test = _root / "tests" / "test_adversarial_spec.py"
        text = adv_test.read_text()
        # Count test_advXX methods
        import re
        adv_tests = re.findall(r"def (test_adv\d+_)", text)
        self.assertGreaterEqual(len(adv_tests), 40)


# ── Section 14: Reproducibility ───────────────────────────────────────────────

class TestSection14Reproducibility(unittest.TestCase):
    """Section 14: Reproducibility."""

    def test_kernel_context_has_required_fields(self):
        from core.kernel.schema import KernelContext
        ctx = KernelContext(run_id="R1", goal="x", project_id="p")
        d = ctx.to_dict()
        for field in ["run_id", "goal", "project_id", "kernel_phase",
                       "kernel_status", "llm_calls", "errors",
                       "started_at", "created_at"]:
            self.assertIn(field, d)

    def test_run_state_has_required_fields(self):
        from core.runtime.schema import RunState
        s = RunState(run_id="R1", goal="x", project_id="p")
        d = s.to_dict()
        for field in ["run_id", "goal", "project_id", "phase", "status",
                       "started_at", "metrics"]:
            self.assertIn(field, d)

    def test_checkpoint_atomic_write(self):
        from core.kernel.lifecycle import KernelLifecycle, _gen_run_id
        from core.kernel.schema import KernelContext
        import tempfile, shutil
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(d, ignore_errors=True))
        lc = KernelLifecycle(d)
        ctx = KernelContext(run_id=_gen_run_id(), goal="x", project_id="p")
        lc.save(ctx)
        # No .tmp file remaining
        self.assertFalse((Path(d) / f"{ctx.run_id}.json.tmp").exists())
        # Main file exists
        self.assertTrue((Path(d) / f"{ctx.run_id}.json").exists())


# ── Section 15: Improvement ───────────────────────────────────────────────────

class TestSection15Improvement(unittest.TestCase):
    """Section 15: Improvement."""

    def test_improvement_candidate_schema(self):
        from core.evaluation.schema import ImprovementCandidate
        c = ImprovementCandidate(
            candidate_id="IMP-1",
            target="x",
            hypothesis="h",
            baseline_evaluation_id="B1",  # Required
            proposed_change="c",
            expected_benefit="+10%",
            risk="low",
        )
        d = c.to_dict()
        self.assertEqual(d["baseline_evaluation_id"], "B1")

    def test_no_baseline_no_improvement(self):
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
        # Neutral (no improvement) is rejected
        self.assertEqual(result.verdict, ImprovementStatus.REJECTED.value)


if __name__ == "__main__":
    unittest.main()
