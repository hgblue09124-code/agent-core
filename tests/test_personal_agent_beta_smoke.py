#!/usr/bin/env python3
# tests/test_personal_agent_beta_smoke.py
"""Personal Agent Beta v0.1 Representative Missions Executable Smoke Test Suite.

Executes tests for all 15 Beta Missions defined in the Beta Mission Specification:
- Mission 01: Remember Information
- Mission 02: Retrieve Stored Information
- Mission 03: Update Stored Information
- Mission 04: Basic Reasoning Task
- Mission 05: Multi-Step Planning Task
- Mission 06: Vault Read/Write
- Mission 07: Capability Discovery
- Mission 08: Capability Execution (MOCK/LOCAL vs REAL_EXTERNAL)
- Mission 09: Policy Denial
- Mission 10: Approval-Required Write Action
- Mission 11: Capability Failure Handling
- Mission 12: Resume Interrupted Task (Process Restart Continuity)
- Mission 13: End-to-End Personal-Agent Workflow
- Mission 14: Repeated Execution / Continuity (Process Restart Persistence)
- Mission 15: External Capability Failure Without False Success (HTTP 401/403/404/503 -> FAILED)

Evidence Classifications:
- MOCK/LOCAL: Executable locally with mock planner or in-memory/filesystem stores.
- REAL_EXTERNAL: Executed against live external API if GITHUB_TOKEN present; skipped or marked NOT EXECUTED if absent.
"""

from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import patch
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from core.agent import Agent, AgentRunResult
from core.capabilities.adapter import BaseCapabilityAdapter
from core.capabilities.github import GitHubCapabilityAdapter
from core.capabilities.schema import CapabilityConstraint, CapabilityResult, CapabilitySpec
from core.memory.schema import MemoryType
from core.vault.adapter import BaseVaultAdapter, PersonalVaultAdapter


