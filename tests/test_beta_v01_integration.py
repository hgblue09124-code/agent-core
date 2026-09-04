#!/usr/bin/env python3
# tests/test_beta_v01_integration.py
"""Focused Beta v0.1 Integration Test Suite for Agent-Core.

Tests the full Beta v0.1 composition: Agent-Core + Personal Vault + External Capabilities.

Coverage:
1. Successful capability execution (GitHub capability target).
2. Capability permission and policy denial.
3. Capability failure propagation (ensuring Core integrity is preserved).
4. Personal Vault integration and local fallback when external package is absent.
5. Experience persistence and run state continuation via agent.resume(run_id).
6. Core functionality without optional external integrations.
7. Architectural boundary isolation.
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
from core.capabilities.adapter import BaseCapabilityAdapter
from core.capabilities.bridge import ExternalCapabilityBridge
from core.capabilities.github import GitHubCapabilityAdapter
from core.capabilities.schema import CapabilityConstraint, CapabilityResult, CapabilitySpec
from core.kernel.policy import PolicyEngine
from core.vault.adapter import BaseVaultAdapter, PersonalVaultAdapter


class TestPersonalVaultAdapter(unittest.TestCase):
    """Test Personal Vault integration & narrow storage adapter."""

    def test_vault_local_fallback_when_external_absent(self):
        vault = PersonalVaultAdapter()
        self.assertFalse(vault.is_available())
        status = vault.get_status()
        self.assertFalse(status["available"])
        self.assertIsNone(status["external_vault_type"])

        # Store personal context into fallback
        stored = vault.store_context("user_nickname", {"nickname": "Jules"}, category="user_preference")
        self.assertTrue(stored)

        # Retrieve context
        results = vault.retrieve_context("Jules")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["key"], "user_nickname")
        self.assertEqual(results[0]["data"]["nickname"], "Jules")

    def test_vault_with_mock_external_client(self):
        class MockExternalVault:
            def __init__(self):
                self.store = {}

            def is_available(self):
                return True

            def retrieve_context(self, query, limit=5):
                return [{"key": "github_username", "data": {"username": "hgblue09124"}}]

            def store_context(self, key, data, category="user_preference"):
                self.store[key] = data
                return True

        mock_ext = MockExternalVault()
        vault = PersonalVaultAdapter(external_vault=mock_ext)
        self.assertTrue(vault.is_available())
        self.assertEqual(vault.get_status()["external_vault_type"], "MockExternalVault")

        ctxs = vault.retrieve_context("username")
        self.assertEqual(len(ctxs), 1)
        self.assertEqual(ctxs[0]["data"]["username"], "hgblue09124")

        stored = vault.store_context("theme", {"mode": "dark"})
        self.assertTrue(stored)
        self.assertIn("theme", mock_ext.store)


class TestExternalCapabilityBridgeAndGitHub(unittest.TestCase):
    """Test External Capability Bridge and GitHub Capability Adapter."""

    def test_github_capability_get_repo(self):
        gh = GitHubCapabilityAdapter()
        spec = gh.get_spec()
        self.assertEqual(spec.capability_id, "github_integration")
        self.assertIn("api.github.com", spec.constraints.allowed_domains)

        res = gh.execute({"action": "get_repo", "owner": "hgblue09124", "repo": "agent-core", "mock_offline": True})
        self.assertTrue(res.success)
        self.assertEqual(res.output["action"], "get_repo")

    def test_github_capability_missing_parameters_fails_gracefully(self):
        gh = GitHubCapabilityAdapter()
        res = gh.execute({"action": "get_repo"})
        self.assertFalse(res.success)
        self.assertEqual(res.status, "FAILED")
        self.assertIn("Missing required parameters", res.error)

    def test_external_capability_bridge(self):
        class ExtDummyCap:
            def __init__(self):
                self.capability_id = "external_dummy"
                self.name = "Dummy Ext Cap"
                self.description = "Test external cap"

            def execute(self, inputs):
                return {"status": "SUCCESS", "output": f"Echo: {inputs.get('msg')}"}

        bridge = ExternalCapabilityBridge(ExtDummyCap())
        spec = bridge.get_spec()
        self.assertEqual(spec.capability_id, "external_dummy")

        res = bridge.execute({"msg": "Hello Beta"})
        self.assertTrue(res.success)
        self.assertEqual(res.output, "Echo: Hello Beta")


class TestCapabilityPolicyAndPermissionValidation(unittest.TestCase):
    """Test Capability execution passing through Policy Engine authorization."""

    def setUp(self):
        self.policy = PolicyEngine()

    def test_policy_denies_write_action_on_readonly_capability(self):
        spec = CapabilitySpec(
            capability_id="readonly_cap",
            name="Read-Only Cap",
            description="Spec for read-only capability",
            constraints=CapabilityConstraint(read_only=True),
        )

        authorized, reason = self.policy.authorize_capability(
            spec, action="create_issue_comment", inputs={"action": "create_issue_comment"}
        )
        self.assertFalse(authorized)
        self.assertIn("restricted to read-only actions", reason)

    def test_policy_requires_user_approval(self):
        spec = CapabilitySpec(
            capability_id="sensitive_cap",
            name="Sensitive Cap",
            description="Spec requiring approval",
            constraints=CapabilityConstraint(requires_user_approval=True),
        )

        # Unapproved -> Denied
        authorized, reason = self.policy.authorize_capability(spec, user_approved=False)
        self.assertFalse(authorized)
        self.assertIn("requires explicit user approval", reason)

        # Approved -> Authorized
        authorized, reason = self.policy.authorize_capability(spec, user_approved=True)
        self.assertTrue(authorized)
        self.assertIsNone(reason)


class TestAgentBetaV01AcceptanceFlow(unittest.TestCase):
    """Test complete Beta v0.1 acceptance flow in Agent."""

    def setUp(self):
        os.environ["AGENTCORE_PLANNER_PROVIDER"] = "mock"
        self.agent = Agent(project_id="default")

    def test_agent_execute_capability_success(self):
        res: CapabilityResult = self.agent.execute_capability(
            "github_integration",
            {"action": "list_issues", "owner": "hgblue09124", "repo": "agent-core", "mock_offline": True},
        )
        self.assertTrue(res.success)
        self.assertEqual(res.status, "SUCCESS")

    def test_agent_run_with_capability_dispatch(self):
        res: AgentRunResult = self.agent.run(
            "Inspect repository and list open issues",
            capability_dispatch=(
                "github_integration",
                {"action": "list_issues", "owner": "hgblue09124", "repo": "agent-core", "mock_offline": True},
            ),
        )

        self.assertTrue(res.success)
        self.assertTrue(res.authorized)
        self.assertTrue(any("Capability 'github_integration' executed successfully" in obs for obs in res.observations))

    def test_agent_run_with_policy_denied_capability(self):
        # Register a capability that requires user approval
        class RestrictedCap(BaseCapabilityAdapter):
            def get_spec(self):
                return CapabilitySpec(
                    capability_id="restricted_action",
                    name="Restricted Action",
                    description="Requires user approval",
                    constraints=CapabilityConstraint(requires_user_approval=True),
                )

            def execute(self, inputs):
                return CapabilityResult(capability_id="restricted_action", status="SUCCESS")

        self.agent.register_capability(RestrictedCap())

        res: AgentRunResult = self.agent.run(
            "Attempt unapproved restricted action",
            capability_dispatch=("restricted_action", {"action": "do_something"}),
            user_approved=False,
        )

        self.assertFalse(res.success)
        self.assertEqual(res.status, "FAILED")
        self.assertTrue(any("Policy/Permission denial" in err for err in res.errors))

    def test_capability_failure_does_not_compromise_core_integrity(self):
        """Verify capability runtime exception is handled safely without crashing Core."""
        class CrashingCap(BaseCapabilityAdapter):
            def get_spec(self):
                return CapabilitySpec(
                    capability_id="crashing_capability",
                    name="Crashing Capability",
                    description="Throws unhandled exception",
                )

            def execute(self, inputs):
                raise RuntimeError("Unexpected internal capability failure!")

        self.agent.register_capability(CrashingCap())

        # Direct invocation returns FAILED CapabilityResult
        res = self.agent.execute_capability("crashing_capability", {})
        self.assertEqual(res.status, "FAILED")
        self.assertIn("Capability execution exception", res.error)

        # Agent run with crashing capability captures error gracefully
        run_res = self.agent.run(
            "Run task with crashing capability",
            capability_dispatch=("crashing_capability", {}),
        )
        self.assertFalse(run_res.success)
        self.assertTrue(any("crashing_capability" in err for err in run_res.errors))

    def test_agent_resume_non_terminal_run(self):
        """Verify an interrupted run can be resumed from authoritative checkpoint."""
        # Initial run
        res = self.agent.run("Initial run for resume test")
        self.assertTrue(res.success)

        # Resume the run using run_id
        resumed_res = self.agent.resume(res.run_id)
        self.assertEqual(resumed_res.run_id, res.run_id)
        self.assertTrue(resumed_res.success)
        self.assertIn(f"Resumed run '{res.run_id}'", resumed_res.observations[0])


if __name__ == "__main__":
    unittest.main()
