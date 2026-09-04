#!/usr/bin/env python3
# tests/test_personal_agent_beta_smoke.py
"""Personal Agent Beta v0.1 End-to-End Real-World Pipeline Smoke Test Suite.

Verifies the complete Personal Agent Beta v0.1 pipeline:
User Request -> Agent-Core -> Identity/Memory -> PersonalVaultAdapter ->
Reason/Plan -> Policy/Permission -> Capability Dispatch -> Execution ->
Verification -> Experience -> Lesson/Strategy -> Memory/Vault Update -> Resume/Continuity

Explicitly distinguishes execution modes:
- MOCK: Simulated providers and mock capability execution.
- LOCAL: In-memory or local disk filesystem state operations.
- REAL_EXTERNAL: Live network calls to external APIs (e.g. GitHub API).
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
from core.capabilities.adapter import BaseCapabilityAdapter
from core.capabilities.github import GitHubCapabilityAdapter
from core.capabilities.schema import CapabilityConstraint, CapabilityResult, CapabilitySpec
from core.memory.schema import MemoryQuery, MemoryType
from core.vault.adapter import BaseVaultAdapter, PersonalVaultAdapter


class TestPersonalAgentBetaEndToEndSmoke(unittest.TestCase):
    """End-to-End Smoke Test Suite for Personal Agent Beta v0.1."""

    def setUp(self):
        os.environ["AGENTCORE_PLANNER_PROVIDER"] = "mock"
        self.agent = Agent(project_id="default")

    def test_01_basic_agent_request(self):
        """1. Check Basic Agent request execution [Mode: MOCK/LOCAL]."""
        res: AgentRunResult = self.agent.run("Basic agent request check")
        self.assertTrue(res.success)
        self.assertEqual(res.status, "COMPLETED")
        self.assertEqual(res.verification_verdict, "PASS")

    def test_02_personal_context_retrieval(self):
        """2. Check Personal context retrieval [Mode: LOCAL]."""
        vault = self.agent._vault
        vault.store_context("user_preference_editor", {"preferred_editor": "vscode"}, category="user_preference")

        ctxs = vault.retrieve_context("vscode")
        self.assertTrue(len(ctxs) > 0)
        self.assertEqual(ctxs[0]["data"]["preferred_editor"], "vscode")

    def test_03_vault_read_write(self):
        """3. Check Vault read/write operations [Mode: LOCAL]."""
        vault = PersonalVaultAdapter()
        ok_write = vault.store_context("test_key", {"val": 123}, category="test")
        self.assertTrue(ok_write)

        read_res = vault.retrieve_context("test_key")
        self.assertEqual(len(read_res), 1)
        self.assertEqual(read_res[0]["data"]["val"], 123)

    def test_04_capability_dispatch(self):
        """4. Check capability dispatch mechanism [Mode: MOCK/LOCAL]."""
        res: CapabilityResult = self.agent.execute_capability(
            "mock.echo",
            {"text": "smoke_test_dispatch"},
        )
        self.assertTrue(res.success)
        self.assertEqual(res.output, {"echo": "ECHO: smoke_test_dispatch"})

    def test_05_policy_authorization(self):
        """5. Check policy authorization enforcement [Mode: LOCAL]."""
        # Read-only capability attempting write action -> Policy Denial
        spec = CapabilitySpec(
            capability_id="readonly_test_cap",
            name="Read-Only Cap",
            description="Read-only test",
            constraints=CapabilityConstraint(read_only=True),
        )

        authorized, reason = self.agent._policy.authorize_capability(
            spec, action="create_issue_comment", inputs={"action": "create_issue_comment"}
        )
        self.assertFalse(authorized)
        self.assertIn("restricted to read-only actions", reason)

    def test_06_capability_execution(self):
        """6. Check GitHub capability execution [Mode: MOCK/LOCAL or REAL_EXTERNAL]."""
        gh = GitHubCapabilityAdapter()
        # Explicit mock mode used for deterministic offline test verification
        res = gh.execute({"action": "get_repo", "owner": "hgblue09124", "repo": "agent-core", "mock_offline": True})
        self.assertTrue(res.success)
        self.assertEqual(res.output["action"], "get_repo")

    def test_07_successful_result_propagation(self):
        """7. Check successful result propagation through AgentRunResult [Mode: LOCAL]."""
        res: AgentRunResult = self.agent.run(
            "Run task with github capability dispatch",
            capability_dispatch=(
                "github_integration",
                {"action": "get_repo", "owner": "hgblue09124", "repo": "agent-core", "mock_offline": True},
            ),
        )

        self.assertTrue(res.success)
        self.assertTrue(any("github_integration" in obs for obs in res.observations))

    def test_08_experience_recording(self):
        """8. Check experience recording in Experience Engine [Mode: LOCAL]."""
        res = self.agent.run("Smoke task for experience recording")
        self.assertTrue(res.experience_recorded)

        exp = self.agent._experience_engine.get_experience(res.run_id)
        self.assertIsNotNone(exp)
        self.assertEqual(exp.run_id, res.run_id)

    def test_09_memory_context_persistence(self):
        """9. Check memory & vault context update and persistence [Mode: LOCAL]."""
        res = self.agent.run("Rememberable goal for memory check")
        self.assertTrue(res.success)

        # Check memory store contains entry
        mems = self.agent._memory.store.list_all(memory_type=MemoryType.SHORT_TERM.value)
        self.assertTrue(any(res.run_id in str(m.source_run_id) for m in mems))

        # Check vault store contains run history entry
        vault_entry = self.agent._vault.retrieve_context(res.run_id)
        self.assertTrue(len(vault_entry) > 0)

    def test_10_run_resume_continuity(self):
        """10. Check run resume and continuity from checkpoint [Mode: LOCAL]."""
        res = self.agent.run("Initial goal for resume check")
        self.assertTrue(res.success)

        resumed = self.agent.resume(res.run_id)
        self.assertEqual(resumed.run_id, res.run_id)
        self.assertTrue(resumed.success)

    def test_11_capability_failure_does_not_corrupt_core(self):
        """11. Check capability failure fault isolation [Mode: MOCK/LOCAL]."""
        class FailingCap(BaseCapabilityAdapter):
            def get_spec(self):
                return CapabilitySpec(
                    capability_id="failing_cap",
                    name="Failing Capability",
                    description="Fails with exception",
                )

            def execute(self, inputs):
                raise Exception("Simulated capability crash")

        self.agent.register_capability(FailingCap())

        res = self.agent.run(
            "Goal with failing capability",
            capability_dispatch=("failing_cap", {}),
        )
        # Capability error captured without crashing Agent-Core
        self.assertFalse(res.success)
        self.assertTrue(any("failing_cap" in err for err in res.errors))

    def test_12_full_end_to_end_beta_flow(self):
        """12. Check complete Beta v0.1 E2E pipeline execution [Mode: MOCK/LOCAL]."""
        # Store initial personal preference in vault matching query term
        self.agent._vault.store_context("github_default_owner", {"owner": "hgblue09124", "topic": "pipeline"}, category="user_config")

        # Execute request that uses vault personal context + capability dispatch + policy check + experience + memory
        res = self.agent.run(
            "Execute pipeline test with github context",
            capability_dispatch=(
                "github_integration",
                {"action": "get_repo", "owner": "hgblue09124", "repo": "agent-core", "mock_offline": True},
            ),
        )

        self.assertTrue(res.success)
        self.assertEqual(res.status, "COMPLETED")
        self.assertEqual(res.verification_verdict, "PASS")
        self.assertTrue(res.authorized)
        self.assertTrue(res.experience_recorded)
        self.assertTrue(any("Vault personal context" in obs for obs in res.observations))
        self.assertTrue(any("github_integration" in obs for obs in res.observations))


if __name__ == "__main__":
    unittest.main()
