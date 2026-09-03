#!/usr/bin/env python3
# tests/test_philosophy.py
"""Comprehensive & Adversarial Tests for core/philosophy module.

Verifies:
1. New lesson -> Philosophy Candidate
2. Candidate does NOT affect behavior (is_active_preference is False)
3. Human teaches a tendency -> provenance preserved, status remains CANDIDATE by default
4. One teaching event does not automatically become established truth (SUPPORTED)
5. Repeated supporting evidence -> confidence increases deterministically and promotes CANDIDATE -> SUPPORTED
5b. Deterministic threshold promotion math
6. Contradicting evidence -> confidence decreases deterministically
7. Strong contradiction -> tendency weakened/rejected according to lifecycle
7b. Cannot resurrect REJECTED or RETIRED tendencies
8. Rejected tendency cannot be consulted
9. Retired tendency cannot be consulted
10. Weakened tendency does not behave as Supported (excluded by default)
11. Philosophy cannot bypass Kernel invariants or Security boundaries
12. Philosophy cannot bypass Verification requirements
13. Philosophy cannot violate Task Contract
14. Actual precedence conflict resolution: explicit task requirement beats philosophy preference
15. Evolution history is complete, ordered, and retains exact provenance
16. Serialization/deserialization retains all history and provenance
17. Reloading from PhilosophyStore preserves exact semantics
18. Context-aware preference consultation matching on tags/keywords is deterministic
19. Invalid evidence ID structure is rejected by validation interface
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from core.experience.lesson import Lesson, LessonType
from core.philosophy.schema import (
    PhilosophyStatus,
    TeachingType,
    EvolutionRecord,
    PhilosophyTendency,
)
from core.philosophy.store import PhilosophyStore, PhilosophyStoreError
from core.philosophy.engine import PhilosophyEngine, PhilosophyPrecedenceError


class TestPhilosophyHardeningAdversarial(unittest.TestCase):
    """Adversarial and hardening unit test scenarios for Agent Philosophy."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="phil_adv_test_")
        self.store = PhilosophyStore(store_dir=self.tmpdir)
        self.engine = PhilosophyEngine(store=self.store)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_01_new_lesson_creates_philosophy_candidate(self):
        lesson = Lesson(
            lesson_id="L-KRUN-001-verify",
            title="Inspect project structure before editing",
            description="Inspecting project files reduces unexpected path errors.",
            lesson_type=LessonType.FIRST_OBSERVATION,
            source_experience_id="KRUN-001",
            confidence=0.3,
        )
        cand = self.engine.propose_candidate_from_lesson(lesson)

        self.assertEqual(cand.status, PhilosophyStatus.CANDIDATE.value)
        self.assertIn("L-KRUN-001-verify", cand.source_lesson_ids)
        self.assertIn("L-KRUN-001-verify", cand.supporting_evidence_ids)

    def test_02_candidate_does_not_affect_behavior(self):
        lesson = Lesson(
            lesson_id="L-KRUN-002",
            title="A candidate tendency",
            description="Forming seed",
            lesson_type=LessonType.FIRST_OBSERVATION,
            source_experience_id="KRUN-002",
        )
        cand = self.engine.propose_candidate_from_lesson(lesson)

        # 1. is_active_preference is False for CANDIDATE
        self.assertFalse(cand.is_active_preference())

        # 2. consult_soft_preferences excludes CANDIDATE
        active_prefs = self.engine.consult_soft_preferences()
        self.assertNotIn(cand.tendency_id, [p.tendency_id for p in active_prefs])

    def test_03_human_teaches_tendency_preserves_provenance(self):
        t = self.engine.teach(
            statement="I tend to check git status before submitting",
            origin="operator_alice_teaching_session_01",
        )

        self.assertEqual(t.origin, "operator_alice_teaching_session_01")
        self.assertEqual(t.status, PhilosophyStatus.CANDIDATE.value)
        self.assertEqual(t.evolution_history[0].actor, "human")
        self.assertEqual(t.evolution_history[0].action_type, TeachingType.TEACH.value)

    def test_04_one_teaching_event_not_automatic_truth(self):
        t = self.engine.teach(
            statement="I tend to write docstrings first",
            initial_confidence=0.2,
        )

        # By default, a single teach event remains CANDIDATE and is NOT active preference truth
        self.assertEqual(t.status, PhilosophyStatus.CANDIDATE.value)
        self.assertFalse(t.is_active_preference())
        self.assertNotIn(t.tendency_id, [p.tendency_id for p in self.engine.consult_soft_preferences()])

    def test_05_repeated_supporting_evidence_increases_confidence_and_promotes(self):
        # Starts as candidate with confidence 0.2
        t = self.engine.teach("I tend to verify imports before running", initial_confidence=0.2)
        self.assertEqual(t.status, PhilosophyStatus.CANDIDATE.value)

        # First supporting evidence (+0.15) -> confidence 0.35 (still CANDIDATE)
        t = self.engine.support(t.tendency_id, feedback="First evidence", evidence_id="EV-001")
        self.assertEqual(t.status, PhilosophyStatus.CANDIDATE.value)
        self.assertAlmostEqual(t.confidence, 0.35)
        self.assertFalse(t.is_active_preference())

        # REPEATED supporting evidence (+0.15) -> confidence 0.50 -> Promoted to SUPPORTED
        t = self.engine.support(t.tendency_id, feedback="Repeated evidence", evidence_id="EV-002")
        self.assertEqual(t.status, PhilosophyStatus.SUPPORTED.value)
        self.assertAlmostEqual(t.confidence, 0.50)
        self.assertTrue(t.is_active_preference())

    def test_05b_deterministic_threshold_promotion(self):
        t = self.engine.teach("Threshold promotion test", initial_confidence=0.35)
        self.assertEqual(t.status, PhilosophyStatus.CANDIDATE.value)

        t = self.engine.support(t.tendency_id, feedback="Support event", evidence_id="EV-THRESH-1")
        self.assertAlmostEqual(t.confidence, 0.50)
        self.assertEqual(t.status, PhilosophyStatus.SUPPORTED.value)

    def test_06_contradicting_evidence_decreases_confidence(self):
        t = self.engine.teach("I tend to assume default options", initial_confidence=0.6, establish_immediately=True)
        self.assertEqual(t.status, PhilosophyStatus.SUPPORTED.value)

        t = self.engine.challenge(t.tendency_id, feedback="Failed on custom option", evidence_id="EV-FAIL-01")
        self.assertAlmostEqual(t.confidence, 0.35)
        self.assertIn("EV-FAIL-01", t.contradicting_evidence_ids)

    def test_07_strong_contradiction_weakens_or_rejects(self):
        t = self.engine.teach("I tend to ignore warnings", initial_confidence=0.5, establish_immediately=True)

        # Challenge 1 -> confidence 0.25 < 0.35 -> status WEAKENED
        t = self.engine.challenge(t.tendency_id, feedback="Warning caused crash", evidence_id="EV-01")
        self.assertEqual(t.status, PhilosophyStatus.WEAKENED.value)

        # Reject explicitly upon strong contradiction
        t = self.engine.reject(t.tendency_id, reason="Security audit rejected ignoring warnings")
        self.assertEqual(t.status, PhilosophyStatus.REJECTED.value)
        self.assertEqual(t.confidence, 0.0)

    def test_07b_cannot_resurrect_rejected_or_retired(self):
        t1 = self.engine.teach("Rejection test", establish_immediately=True)
        self.engine.reject(t1.tendency_id, reason="Rejected")

        with self.assertRaises(ValueError) as cm1:
            self.engine.support(t1.tendency_id, evidence_id="EV-NEW-1")
        self.assertIn("Cannot support a REJECTED", str(cm1.exception))

        t2 = self.engine.teach("Retirement test", establish_immediately=True)
        self.engine.retire(t2.tendency_id, reason="Retired")

        with self.assertRaises(ValueError) as cm2:
            self.engine.challenge(t2.tendency_id, evidence_id="EV-NEW-2")
        self.assertIn("Cannot challenge a RETIRED", str(cm2.exception))

    def test_08_rejected_tendency_not_consulted(self):
        t = self.engine.teach("I tend to use deprecated APIs", establish_immediately=True)
        self.engine.reject(t.tendency_id, reason="Deprecated")

        prefs = self.engine.consult_soft_preferences()
        self.assertNotIn(t.tendency_id, [p.tendency_id for p in prefs])

    def test_09_retired_tendency_not_consulted(self):
        t = self.engine.teach("I tend to use Python 2 print statements", establish_immediately=True)
        self.engine.retire(t.tendency_id, reason="Python 2 EOL")

        prefs = self.engine.consult_soft_preferences()
        self.assertNotIn(t.tendency_id, [p.tendency_id for p in prefs])

    def test_10_weakened_tendency_does_not_behave_as_supported(self):
        t = self.engine.teach("I tend to run tests without isolation", initial_confidence=0.5, establish_immediately=True)
        t = self.engine.challenge(t.tendency_id, feedback="Interference detected", evidence_id="EV-INT-1")

        self.assertEqual(t.status, PhilosophyStatus.WEAKENED.value)
        # Default consultation excludes WEAKENED
        default_prefs = self.engine.consult_soft_preferences(include_weakened=False)
        self.assertNotIn(t.tendency_id, [p.tendency_id for p in default_prefs])

    def test_11_philosophy_cannot_bypass_kernel_invariants(self):
        with self.assertRaises(PhilosophyPrecedenceError) as cm:
            self.engine.enforce_precedence_policy(
                requested_action="read_secrets_unredacted",
                violates_kernel_invariant=True,
            )
        self.assertIn("Kernel invariant or security boundary", str(cm.exception))

    def test_12_philosophy_cannot_bypass_verification(self):
        with self.assertRaises(PhilosophyPrecedenceError) as cm:
            self.engine.enforce_precedence_policy(
                requested_action="declare_task_verified_without_tests",
                bypasses_verification=True,
            )
        self.assertIn("verification requirements", str(cm.exception))

    def test_13_philosophy_cannot_violate_task_contract(self):
        with self.assertRaises(PhilosophyPrecedenceError) as cm:
            self.engine.enforce_precedence_policy(
                requested_action="ignore_contract_scope",
                violates_task_contract=True,
            )
        self.assertIn("explicit task contract", str(cm.exception))

    def test_14_actual_precedence_conflict_resolution(self):
        # Soft philosophy preference
        philosophy_preference = "I tend to prefer concise answers"
        t = self.engine.teach(philosophy_preference, initial_confidence=0.8, establish_immediately=True)
        self.assertTrue(t.is_active_preference())

        # Explicit task contract requirement
        task_requirement = "Produce detailed 10-page audit report"

        # Resolve conflict deterministically: Task requirement strictly wins!
        chosen, reason = self.engine.resolve_action_conflict(philosophy_preference, task_requirement)
        self.assertEqual(chosen, task_requirement)
        self.assertIn("strictly overrides", reason)

        # Precedence policy enforcement raises exception if philosophy attempts to violate task contract
        with self.assertRaises(PhilosophyPrecedenceError):
            self.engine.enforce_precedence_policy(philosophy_preference, violates_task_contract=True)

    def test_15_evolution_history_complete_and_ordered(self):
        t = self.engine.teach("I tend to verify assumptions first", initial_confidence=0.3)
        t = self.engine.support(t.tendency_id, feedback="Support 1", evidence_id="EV-01")
        t = self.engine.challenge(t.tendency_id, feedback="Challenge 1", evidence_id="EV-02")
        t = self.engine.modify(t.tendency_id, new_statement="I perform better when I verify assumptions first")

        history = t.evolution_history
        self.assertEqual(len(history), 4)
        self.assertEqual(history[0].action_type, TeachingType.TEACH.value)
        self.assertEqual(history[1].action_type, TeachingType.SUPPORT.value)
        self.assertEqual(history[2].action_type, TeachingType.CHALLENGE.value)
        self.assertEqual(history[3].action_type, TeachingType.MODIFY.value)

    def test_16_serialization_deserialization_retains_history_and_provenance(self):
        t = self.engine.teach("I tend to run pytest -v", initial_confidence=0.4)
        t = self.engine.support(t.tendency_id, feedback="Verified in CI", evidence_id="EV-CI-100")

        d = t.to_dict()
        restored = PhilosophyTendency.from_dict(d)

        self.assertEqual(restored.tendency_id, t.tendency_id)
        self.assertEqual(restored.supporting_evidence_ids, ["EV-CI-100"])
        self.assertEqual(len(restored.evolution_history), 2)
        self.assertEqual(restored.evolution_history[1].reason, "Verified in CI")

    def test_17_reload_from_store_preserves_exact_semantics(self):
        t = self.engine.teach("Persistent tendency", initial_confidence=0.6, establish_immediately=True)
        t_id = t.tendency_id

        # Create fresh engine pointing to same store directory
        new_engine = PhilosophyEngine(store=PhilosophyStore(store_dir=self.tmpdir))
        reloaded = new_engine.get_tendency(t_id)

        self.assertIsNotNone(reloaded)
        self.assertEqual(reloaded.statement, "Persistent tendency")
        self.assertEqual(reloaded.status, PhilosophyStatus.SUPPORTED.value)
        self.assertTrue(reloaded.is_active_preference())

    def test_18_context_aware_consultation_matching_is_deterministic(self):
        t1 = self.engine.teach("I tend to verify cuu-gioi architecture documents first", tags=["cuu-gioi", "architecture"], establish_immediately=True)
        t2 = self.engine.teach("I tend to run database migrations with backup", tags=["database", "migration"], establish_immediately=True)

        task_context = {"project_id": "cuu-gioi", "tags": ["architecture"]}
        matched = self.engine.consult_soft_preferences(task_context=task_context)

        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0].tendency_id, t1.tendency_id)

    def test_19_invalid_evidence_id_rejected(self):
        t = self.engine.teach("Test invalid evidence ID", establish_immediately=True)
        with self.assertRaises(ValueError):
            self.engine.support(t.tendency_id, evidence_id="")
        with self.assertRaises(ValueError):
            self.engine.challenge(t.tendency_id, evidence_id="   ")


if __name__ == "__main__":
    unittest.main()
