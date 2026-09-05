#!/usr/bin/env python3
# tests/test_personal_agent_beta_real_use.py
"""Personal Agent Beta v0.1 Real-Use Acceptance Workflow Test Suite.

Verifies actual observable behavior across a 16-step realistic Personal Agent workflow:
1. Initialize Agent
2. Store personal information in Vault
3. Retrieve personal information from Vault
4. Update personal information in Vault
5. Perform basic reasoning task
6. Create multi-step plan task
7. Discover registered capabilities
8. Execute safe read-only capability
9. Attempt restricted write capability without approval -> DENIED
10. Execute same approved write capability -> SUCCESS
11. Record experience
12. Persist state
13. Create fresh Agent instance (simulating process restart)
14. Verify persisted memory and experience on fresh instance
15. Resume previous run on fresh instance
16. Execute another task after restart on fresh instance
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from core.agent import Agent, AgentRunResult
from core.capabilities.schema import CapabilityResult


class TestPersonalAgentRealUseWorkflow(unittest.TestCase):
    """Real-use acceptance workflow test suite for Personal Agent Beta v0.1."""

    def setUp(self):
        os.environ["AGENTCORE_PLANNER_PROVIDER"] = "mock"

    def test_16_step_real_use_acceptance_workflow(self):
        """Execute the 16-step real-use Personal Agent workflow sequentially."""

        # 1. Initialize Agent
        agent = Agent(project_id="default")
        self.assertIsNotNone(agent)

        # 2. Store personal information
        stored = agent._vault.store_context("user_email", {"email": "user@example.com"}, category="user_identity")
        self.assertTrue(stored)

        # 3. Retrieve personal information
        retrieved = agent._vault.retrieve_context("user@example.com")
        self.assertEqual(len(retrieved), 1)
        self.assertEqual(retrieved[0]["data"]["email"], "user@example.com")

        # 4. Update personal information
        updated = agent._vault.store_context("user_email", {"email": "new_email@example.com"}, category="user_identity")
        self.assertTrue(updated)
        retrieved_updated = agent._vault.retrieve_context("new_email@example.com")
        self.assertEqual(len(retrieved_updated), 1)
        self.assertEqual(retrieved_updated[0]["data"]["email"], "new_email@example.com")

        # 5. Perform basic reasoning task
        res_reasoning: AgentRunResult = agent.run("Evaluate current user preferences and project setup")
        self.assertTrue(res_reasoning.success)
        self.assertEqual(res_reasoning.status, "COMPLETED")

        # 6. Create multi-step plan task
        res_plan: AgentRunResult = agent.run("Inspect workspace architecture and verify documentation")
        self.assertTrue(res_plan.success)
        self.assertTrue(len(res_plan.plan_steps) >= 1)

        # 7. Discover capability
        specs = agent._capabilities.list_specs()
        cap_ids = [s.capability_id for s in specs]
        self.assertIn("github_integration", cap_ids)

        # 8. Execute safe capability
        res_safe: CapabilityResult = agent.execute_capability(
            "github_integration",
            {"action": "get_repo", "owner": "hgblue09124", "repo": "agent-core", "mock_offline": True},
        )
        self.assertTrue(res_safe.success)
        self.assertEqual(res_safe.status, "SUCCESS")

        # 9. Attempt restricted/write capability without approval -> DENIED
        res_unapproved: CapabilityResult = agent.execute_capability(
            "github_integration",
            {"action": "create_issue_comment", "owner": "hgblue09124", "repo": "agent-core", "issue_number": 1, "body": "unapproved comment"},
            user_approved=False,
        )
        self.assertFalse(res_unapproved.success)
        self.assertEqual(res_unapproved.status, "DENIED")
        self.assertIn("requires explicit user approval", res_unapproved.error)

        # 10. Execute same approved write action -> SUCCESS
        res_approved: CapabilityResult = agent.execute_capability(
            "github_integration",
            {"action": "create_issue_comment", "owner": "hgblue09124", "repo": "agent-core", "issue_number": 1, "body": "approved comment", "mock_offline": True},
            user_approved=True,
        )
        self.assertTrue(res_approved.success)
        self.assertEqual(res_approved.status, "SUCCESS")

        # 11. Record experience
        exp = agent._experience_engine.get_experience(res_plan.run_id)
        self.assertIsNotNone(exp)
        self.assertEqual(exp.run_id, res_plan.run_id)

        # 12. Persist state (happens automatically via atomic file persistence)
        run_id_to_resume = res_plan.run_id

        # 13. Create fresh Agent instance (simulating process restart)
        fresh_agent = Agent(project_id="default")
        self.assertIsNotNone(fresh_agent)

        # 14. Verify persisted memory/experience on fresh instance
        persisted_exp = fresh_agent._experience_engine.get_experience(run_id_to_resume)
        self.assertIsNotNone(persisted_exp)
        self.assertEqual(persisted_exp.run_id, run_id_to_resume)

        persisted_vault = fresh_agent._vault.retrieve_context("new_email@example.com")
        self.assertEqual(len(persisted_vault), 1)

        # 15. Resume previous run on fresh instance
        resumed_res = fresh_agent.resume(run_id_to_resume)
        self.assertEqual(resumed_res.run_id, run_id_to_resume)
        self.assertTrue(resumed_res.success)

        # 16. Execute another task after restart
        post_restart_res: AgentRunResult = fresh_agent.run("Post-restart execution task")
        self.assertTrue(post_restart_res.success)
        self.assertNotEqual(post_restart_res.run_id, run_id_to_resume)


if __name__ == "__main__":
    unittest.main()
