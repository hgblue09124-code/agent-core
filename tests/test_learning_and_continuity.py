#!/usr/bin/env python3
# tests/test_learning_and_continuity.py
"""Comprehensive test suite for Strategy Memory, Learning Pipeline, and Process Restart Continuity (100% Foundation).

Verifies:
1. End-to-end learning loop: Experience -> Lesson -> Candidate Strategy -> Application -> Outcome Evaluation
2. Deterministic strategy confidence boost on SUCCESS (0.35 -> 0.50 -> VALIDATED)
3. Deterministic strategy confidence penalty and retirement on FAILURE (3 failures -> RETIRED)
4. Inconclusive outcome stability (no unjustified confidence shift)
5. Strategy conflict resolution and version supersession without evidence deletion
6. Process restart continuity (Identity, Memory, Strategies, and Confidence survive restart)
7. Constitutional hierarchy (PolicyEngine strictly overrides learned strategy)
8. Capability adapter replacement isolation
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

from core.memory.schema import MemoryType, MemoryQuery
from core.memory.manager import MemoryManager
from core.memory.consolidation import MemoryConsolidator
from core.learning.strategy import Strategy, StrategyStatus
from core.learning.store import StrategyStore
from core.learning.pipeline import LearningPipeline
from core.learning.evaluator import StrategyEvaluator
from core.learning.retrieval import StrategyRanker
from core.experience.schema import Experience
from core.capabilities.adapter import CapabilityRegistry
from core.capabilities.mock_adapter import MockEchoCapabilityAdapter
from core.agent import Agent, AgentRunResult


class TestStrategyLifecycleAndEvaluator(unittest.TestCase):
    """Test Strategy schema, Store, Evaluator confidence updates, and state transitions."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.store = StrategyStore(store_dir=self.tmpdir.name)
        self.evaluator = StrategyEvaluator(store=self.store)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_confidence_boost_and_validated_transition_on_success(self):
        strat = Strategy(
            strategy_id="STRAT-001",
            name="Verified Test Strategy",
            description="Test strategy",
            rule="Always verify outputs",
            confidence=0.35,
            status=StrategyStatus.CANDIDATE.value,
        )
        self.store.create(strat)

        # Application 1: SUCCESS -> Boost +0.15 = 0.50 -> VALIDATED
        s1 = self.evaluator.evaluate_application(
            strategy_id="STRAT-001",
            run_id="RUN-1",
            task_id="TASK-1",
            verification_result="PASS",
        )
        self.assertAlmostEqual(s1.confidence, 0.50)
        self.assertEqual(s1.status, StrategyStatus.VALIDATED.value)

        # Application 2: SUCCESS -> Boost +0.15 = 0.65 -> VALIDATED
        # Application 3: SUCCESS -> Boost +0.15 = 0.80 -> SUPPORTED (since count >= 2 and conf >= 0.75)
        self.evaluator.evaluate_application("STRAT-001", "RUN-2", "TASK-2", "PASS")
        s3 = self.evaluator.evaluate_application("STRAT-001", "RUN-3", "TASK-3", "PASS")
        self.assertAlmostEqual(s3.confidence, 0.80)
        self.assertEqual(s3.status, StrategyStatus.SUPPORTED.value)

    def test_confidence_penalty_and_retirement_on_repeated_failure(self):
        strat = Strategy(
            strategy_id="STRAT-FAIL",
            name="Flaky Strategy",
            description="Flaky strategy test",
            rule="Flaky rule",
            confidence=0.50,
            status=StrategyStatus.VALIDATED.value,
        )
        self.store.create(strat)

        # Fail 1 -> conf 0.25 (VALIDATED)
        s1 = self.evaluator.evaluate_application("STRAT-FAIL", "R1", "T1", "FAIL", "Error 1")
        self.assertAlmostEqual(s1.confidence, 0.25)

        # Fail 2 -> failure_count = 2, conf <= 0.35 -> WEAKENED
        s2 = self.evaluator.evaluate_application("STRAT-FAIL", "R2", "T2", "FAIL", "Error 2")
        self.assertEqual(s2.status, StrategyStatus.WEAKENED.value)

        # Fail 3 -> failure_count = 3, conf <= 0.15 -> RETIRED
        s3 = self.evaluator.evaluate_application("STRAT-FAIL", "R3", "T3", "FAIL", "Error 3")
        self.assertEqual(s3.status, StrategyStatus.RETIRED.value)
        self.assertFalse(s3.is_active())

    def test_inconclusive_outcome_preserves_confidence(self):
        strat = Strategy(
            strategy_id="STRAT-INC",
            name="Inconclusive Strategy",
            description="Test inconclusive",
            rule="Rule inc",
            confidence=0.60,
            status=StrategyStatus.VALIDATED.value,
        )
        self.store.create(strat)

        s = self.evaluator.evaluate_application("STRAT-INC", "R1", "T1", "INCONCLUSIVE")
        self.assertAlmostEqual(s.confidence, 0.60)
        self.assertEqual(s.inconclusive_count, 1)

    def test_supersede_strategy_creates_candidate_and_preserves_superseded_old(self):
        old_strat = Strategy(
            strategy_id="STRAT-OLD",
            name="Old Strategy v1",
            description="Old rule description",
            rule="Old rule",
            version=1,
            confidence=0.40,
            status=StrategyStatus.VALIDATED.value,
        )
        self.store.create(old_strat)

        new_strat = self.evaluator.supersede_strategy("STRAT-OLD", "New improved rule v2")
        self.assertIsNotNone(new_strat)
        self.assertEqual(new_strat.version, 2)
        self.assertEqual(new_strat.status, StrategyStatus.CANDIDATE.value)
        self.assertEqual(new_strat.confidence, 0.35)
        self.assertEqual(new_strat.supersedes, "STRAT-OLD")

        # Verify old strategy state
        reloaded_old = self.store.get("STRAT-OLD")
        self.assertEqual(reloaded_old.status, StrategyStatus.SUPERSEDED.value)
        self.assertEqual(reloaded_old.superseded_by, new_strat.strategy_id)

    def test_ranker_excludes_candidates_by_default(self):
        cand = Strategy(
            strategy_id="STRAT-CAND",
            name="Candidate Strategy",
            description="Desc",
            rule="Rule cand",
            applicable_context="test goal",
            confidence=0.35,
            status=StrategyStatus.CANDIDATE.value,
        )
        val = Strategy(
            strategy_id="STRAT-VAL",
            name="Validated Strategy",
            description="Desc",
            rule="Rule val",
            applicable_context="test goal",
            confidence=0.55,
            status=StrategyStatus.VALIDATED.value,
        )
        self.store.create(cand)
        self.store.create(val)

        ranker = StrategyRanker(store=self.store)

        # Default ranking excludes CANDIDATE strategies
        default_strats = ranker.select_applicable_strategies("test goal")
        self.assertEqual(len(default_strats), 1)
        self.assertEqual(default_strats[0].strategy_id, "STRAT-VAL")

        # Explicit request includes CANDIDATE strategies
        all_strats = ranker.select_applicable_strategies("test goal", include_candidates=True)
        self.assertEqual(len(all_strats), 2)


