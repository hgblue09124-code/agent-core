#!/usr/bin/env python3
# tests/test_ios_portability_and_boundaries.py
"""Portability and Dependency Boundary Verification Test Suite for iOS Local Runtime.

Verifies that Agent-Core remains a clean, portable kernel suitable for embedding
inside a native local iOS runtime:
1. Agent initializes cleanly without cloud services.
2. Memory persists locally across Agent reinstantiations.
3. Experience persists locally across Agent reinstantiations.
4. Policy denial and write approval checks are strictly enforced.
5. Capability failures return status="FAILED" without crashing kernel.
6. Offline local operations function without network connectivity.
7. Vault is replaceable.
8. Automated Dependency Boundary Check: Verifies Agent-Core imports ZERO concrete Apple/platform UI/cloud frameworks (UIKit, SwiftUI, CloudKit, CoreData, etc.).
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
from core.capabilities.schema import CapabilityConstraint, CapabilityResult, CapabilitySpec
from core.memory.schema import MemoryQuery, MemoryType
from core.vault.adapter import BaseVaultAdapter, PersonalVaultAdapter


class TestIOSPortabilityAndBoundaries(unittest.TestCase):
    """Automated Portability and Platform Boundary Test Suite."""

    def setUp(self):
        os.environ["AGENTCORE_PLANNER_PROVIDER"] = "mock"

    def test_01_agent_initialization_without_cloud_services(self):
        """1. Verify Agent initializes cleanly in local offline environment."""
        agent = Agent(project_id="default")
        self.assertIsNotNone(agent)
        self.assertEqual(agent.project_id, "default")

    def test_02_local_memory_persistence(self):
        """2. Verify memory persists locally across Agent reinstantiations."""
        agent1 = Agent(project_id="default")
        mem1 = agent1._memory.remember(
            content="Local iOS sandbox memory test",
            memory_type=MemoryType.USER_CONTEXT.value,
            importance=0.8,
        )
        self.assertIsNotNone(mem1)

        # Fresh instance simulating app restart
        agent2 = Agent(project_id="default")
        retrieved = agent2._memory.get_user_context()
        self.assertTrue(any("Local iOS sandbox memory test" in m.content for m in retrieved))

    def test_03_local_experience_persistence(self):
        """3. Verify experience persists locally across Agent reinstantiations."""
        agent1 = Agent(project_id="default")
        res1: AgentRunResult = agent1.run("Experience persistence check for iOS")
        self.assertTrue(res1.success)
        run_id = res1.run_id

        # Fresh instance simulating app restart
        agent2 = Agent(project_id="default")
        exp = agent2._experience_engine.get_experience(run_id)
        self.assertIsNotNone(exp)
        self.assertEqual(exp.run_id, run_id)

    def test_04_policy_denial_and_write_approval(self):
        """4. Verify policy denial and write approval checks remain authoritative."""
        agent = Agent(project_id="default")

        # Unapproved write -> DENIED
        res_denied = agent.execute_capability(
            "github_integration",
            {"action": "create_issue_comment", "owner": "owner", "repo": "repo", "issue_number": 1, "body": "test"},
            user_approved=False,
        )
        self.assertFalse(res_denied.success)
        self.assertEqual(res_denied.status, "DENIED")

        # Approved write -> AUTHORIZED
        res_approved = agent.execute_capability(
            "github_integration",
            {"action": "create_issue_comment", "owner": "owner", "repo": "repo", "issue_number": 1, "body": "test", "mock_offline": True},
            user_approved=True,
        )
        self.assertTrue(res_approved.success)

    def test_05_capability_failure_propagation(self):
        """5. Verify capability execution failures return FAILED without crashing kernel."""
        class FailingTestCapability(BaseCapabilityAdapter):
            def get_spec(self):
                return CapabilitySpec(capability_id="failing_test_cap", name="Failing Cap", description="Fails on execute")

            def execute(self, inputs):
                raise RuntimeError("Capability internal crash")

        agent = Agent(project_id="default")
        agent.register_capability(FailingTestCapability())

        res = agent.execute_capability("failing_test_cap", {})
        self.assertFalse(res.success)
        self.assertEqual(res.status, "FAILED")
        self.assertIn("Capability execution exception", res.error)

    def test_06_offline_operation_without_network(self):
        """6. Verify Agent runs offline without network connectivity."""
        agent = Agent(project_id="default")
        res = agent.run("Offline local run check")
        self.assertTrue(res.success)
        self.assertEqual(res.status, "COMPLETED")

    def test_07_vault_replaceability(self):
        """7. Verify PersonalVaultAdapter remains pluggable and replaceable."""
        class CustomMockVaultAdapter(BaseVaultAdapter):
            def is_available(self):
                return True

            def store_context(self, key, data, category="user_preference"):
                return True

            def retrieve_context(self, query, limit=5):
                return [{"key": "custom_key", "data": {"custom": "data"}}]

        custom_vault = CustomMockVaultAdapter()
        agent = Agent(project_id="default", vault=custom_vault)

        res = agent._vault.retrieve_context("custom")
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["data"]["custom"], "data")

    def test_08_platform_dependency_boundary_check(self):
        """8. Automated Boundary Check: Verify Agent-Core imports ZERO concrete Apple/UI/cloud frameworks."""
        forbidden_imports = {
            "UIKit", "SwiftUI", "CloudKit", "CoreData", "AppKit",
            "WatchKit", "TVKit", "SceneKit", "Metal", "CoreLocation", "EventKit"
        }

        agent_core_dir = Path(_root) / "core"
        py_files = list(agent_core_dir.rglob("*.py"))
        self.assertTrue(len(py_files) > 0, "No Python source files found in core/")

        violations = []
        for py_file in py_files:
            try:
                content = py_file.read_text(encoding="utf-8")
                for forbidden in forbidden_imports:
                    # Check for direct import or from import of platform frameworks
                    if f"import {forbidden}" in content or f"from {forbidden}" in content:
                        violations.append(f"{py_file.relative_to(_root)} imports forbidden framework '{forbidden}'")
            except Exception as exc:
                self.fail(f"Failed to read file {py_file}: {exc}")

        self.assertEqual(len(violations), 0, f"Platform dependency violations detected: {violations}")


if __name__ == "__main__":
    unittest.main()