class TestPersonalAgentBeta15Missions(unittest.TestCase):
    """Executable smoke test suite for the 15 Beta Missions."""

    def setUp(self):
        os.environ["AGENTCORE_PLANNER_PROVIDER"] = "mock"
        self.agent = Agent(project_id="default")

    def test_mission_01_remember_information(self):
        """Mission 1: Remember Information [Mode: MOCK/LOCAL]."""
        mem_item = self.agent._memory.remember(
            content="Primary development branch is master",
            memory_type=MemoryType.USER_CONTEXT.value,
            importance=0.9,
        )
        self.assertIsNotNone(mem_item)
        self.assertIn("master", mem_item.content)

    def test_mission_02_retrieve_stored_information(self):
        """Mission 2: Retrieve Stored Information [Mode: LOCAL]."""
        self.agent._vault.store_context("primary_branch", {"branch": "master"}, category="user_preference")
        ctxs = self.agent._vault.retrieve_context("branch")
        self.assertTrue(len(ctxs) > 0)
        self.assertEqual(ctxs[0]["data"]["branch"], "master")

    def test_mission_03_update_stored_information(self):
        """Mission 3: Update Stored Information [Mode: LOCAL]."""
        vault = self.agent._vault
        vault.store_context("preferred_editor", {"editor": "vscode"}, category="pref")
        updated = vault.store_context("preferred_editor", {"editor": "neovim"}, category="pref")
        self.assertTrue(updated)

        res = vault.retrieve_context("preferred_editor")
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["data"]["editor"], "neovim")

    def test_mission_04_basic_reasoning_task(self):
        """Mission 4: Basic Reasoning Task [Mode: MOCK/LOCAL]."""
        res: AgentRunResult = self.agent.run("Basic reasoning task check")
        self.assertTrue(res.success)
        self.assertEqual(res.status, "COMPLETED")

    def test_mission_05_multi_step_planning_task(self):
        """Mission 5: Multi-Step Planning Task [Mode: MOCK/LOCAL]."""
        res: AgentRunResult = self.agent.run("Inspect workspace architecture and verify docs")
        self.assertTrue(res.success)
        self.assertTrue(len(res.plan_steps) >= 1)

    def test_mission_06_vault_read_write(self):
        """Mission 6: Vault Read/Write [Mode: LOCAL]."""
        vault = PersonalVaultAdapter()
        w_ok = vault.store_context("github_org", {"org": "hgblue09124"}, category="config")
        self.assertTrue(w_ok)

        read_back = vault.retrieve_context("github_org")
        self.assertEqual(len(read_back), 1)
        self.assertEqual(read_back[0]["data"]["org"], "hgblue09124")

    def test_mission_07_capability_discovery(self):
        """Mission 7: Capability Discovery [Mode: LOCAL]."""
        specs = self.agent._capabilities.list_specs()
        cap_ids = [s.capability_id for s in specs]
        self.assertIn("github_integration", cap_ids)
        self.assertIn("mock.echo", cap_ids)

    def test_mission_08_capability_execution(self):
        """Mission 8: Capability Execution [Mode: MOCK/LOCAL or REAL_EXTERNAL]."""
        has_token = bool(os.getenv("GITHUB_TOKEN"))
        gh = GitHubCapabilityAdapter()

        if has_token:
            # REAL_EXTERNAL execution when GITHUB_TOKEN is supplied
            res = gh.execute({"action": "get_repo", "owner": "hgblue09124", "repo": "agent-core"})
            self.assertTrue(res.success)
        else:
            # MOCK/LOCAL explicit mock execution when token is absent
            res = gh.execute({"action": "get_repo", "owner": "hgblue09124", "repo": "agent-core", "mock_offline": True})
            self.assertTrue(res.success)
            self.assertTrue(res.metadata.get("simulated_mock"))

    def test_mission_09_policy_denial(self):
        """Mission 9: Policy Denial [Mode: LOCAL]."""
        spec = CapabilitySpec(
            capability_id="readonly_cap",
            name="Read-Only Cap",
            description="Test read-only cap",
            constraints=CapabilityConstraint(read_only=True),
        )
        authorized, reason = self.agent._policy.authorize_capability(
            spec, action="create_issue_comment", inputs={"action": "create_issue_comment"}
        )
        self.assertFalse(authorized)
        self.assertIn("restricted to read-only actions", reason)

    def test_mission_10_approval_required_action(self):
        """Mission 10: Approval-Required Write Action [Mode: LOCAL]."""
        spec = self.agent._capabilities.get("github_integration").get_spec()

        # Unapproved -> Denied
        auth_unapproved, reason = self.agent._policy.authorize_capability(
            spec, action="create_issue_comment", user_approved=False
        )
        self.assertFalse(auth_unapproved)
        self.assertIn("requires explicit user approval", reason)

        # Approved -> Authorized
        auth_approved, reason = self.agent._policy.authorize_capability(
            spec, action="create_issue_comment", user_approved=True
        )
        self.assertTrue(auth_approved)

    def test_mission_11_capability_failure_handling(self):
        """Mission 11: Capability Failure Handling [Mode: MOCK/LOCAL]."""
        class CrashingCap(BaseCapabilityAdapter):
            def get_spec(self):
                return CapabilitySpec(
                    capability_id="crashing_cap",
                    name="Crashing Cap",
                    description="Test crashing cap",
                )

            def execute(self, inputs):
                raise RuntimeError("Internal capability crash")

        self.agent.register_capability(CrashingCap())
        res = self.agent.execute_capability("crashing_cap", {})
        self.assertEqual(res.status, "FAILED")
        self.assertIn("Capability execution exception", res.error)

    def test_mission_12_resume_interrupted_task(self):
        """Mission 12: Resume Interrupted Task Across Process Restart [Mode: LOCAL]."""
        # Instance 1: Initial run created and saved to file storage
        initial_res = self.agent.run("Task for process-restart resume test")
        self.assertTrue(initial_res.success)
        run_id = initial_res.run_id

        # Instance 2: New Agent instance simulating process restart
        fresh_agent = Agent(project_id="default")
        resumed_res = fresh_agent.resume(run_id)
        self.assertEqual(resumed_res.run_id, run_id)
        self.assertTrue(resumed_res.success)

    def test_mission_13_end_to_end_personal_agent_workflow(self):
        """Mission 13: End-to-End Personal-Agent Workflow [Mode: MOCK/LOCAL]."""
        self.agent._vault.store_context("default_repo_topic", {"topic": "agent-core"}, category="workflow")

        res = self.agent.run(
            "Execute workflow with topic context",
            capability_dispatch=(
                "github_integration",
                {"action": "get_repo", "owner": "hgblue09124", "repo": "agent-core", "mock_offline": True},
            ),
        )
        self.assertTrue(res.success)
        self.assertTrue(res.authorized)
        self.assertTrue(res.experience_recorded)

    def test_mission_14_repeated_execution_continuity(self):
        """Mission 14: Repeated Execution & Process-Restart Persistence [Mode: LOCAL]."""
        # Instance 1: Run task and store memory
        res1 = self.agent.run("First process run task")
        self.assertTrue(res1.success)
        run_id1 = res1.run_id

        # Instance 2: Fresh Agent instance simulating process restart
        restart_agent = Agent(project_id="default")

        # Verify experience persisted across process restart
        persisted_exp = restart_agent._experience_engine.get_experience(run_id1)
        self.assertIsNotNone(persisted_exp)
        self.assertEqual(persisted_exp.run_id, run_id1)

        # Execute subsequent task on restarted instance
        res2 = restart_agent.run("Second process run task")
        self.assertTrue(res2.success)
        self.assertNotEqual(res1.run_id, res2.run_id)

    def test_mission_15_external_capability_failure_without_false_success(self):
        """Mission 15: External Capability Failure Without False Success [Mode: MOCK/LOCAL]."""
        gh = GitHubCapabilityAdapter()

        for http_code in (401, 403, 404, 503):
            with patch.object(gh, "_http_request", return_value=(http_code, {"error": f"HTTP {http_code} Error"})):
                res = gh.execute({"action": "get_repo", "owner": "owner", "repo": "repo"})
                self.assertFalse(res.success, f"HTTP {http_code} must not return success")
                self.assertEqual(res.status, "FAILED")
                self.assertIn(f"HTTP {http_code}", res.error)


if __name__ == "__main__":
    unittest.main()