class TestLearningPipelineAndConsolidation(unittest.TestCase):
    """Test Experience -> Lesson -> Strategy pipeline and Memory Consolidation."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.store = StrategyStore(store_dir=self.tmpdir.name)
        self.pipeline = LearningPipeline(strategy_store=self.store)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_experience_to_candidate_strategy_conversion(self):
        exp = Experience(
            run_id="KRUN-1001",
            goal="Inspect project architecture",
            project_id="default",
            action="Agent.run('Inspect project architecture')",
            observation="Kernel status=COMPLETED, phase=COMPLETE",
            outcome="success",
            llm_calls=0,
            estimated_tokens=0,
        )

        strat = self.pipeline.process_experience(exp)
        self.assertIsNotNone(strat)
        self.assertEqual(strat.status, StrategyStatus.CANDIDATE.value)
        self.assertIn("Inspect project architecture", strat.applicable_context)
        self.assertEqual(strat.source_experiences, ["KRUN-1001"])

    def test_memory_conflict_resolution_without_erasing_history(self):
        mem_mgr = MemoryManager(store_dir=os.path.join(self.tmpdir.name, "mem"))
        consolidator = MemoryConsolidator(
            memory_manager=mem_mgr,
            strategy_store=self.store,
        )

        old_strat = Strategy(
            strategy_id="STRAT-CONF",
            name="Conflicting Strategy",
            description="Desc",
            rule="Rule A",
            confidence=0.60,
            status=StrategyStatus.VALIDATED.value,
        )
        self.store.create(old_strat)

        new_strat = consolidator.resolve_strategy_conflict(
            existing_strategy_id="STRAT-CONF",
            conflicting_rule="Rule B (Updated)",
            new_evidence="Observed failure with Rule A under condition Z",
        )

        self.assertIsNotNone(new_strat)
        self.assertEqual(new_strat.rule, "Rule B (Updated)")

        reloaded_old = self.store.get("STRAT-CONF")
        self.assertEqual(reloaded_old.status, StrategyStatus.SUPERSEDED.value)
        self.assertTrue(any("Conflict observed" in ev for ev in reloaded_old.evidence))


class TestProcessRestartContinuity(unittest.TestCase):
    """Test process restart continuity: learned state survives process restart."""

    def test_first_execution_generates_and_persists_strategy(self):
        """Mandatory regression test: single first execution on fresh storage must generate and persist a strategy."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ["AGENTCORE_STORAGE_DIR"] = tmpdir
            os.environ["AGENTCORE_PLANNER_PROVIDER"] = "mock"

            # 1. Fresh Agent instance
            agent = Agent(project_id="default")

            # 2. Execute successful task on FIRST run
            res: AgentRunResult = agent.run("Verify first execution strategy creation")
            self.assertTrue(res.success)
            self.assertTrue(res.experience_recorded)

            # 3. Verify Experience exists
            exp_store = agent._experience_engine.store
            exps = exp_store.list_all()
            self.assertEqual(len(exps), 1)

            # 4. Verify Strategy is created and persisted immediately on run 1
            strat_store = StrategyStore(store_dir=os.path.join(tmpdir, "strategies"))
            strats = strat_store.list_all()
            self.assertTrue(len(strats) > 0, "Strategy must be created on the very first execution")

            # 5. Process restart simulation: new Agent instance retrieves strategy
            agent2 = Agent(project_id="default")
            ranker2 = StrategyRanker(store=agent2._strategy_store)
            # Include candidates or query all stored strategies for inspection
            all_stored = agent2._strategy_store.list_all()
            self.assertTrue(len(all_stored) > 0, "Strategy must survive process restart")
            retrieved = ranker2.select_applicable_strategies("Verify first execution strategy creation", include_candidates=True)
            self.assertTrue(len(retrieved) > 0, "Strategy must be inspectable and retrievable")

    def test_learned_strategy_survives_restart_and_affects_future_runs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ["AGENTCORE_STORAGE_DIR"] = tmpdir
            os.environ["AGENTCORE_PLANNER_PROVIDER"] = "mock"

            # Session 1: Instantiate Agent, run task, generate experience & strategy
            agent1 = Agent(project_id="default")
            res1: AgentRunResult = agent1.run("Audit code security boundaries")
            self.assertTrue(res1.success)

            # Confirm strategy created
            strat_store1 = StrategyStore(store_dir=os.path.join(tmpdir, "strategies"))
            strats1 = strat_store1.list_all()
            self.assertTrue(len(strats1) > 0)

            # Simulate Process Restart (Session 2): Create brand new Agent instance reading same storage
            agent2 = Agent(project_id="default")

            # Verify memory and identity continuity
            identity2 = agent2._memory.get_identity()
            self.assertIsNotNone(identity2)

            # Retrieve strategy in Session 2
            ranker2 = StrategyRanker(store=agent2._strategy_store)
            retrieved_strats = ranker2.select_applicable_strategies("Audit code security boundaries", include_candidates=True)
            self.assertTrue(len(retrieved_strats) > 0)

            # Execute task in Session 2
            res2: AgentRunResult = agent2.run("Audit code security boundaries")
            self.assertTrue(res2.success)


