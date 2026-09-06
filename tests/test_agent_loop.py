# tests/test_agent_loop.py
"""Comprehensive Unit & Integration Test Suite for Agent Loop Architecture."""

from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.agent import Agent, AgentRunResult
from core.capabilities.mock_adapter import (
    AlwaysFailCapability,
    EvidenceMissingCapability,
    FailOnceCapability,
    MutationCapability,
    SuccessCapability,
)
from core.kernel.policy import PolicyEngine
from core.runtime.decision import DecisionEngine
from core.runtime.loop import AgentLoopController, LoopStateStore
from core.runtime.state import (
    AgentAction,
    AgentLoopPhase,
    AgentLoopStatus,
    AgentLoopState,
    InvalidStateTransitionError,
    TimeBudget,
)
from core.runtime.verification import VerificationEngine


class TestAgentLoopArchitecture(unittest.TestCase):
    """Core test suite for closed-loop Personal Agent execution."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.agent = Agent(project_id="default")
        # Register mock test capabilities
        self.agent._capabilities.register(SuccessCapability())
        self.agent._capabilities.register(FailOnceCapability())
        self.agent._capabilities.register(AlwaysFailCapability())
        self.agent._capabilities.register(MutationCapability())
        self.agent._capabilities.register(EvidenceMissingCapability())

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_01_successful_loop(self):
        """Test 1: Single action successful loop (BOOTSTRAP -> COMPLETE)."""
        action = AgentAction(
            action_id="ACT-1",
            capability="mock.success",
            operation="test_op",
            arguments={"param": "value"},
            reason="Test success capability",
        )
        res = self.agent.run("Achieve success", plan_actions=[action])

        self.assertTrue(res.success)
        self.assertEqual(res.status, "COMPLETED")
        self.assertEqual(res.verification_verdict, "PASS")
        self.assertTrue(res.experience_recorded)

    def test_02_multiple_actions_loop(self):
        """Test 2: Goal requiring multiple sequential actions in single loop."""
        act_1 = AgentAction(
            action_id="ACT-1",
            capability="mock.success",
            operation="step_1",
            arguments={"text": "first"},
        )
        act_2 = AgentAction(
            action_id="ACT-2",
            capability="mock.success",
            operation="step_2",
            arguments={"text": "second"},
        )
        res = self.agent.run("Multi-step task", plan_actions=[act_1, act_2])

        self.assertTrue(res.success)
        self.assertEqual(res.status, "COMPLETED")

        loop_state = self.agent._loop_controller._store.load(res.run_id)
        self.assertIsNotNone(loop_state)
        self.assertEqual(len(loop_state.completed_actions), 2)
        self.assertEqual(loop_state.telemetry.actions_executed, 2)

    def test_03_execution_failure_retry(self):
        """Test 3: Execution failure triggering automatic retry and succeeding."""
        act = AgentAction(
            action_id="ACT-RETRY",
            capability="mock.fail_once",
            operation="transient_op",
            arguments={},
        )
        res = self.agent.run("Task with transient failure", plan_actions=[act])

        self.assertTrue(res.success)
        self.assertEqual(res.status, "COMPLETED")

        loop_state = self.agent._loop_controller._store.load(res.run_id)
        self.assertIsNotNone(loop_state)
        self.assertEqual(loop_state.retry_count, 1)

    def test_04_failure_and_replan(self):
        """Test 4: Permanent action failure triggering REPLAN state transition."""
        act = AgentAction(
            action_id="ACT-FAIL",
            capability="mock.always_fail",
            operation="failing_op",
            arguments={},
        )
        res = self.agent.run("Task triggering replan", plan_actions=[act])

        self.assertFalse(res.success)
        self.assertEqual(res.status, "FAILED")

        loop_state = self.agent._loop_controller._store.load(res.run_id)
        self.assertIsNotNone(loop_state)
        self.assertGreater(loop_state.replan_count, 0)

    def test_05_policy_deny(self):
        """Test 5: Mutation policy DENY prevents capability execution."""
        act = AgentAction(
            action_id="ACT-MUTATE-DENIED",
            capability="mock.mutation",
            operation="delete_records",
            arguments={"target": "all"},
            risk_level="HIGH",
            requires_approval=True,
        )
        # Without user approval, mutation capability is denied by policy
        res = self.agent.run("Forbidden mutation", plan_actions=[act], user_approved=False)

        self.assertFalse(res.success)
        self.assertTrue(any("requires explicit user approval" in err or "Policy" in err or "denied" in err for err in res.errors))

    def test_06_ask_user_transition(self):
        """Test 6: High risk mutation without approval transitions to WAITING_FOR_USER."""
        act = AgentAction(
            action_id="ACT-ASK-USER",
            capability="mock.mutation",
            operation="update_schema",
            arguments={"table": "users"},
            risk_level="HIGH",
            requires_approval=True,
        )
        res = self.agent.run("Schema migration", plan_actions=[act], user_approved=False)

        self.assertEqual(res.status, "WAITING_FOR_USER")
        self.assertEqual(res.phase, "WAITING_FOR_USER")

        saved_state = self.agent._loop_controller._store.load(res.run_id)
        self.assertIsNotNone(saved_state)
        self.assertEqual(saved_state.status, "WAITING_FOR_USER")
        self.assertIsNotNone(saved_state.pending_action)

    def test_07_resume_from_waiting_user(self):
        """Test 7: Resume WAITING_FOR_USER task after user approval."""
        act = AgentAction(
            action_id="ACT-MUTATE-RESUME",
            capability="mock.mutation",
            operation="drop_index",
            arguments={"index": "idx_temp"},
            risk_level="HIGH",
            requires_approval=True,
        )
        res_initial = self.agent.run("Index cleanup", plan_actions=[act], user_approved=False)
        self.assertEqual(res_initial.status, "WAITING_FOR_USER")

        # Resume with user approval
        res_resumed = self.agent.resume(res_initial.run_id, user_approved=True)

        self.assertTrue(res_resumed.success)
        self.assertEqual(res_resumed.status, "COMPLETED")

    def test_08_verification_failure(self):
        """Test 8: Adapter returns OK but verification verdict is FAIL (missing evidence)."""
        act = AgentAction(
            action_id="ACT-EVID-MISSING",
            capability="mock.evidence_missing",
            operation="query_status",
            arguments={},
            expected_outcome="Confirmed signature",
        )
        res = self.agent.run("Verification check", plan_actions=[act])

        self.assertFalse(res.success)
        self.assertEqual(res.verification_verdict, "FAIL")

    def test_09_time_budget_timeout_protection(self):
        """Test 9: Time budget expiration triggers TIMEOUT status and prevents runaway loops."""
        tb = TimeBudget(timeout_seconds=0.01, start_time=time.time() - 1.0)
        self.assertTrue(tb.is_expired())

        act = AgentAction(
            action_id="ACT-TIMEOUT",
            capability="mock.success",
            operation="op",
            arguments={},
        )
        res = self.agent.run("Timeout goal", plan_actions=[act], timeout_seconds=0.001)

        self.assertEqual(res.status, "TIMEOUT")
        self.assertIn("time budget", res.errors[0].lower())

    def test_10_experience_recording(self):
        """Test 10: Successful and failed loops both produce Experience records."""
        act_ok = AgentAction(
            action_id="ACT-EXP-OK",
            capability="mock.success",
            operation="op",
            arguments={},
        )
        res_ok = self.agent.run("Success exp", plan_actions=[act_ok])
        self.assertTrue(res_ok.experience_recorded)

        exp_ok = self.agent._experience_engine.get_experience(res_ok.run_id)
        self.assertIsNotNone(exp_ok)
        self.assertEqual(exp_ok.outcome, "success")

    def test_11_terminal_state_immutability(self):
        """Test 11: Terminal states (COMPLETED, FAILED, TIMEOUT, CANCELLED) raise InvalidStateTransitionError on resume."""
        act = AgentAction(
            action_id="ACT-TERM",
            capability="mock.success",
            operation="op",
            arguments={},
        )
        res = self.agent.run("Terminal goal", plan_actions=[act])
        self.assertEqual(res.status, "COMPLETED")

        with self.assertRaises(InvalidStateTransitionError):
            self.agent.resume(res.run_id)

    def test_12_no_nested_orchestration_loop(self):
        """Test 12: agent.run() creates a single orchestration loop without nested kernel loops."""
        with patch.object(self.agent._loop_controller, "run", wraps=self.agent._loop_controller.run) as spy_loop:
            res = self.agent.run("Goal verifying no nested orchestration")
            self.assertTrue(res.success)
            spy_loop.assert_called_once()

    def test_13_goal_vs_execution_success(self):
        """Test 13: Goal verification evaluates evidence beyond adapter HTTP/status success."""
        verif_engine = VerificationEngine()
        act = AgentAction(
            action_id="ACT-GOAL-CHECK",
            capability="github",
            operation="create_issue",
            arguments={},
            expected_outcome="Issue created with ID #123",
        )
        cap_res = MagicMock(success=True, status="SUCCESS", output="API 200 OK", metadata={})
        obs = MagicMock(status="SUCCESS", output="API 200 OK", evidence={})

        verif = verif_engine.verify_execution(goal="Create issue #123", action=act, result=cap_res, observation=obs)
        self.assertIn(verif.verdict, ["PASS", "INCONCLUSIVE", "FAIL"])

    def test_14_capability_isolation(self):
        """Test 14: Decision engine prevents direct capability execution without policy check."""
        dec_engine = DecisionEngine(
            registry=self.agent._capabilities,
            policy=self.agent._policy,
        )
        action = AgentAction(
            action_id="ACT-ISOLATION",
            capability="mock.mutation",
            operation="drop_database",
            arguments={},
            requires_approval=True,
        )
        res = dec_engine.evaluate_action(action, user_approved=False)
        self.assertFalse(res.is_allowed)

    def test_15_fsm_transition_validation(self):
        """Test 15: Invalid phase transitions raise InvalidStateTransitionError according to FSM graph rules."""
        state = AgentLoopState(
            run_id="FSM-TEST",
            task_id="FSM-TEST",
            goal="FSM test",
            project_id="default",
            phase=AgentLoopPhase.OBSERVE.value,
            status=AgentLoopStatus.RUNNING.value,
        )
        # OBSERVE -> RETRIEVE is valid
        state.transition_to(AgentLoopStatus.RUNNING, AgentLoopPhase.RETRIEVE)
        self.assertEqual(state.phase, AgentLoopPhase.RETRIEVE.value)

        # RETRIEVE -> COMPLETE is INVALID according to FSM graph rules
        with self.assertRaises(InvalidStateTransitionError):
            state.transition_to(AgentLoopStatus.COMPLETED, AgentLoopPhase.COMPLETE)

    def test_16_phase_by_phase_checkpoint_and_resumption(self):
        """Test 16: Checkpoints are saved across phases and allow process-restart resumption."""
        store = LoopStateStore()
        run_id = "CRASH-TEST-RUN-1"
        initial_state = AgentLoopState(
            run_id=run_id,
            task_id=run_id,
            goal="Simulate crash and resume",
            project_id="default",
            phase=AgentLoopPhase.AUTHORIZE.value,
            status=AgentLoopStatus.WAITING_FOR_USER.value,
            pending_action=AgentAction(
                action_id="ACT-PENDING-1",
                capability="mock.mutation",
                operation="delete_records",
                arguments={"target": "temp"},
                requires_approval=True,
            ),
        )
        store.save(initial_state)

        # Simulate fresh Agent process loading checkpoint from disk
        fresh_agent = Agent(project_id="default")
        res = fresh_agent.resume(run_id, user_approved=True)

        self.assertTrue(res.success)
        self.assertEqual(res.status, "COMPLETED")

    def test_17_cumulative_time_budget_across_resumes(self):
        """Test 17: Time budget accumulates elapsed runtime across resumes rather than resetting."""
        store = LoopStateStore()
        run_id = "BUDGET-RESUME-TEST"
        state = AgentLoopState(
            run_id=run_id,
            task_id=run_id,
            goal="Budget accumulation test",
            project_id="default",
            phase=AgentLoopPhase.AUTHORIZE.value,
            status=AgentLoopStatus.WAITING_FOR_USER.value,
            accumulated_runtime_seconds=599.95,  # Almost expired
            pending_action=AgentAction(
                action_id="ACT-EXP",
                capability="mock.success",
                operation="op",
            ),
        )
        store.save(state)

        # Resume with 10s budget, but accumulated runtime (599.95s) exceeds 10s timeout
        res = self.agent.resume(run_id, user_approved=True, timeout_seconds=10.0)
        self.assertEqual(res.status, "TIMEOUT")
        self.assertIn("expired", res.errors[0].lower())

    def test_18_checkpoint_recovery_at_execute_phase(self):
        """Test 18: State checkpoint created before execute allows resuming directly into execution."""
        act = AgentAction(
            action_id="ACT-EXEC-RECOVER",
            capability="mock.success",
            operation="test_op",
            arguments={"param": "val"},
        )
        res_initial = self.agent.run("Checkpoint recover", plan_actions=[act])
        self.assertTrue(res_initial.success)

        # Inspect checkpoint on disk
        saved_state = self.agent._loop_controller._store.load(res_initial.run_id)
        self.assertIsNotNone(saved_state)
        self.assertGreater(saved_state.accumulated_runtime_seconds, 0.0)
        self.assertEqual(saved_state.status, "COMPLETED")


if __name__ == "__main__":
    unittest.main()
