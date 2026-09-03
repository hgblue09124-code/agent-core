#!/usr/bin/env python3
# tests/test_philosophy.py
"""Tests for core/philosophy module.

Verifies:
1. Philosophy Model Creation & Serialization
2. Experience -> Lesson -> Philosophy Provenance
3. Candidate Lifecycle (candidate -> supported -> weakened -> retired / rejected)
4. Supporting & Contradicting Evidence
5. Evolution History Logging
6. Human Teaching Inputs (teach, challenge, support, contradict, modify, reject, retire)
7. Operational Self-Knowledge Statements
8. Precedence Policy Enforcement (Philosophy CANNOT override Kernel, Security, Verification, or Task Contracts)
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


class TestPhilosophySchema(unittest.TestCase):
    """Test philosophy schema serialization and status checks."""

    def test_philosophy_tendency_serialization_roundtrip(self):
        t = PhilosophyTendency(
            tendency_id="PHIL-0001",
            statement="I tend to verify assumptions before modifying code",
            origin="human_teaching",
            supporting_evidence_ids=["EV-001", "EV-002"],
            contradicting_evidence_ids=["EV-003"],
            confidence=0.75,
            status=PhilosophyStatus.SUPPORTED.value,
            tags=["self_knowledge", "verification"],
        )
        d = t.to_dict()
        restored = PhilosophyTendency.from_dict(d)

        self.assertEqual(restored.tendency_id, "PHIL-0001")
        self.assertEqual(
            restored.statement,
            "I tend to verify assumptions before modifying code",
        )
        self.assertEqual(restored.supporting_evidence_ids, ["EV-001", "EV-002"])
        self.assertEqual(restored.contradicting_evidence_ids, ["EV-003"])
        self.assertAlmostEqual(restored.confidence, 0.75)
        self.assertEqual(restored.status, PhilosophyStatus.SUPPORTED.value)
        self.assertTrue(restored.is_active_preference())

    def test_inactive_statuses_are_not_active_preferences(self):
        t1 = PhilosophyTendency(
            tendency_id="P1",
            statement="X",
            origin="o",
            status=PhilosophyStatus.REJECTED.value,
        )
        t2 = PhilosophyTendency(
            tendency_id="P2",
            statement="Y",
            origin="o",
            status=PhilosophyStatus.RETIRED.value,
        )
        t3 = PhilosophyTendency(
            tendency_id="P3",
            statement="Z",
            origin="o",
            status=PhilosophyStatus.SUPPORTED.value,
            confidence=0.05,  # too low
        )

        self.assertFalse(t1.is_active_preference())
        self.assertFalse(t2.is_active_preference())
        self.assertFalse(t3.is_active_preference())


class TestPhilosophyStore(unittest.TestCase):
    """Test atomic storage operations."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="phil_store_test_")
        self.store = PhilosophyStore(store_dir=self.tmpdir)

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_save_and_retrieve_tendency(self):
        t = PhilosophyTendency(
            tendency_id="PHIL-0001",
            statement="I perform better when I inspect project structure first",
            origin="experience",
            confidence=0.6,
        )
        self.store.save(t)
        retrieved = self.store.get("PHIL-0001")

        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.statement, t.statement)
        self.assertEqual(self.store.count(), 1)

    def test_delete_tendency(self):
        t = PhilosophyTendency(
            tendency_id="PHIL-0002",
            statement="Temporary tendency",
            origin="human",
        )
        self.store.save(t)
        self.assertTrue(self.store.exists("PHIL-0002"))

        ok = self.store.delete("PHIL-0002")
        self.assertTrue(ok)
        self.assertFalse(self.store.exists("PHIL-0002"))
        self.assertEqual(self.store.count(), 0)