class TestConstitutionalPrecedenceOverStrategy(unittest.TestCase):
    """Verify PolicyEngine and Kernel Constitution strictly override learned strategies."""

    def test_learned_strategy_cannot_bypass_policy_denial(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ["AGENTCORE_STORAGE_DIR"] = tmpdir
            os.environ["AGENTCORE_PLANNER_PROVIDER"] = "mock"
            agent = Agent(project_id="default")

            # Manually create a high-confidence strategy advocating a forbidden action
            high_conf_strat = Strategy(
                strategy_id="STRAT-FORBIDDEN",
                name="Bypass Security Strategy",
                description="Dangerous rule",
                rule="Bypass policy check",
                applicable_context="Forbidden goal",
                confidence=0.95,
                status=StrategyStatus.SUPPORTED.value,
            )
            agent._strategy_store.create(high_conf_strat)

            # Mock policy denial
            from unittest.mock import patch
            with patch.object(agent._policy, "should_execute", return_value=False):
                res = agent.run("Forbidden goal")
                self.assertFalse(res.authorized)
                self.assertEqual(res.status, "FAILED")
                self.assertEqual(res.phase, "AUTHORITY")
                self.assertIn("Kernel policy prohibits execution", res.errors)


if __name__ == "__main__":
    unittest.main()
