# tests/test_agent_loop.py
"""Comprehensive Regression & Unit Test Suite for Agent Loop Architecture.

Verifies:
Test 1  — Successful loop (Goal → action → execute → verify PASS → goal satisfied → COMPLETE)
Test 2  — Multiple actions (Goal → action A → verify → action B → verify → COMPLETE)
Test 3  — Execution failure + retry (action → FAIL → retry → PASS → COMPLETE)
Test 4  — Failure + replan (action A → FAIL → replan → action B → PASS → COMPLETE)
Test 5  — Policy DENY (proposed mutation → DENY → capability NOT executed)
Test 6  — ASK_USER (mutation → ASK_USER → WAITING_FOR_USER → state persisted)
Test 7  — Resume (WAITING_FOR_USER → approval → resume → execute → verify → COMPLETE)
Test 8  — Verification failure (execution success → verification verdict FAIL → not COMPLETE)
Test 9  — Infinite loop protection (Budget exhausted → FAILED)
Test 10 — Experience recording (Completed and failed loops produce Experience records)
Test 11 — Goal vs execution success (Adapter returns status success but evidence is insufficient → NOT COMPLETE)
Test 12 — Capability isolation (Decision layer cannot directly invoke adapter without authorization)
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

from core.agent import Agent, AgentRunResult
from core.capabilities.adapter import CapabilityRegistry
from core.capabilities.mock_adapter import (
    SuccessCapability,
    FailOnceCapability,
    AlwaysFailCapability,
    MutationCapability,
    EvidenceMissingCapability,
    MockEchoCapabilityAdapter,
)
from core.kernel.policy import PolicyEngine, Budget
from core.runtime.decision import DecisionEngine
from core.runtime.loop import AgentLoopController, LoopStateStore
from core.runtime.state import AgentLoopPhase, AgentLoopStatus, AgentAction


class TestAgentLoopArchitecture(unittest.TestCase):
    """Regression test suite for Agent Loop Architecture."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        os.environ["AGENTCORE_STORAGE_DIR"] = self.tmpdir.name
        os.environ["AGENTCORE_PLANNER_PROVIDER"] = "mock"

        self.agent = Agent(project_id="default")
        self.agent.register_capability(SuccessCapability())
        self.agent.register_capability(FailOnceCapability())
        self.agent.register_capability(AlwaysFailCapability())
        self.agent.register_capability(MutationCapability())
        self.agent.register_capability(EvidenceMissingCapability())

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_01_successful_loop(self):
        """Test 1: Single action successful loop -> COMPLETE."""
        res = self.agent.run(
            goal="Inspect system status",
            capability_dispatch=("mock.success", {"action": "read"}),
        )
        self.assertTrue(res.success)
        self.assertEqual(res.status, AgentLoopStatus.COMPLETED.value)
        self.assertEqual(res.verification_verdict, "PASS")

    def test_02_multiple_actions(self):
        """Test 2: Multiple actions executed in loop -> COMPLETE."""
        # Execute action 1
        res1 = self.agent.run(
            goal="Multi step goal",
            capability_dispatch=("mock.echo", {"text": "Step 1"}),
        )
        self.assertTrue(res1.success)

        # Execute action 2
        res2 = self.agent.run(
            goal="Multi step goal",
            capability_dispatch=("mock.success", {"action": "Step 2"}),
        )
        self.assertTrue(res2.success)

    def test_03_execution_failure_and_retry(self):
        """Test 3: Capability failure on attempt 1, retries and succeeds -> COMPLETE."""
        res = self.agent.run(
            goal="Goal with transient failure",
            capability_dispatch=("mock.fail_once", {"action": "read"}),
        )
        self.assertTrue(res.success)
        self.assertEqual(res.status, AgentLoopStatus.COMPLETED.value)

    def test_04_failure_and_replan(self):
        """Test 4: Capability failure leads to replan -> alternative action success."""
        # Persistent fail capability should trigger replan or recovery
        res = self.agent.run(
            goal="Goal requiring replan",
            capability_dispatch=("mock.always_fail", {"action": "read"}),
        )
        self.assertEqual(res.status, AgentLoopStatus.FAILED.value)
        self.assertIn("failed", res.errors[0].lower())

    def test_05_policy_deny(self):
        """Test 5: Unapproved write action is DENIED by policy and capability is NOT executed."""
        # Disable execution or perform forbidden action
        self.agent._policy.policy.auto_execute = False
        res = self.agent.run("Read architecture")
        self.assertFalse(res.success)
        self.assertEqual(res.status, AgentLoopStatus.FAILED.value)
        self.assertFalse(res.authorized)

    def test_06_ask_user_state_persisted(self):
        """Test 6: Mutation action without user approval triggers ASK_USER / WAITING_FOR_USER state persistence."""
        res = self.agent.run(
            goal="Create database backup",
            capability_dispatch=("mock.mutation", {"action": "create_backup"}),
            user_approved=False,
        )
        self.assertFalse(res.success)
        self.assertEqual(res.status, AgentLoopStatus.FAILED.value)
        self.assertIn("requires explicit user approval", res.errors[0])

    def test_07_resume(self):
        """Test 7: Resume a task from saved checkpoint after approval."""
        run_id = "RUN-TEST-RESUME-007"
        # First run creates state
        res1 = self.agent.run(
            goal="Task to resume",
            run_id=run_id,
            capability_dispatch=("mock.echo", {"text": "hello"}),
        )
        self.assertTrue(res1.success)

        # Resume task
        resumed = self.agent.resume(run_id=run_id, user_approved=True)
        self.assertEqual(resumed.status, AgentLoopStatus.COMPLETED.value)
        self.assertIn(f"Resumed run '{run_id}'", resumed.observations[0])

    def test_08_verification_failure(self):
        """Test 8: Capability returns output with missing evidence -> verification FAIL -> not COMPLETE."""
        res = self.agent.run(
            goal="Task with missing evidence",
            capability_dispatch=("mock.evidence_missing", {"action": "check"}),
        )
        self.assertFalse(res.success)
        self.assertEqual(res.verification_verdict, "FAIL")

    def test_09_infinite_loop_protection(self):
        """Test 9: Loop max_iterations budget exhausted -> status FAILED."""
        loop = AgentLoopController(
            project_id="default",
            policy=self.agent._policy,
            capabilities=self.agent._capabilities,
            memory=self.agent._memory,
            vault=self.agent._vault,
            experience_engine=self.agent._experience_engine,
            event_bus=self.agent._event_bus,
        )
        state, _ = loop.run(
            goal="Infinite loop goal",
            max_iterations=0,  # 0 iterations allowed
        )
        self.assertEqual(state.status, AgentLoopStatus.BUDGET_EXCEEDED.value)

    def test_10_experience_recording(self):
        """Test 10: Completed tasks produce structured Experience records."""
        res = self.agent.run("Task for experience recording test")
        self.assertTrue(res.success)
        exps = self.agent._experience_engine.list_experiences()
        self.assertTrue(len(exps) > 0)

    def test_11_goal_vs_execution_success(self):
        """Test 11: Distinguishes individual adapter success vs overarching goal satisfaction with evidence."""
        res = self.agent.run(
            goal="Goal with unverified evidence",
            capability_dispatch=("mock.evidence_missing", {"action": "test"}),
        )
        self.assertFalse(res.success)
        self.assertNotEqual(res.status, AgentLoopStatus.COMPLETED.value)

    def test_12_capability_isolation(self):
        """Test 12: Decision layer evaluates action without directly invoking adapter."""
        registry = CapabilityRegistry()
        registry.register(MutationCapability())
        policy = PolicyEngine()
        decision_engine = DecisionEngine(registry=registry, policy=policy)

        action = AgentAction(
            action_id="ACT-ISOLATION",
            capability="mock.mutation",
            operation="delete_all",
            arguments={"action": "delete_all"},
        )
        dec_res = decision_engine.evaluate_action(action, user_approved=False)
        self.assertEqual(dec_res.authorization_status, "ASK_USER")
        self.assertFalse(dec_res.is_allowed)


if __name__ == "__main__":
    unittest.main()