class TestPhilosophyEngine(unittest.TestCase):
    """Test philosophy engine operations, human teaching, and precedence rules."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="phil_engine_test_")
        self.store = PhilosophyStore(store_dir=self.tmpdir)
        self.engine = PhilosophyEngine(store=self.store)

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_propose_candidate_from_lesson_preserves_provenance(self):
        lesson = Lesson(
            lesson_id="L-KRUN-100-verify",
            title="Always verify file existence before editing",
            description="Modifying absent files raises FileNotFoundError.",
            lesson_type=LessonType.FIRST_OBSERVATION,
            source_experience_id="KRUN-100",
            evidence_count=2,
            confidence=0.4,
        )

        cand = self.engine.propose_candidate_from_lesson(lesson)

        self.assertEqual(cand.status, PhilosophyStatus.CANDIDATE.value)
        self.assertIn("L-KRUN-100-verify", cand.source_lesson_ids)
        self.assertIn("L-KRUN-100-verify", cand.supporting_evidence_ids)
        self.assertIn("KRUN-100", cand.origin)
        self.assertEqual(len(cand.evolution_history), 1)
        self.assertEqual(cand.evolution_history[0].actor, "lesson")

    def test_human_teach_creates_tendency(self):
        t = self.engine.teach(
            statement="I tend to check git status before committing",
            initial_confidence=0.6,
        )

        self.assertEqual(t.status, PhilosophyStatus.SUPPORTED.value)
        self.assertAlmostEqual(t.confidence, 0.6)
        self.assertEqual(t.evolution_history[0].action_type, TeachingType.TEACH.value)

    def test_human_support_and_challenge_lifecycle(self):
        # 1. Teach initial candidate
        t = self.engine.teach(
            statement="I tend to write unit tests for edge cases",
            initial_confidence=0.3,
        )
        self.assertEqual(t.status, PhilosophyStatus.CANDIDATE.value)

        # 2. Support -> transitions CANDIDATE -> SUPPORTED
        t = self.engine.support(
            t.tendency_id,
            feedback="Confirmed in PR review",
            evidence_id="EV-PASS-01",
        )
        self.assertEqual(t.status, PhilosophyStatus.SUPPORTED.value)
        self.assertAlmostEqual(t.confidence, 0.5)
        self.assertIn("EV-PASS-01", t.supporting_evidence_ids)

        # 3. Challenge -> weakens tendency
        t = self.engine.challenge(
            t.tendency_id,
            feedback="Missed edge case in task 5",
            evidence_id="EV-FAIL-02",
        )
        self.assertAlmostEqual(t.confidence, 0.25)
        self.assertEqual(t.status, PhilosophyStatus.WEAKENED.value)
        self.assertIn("EV-FAIL-02", t.contradicting_evidence_ids)

        # Evolution history records all events
        self.assertEqual(len(t.evolution_history), 3)

    def test_human_modify_reshapes_statement(self):
        t = self.engine.teach("I tend to over-engineer simple tasks")
        t = self.engine.modify(
            t.tendency_id,
            new_statement="I tend to prefer simple modular implementations",
            reason="Reshaped by human mentor",
        )

        self.assertEqual(
            t.statement, "I tend to prefer simple modular implementations"
        )
        self.assertEqual(
            t.evolution_history[-1].action_type, TeachingType.MODIFY.value
        )

    def test_human_reject_and_retire(self):
        t1 = self.engine.teach("I tend to bypass lint checks when in a hurry")
        t1 = self.engine.reject(t1.tendency_id, reason="Security violation")
        self.assertEqual(t1.status, PhilosophyStatus.REJECTED.value)
        self.assertEqual(t1.confidence, 0.0)

        t2 = self.engine.teach("I tend to use Python 2 syntax")
        t2 = self.engine.retire(t2.tendency_id, reason="Obsolete language version")
        self.assertEqual(t2.status, PhilosophyStatus.RETIRED.value)
        self.assertEqual(t2.confidence, 0.0)

    def test_operational_self_knowledge_consultation(self):
        self.engine.teach(
            "I perform better when I verify assumptions first",
            initial_confidence=0.8,
        )
        self.engine.teach(
            "I tend to check test suite after modifying code",
            initial_confidence=0.7,
        )
        bad = self.engine.teach("Rejected tendency", initial_confidence=0.5)
        self.engine.reject(bad.tendency_id)

        prefs = self.engine.consult_soft_preferences()

        self.assertEqual(len(prefs), 2)
        self.assertEqual(
            prefs[0].statement, "I perform better when I verify assumptions first"
        )
        self.assertEqual(
            prefs[1].statement, "I tend to check test suite after modifying code"
        )

    def test_precedence_policy_prevents_philosophy_overrides(self):
        # 1. Normal preference check passes
        ok, msg = self.engine.enforce_precedence_policy("suggest_refactoring")
        self.assertTrue(ok)

        # 2. Cannot override Kernel / Security invariant
        with self.assertRaises(PhilosophyPrecedenceError) as cm1:
            self.engine.enforce_precedence_policy(
                "bypass_sandbox", violates_kernel_invariant=True
            )
        self.assertIn("Kernel invariant or security boundary", str(cm1.exception))

        # 3. Cannot bypass verification
        with self.assertRaises(PhilosophyPrecedenceError) as cm2:
            self.engine.enforce_precedence_policy(
                "skip_tests", bypasses_verification=True
            )
        self.assertIn("verification requirements", str(cm2.exception))

        # 4. Cannot override task contract
        with self.assertRaises(PhilosophyPrecedenceError) as cm3:
            self.engine.enforce_precedence_policy(
                "change_objective", violates_task_contract=True
            )
        self.assertIn("explicit task contract", str(cm3.exception))


if __name__ == "__main__":
    unittest.main()
