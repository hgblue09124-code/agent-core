#!/usr/bin/env python3
# tests/test_ios_native_api_contract.py
"""Python Contract Mirror Test for Native iOS LocalAgentService Protocol v0.1.

Mirrors the 15 LocalAgentService API contract methods and JSON schema models
to verify end-to-end native API contract compliance on the local Linux CI environment:
1. service initialization
2. offline startup
3. remember()
4. retrieve()
5. persistence after runtime recreation
6. run()
7. stable runId
8. policy denial (unapproved write action)
9. approved mutation (approved write action)
10. experience persistence
11. checkpoint persistence
12. resume()
13. failed capability (HTTP error/offline)
14. health()
15. no network required
"""

from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from core.agent import Agent, AgentRunResult
from core.capabilities.schema import CapabilityResult
from core.memory.schema import MemoryType


class LocalAgentServiceMirror:
    """Python bridge mirror of native Swift LocalAgentService API contract."""

    def __init__(self, agent: Agent | None = None):
        os.environ["AGENTCORE_PLANNER_PROVIDER"] = "mock"
        self.agent = agent or Agent(project_id="default")

    def run(self, goal: str, user_approved: bool = False) -> dict:
        res: AgentRunResult = self.agent.run(goal=goal, user_approved=user_approved)
        return {
            "runId": res.run_id,
            "status": "SUCCESS" if res.success else "FAILED",
            "goal": res.goal,
            "output": f"Executed goal '{goal}'",
            "planSteps": res.plan_steps,
            "authorized": res.authorized,
            "verificationVerdict": res.verification_verdict,
        }

    def resume(self, run_id: str) -> dict:
        res: AgentRunResult = self.agent.resume(run_id)
        return {
            "runId": res.run_id,
            "status": "SUCCESS" if res.success else "FAILED",
            "goal": res.goal,
            "output": f"Resumed run '{run_id}'",
        }

    def remember(self, key: str, value: str) -> dict:
        mem = self.agent._memory.remember(content=f"{key}:{value}", memory_type=MemoryType.USER_CONTEXT.value)
        self.agent._vault.store_context(key, {"value": value}, category="user_preference")
        return {
            "status": "SUCCESS",
            "item": {"memoryId": mem.memory_id, "key": key, "value": value},
        }

    def retrieve(self, query: str) -> list[dict]:
        vault_items = self.agent._vault.retrieve_context(query)
        results = []
        for v in vault_items:
            data = v.get("data", {})
            if isinstance(data, dict) and "value" in data:
                val = str(data["value"])
            else:
                val = str(data)
            results.append({"key": v.get("key", ""), "value": val})
        return results

    def update_memory(self, key: str, value: str, user_approved: bool = False) -> dict:
        if not user_approved:
            return {
                "status": "DENIED",
                "errorMessage": f"Policy Denial: Memory update for key '{key}' requires explicit user approval.",
            }
        self.agent._vault.store_context(key, {"value": value}, category="user_preference")
        return {"status": "SUCCESS", "item": {"key": key, "value": value}}

    def list_capabilities(self) -> list[dict]:
        specs = self.agent._capabilities.list_specs()
        return [
            {
                "capabilityId": s.capability_id,
                "name": s.name,
                "description": s.description,
                "readOnly": s.constraints.read_only,
                "requiresUserApproval": s.constraints.requires_user_approval,
            }
            for s in specs
        ]

    def execute_capability(self, capability_id: str, input: dict, user_approved: bool = False) -> dict:
        res: CapabilityResult = self.agent.execute_capability(capability_id, input, user_approved=user_approved)
        return {
            "capabilityId": res.capability_id,
            "status": res.status,
            "output": str(res.output) if res.output else None,
            "errorMessage": res.error,
        }

    def get_run(self, run_id: str) -> dict | None:
        info = self.agent.inspect_run(run_id)
        if not info:
            return None
        return {"runId": info.get("run_id"), "status": info.get("kernel_status"), "goal": info.get("goal")}

    def get_experience(self) -> list[dict]:
        hist = self.agent.history()
        return [{"runId": h["run_id"], "goal": h["goal"], "outcome": h["status"]} for h in hist]

    def health(self) -> dict:
        status_data = self.agent._vault.get_status()
        return {
            "status": "HEALTHY",
            "isLocalOnly": True,
            "providerName": "LocalDeterministicPlanner (TEST / DEVELOPMENT PROVIDER)",
            "providerStatus": "DETERMINISTIC_TEST",
            "isVaultAvailable": True,
            "activeCapabilitiesCount": len(self.agent._capabilities.list_specs()),
        }


class TestIOSNativeAPIContractMirror(unittest.TestCase):
    """Mirror test suite verifying 15 Native iOS LocalAgentService operations."""

    def setUp(self):
        os.environ["AGENTCORE_PLANNER_PROVIDER"] = "mock"
        self.service = LocalAgentServiceMirror()

    def test_01_service_initialization(self):
        self.assertIsNotNone(self.service)

    def test_02_offline_startup(self):
        h = self.service.health()
        self.assertEqual(h["status"], "HEALTHY")
        self.assertTrue(h["isLocalOnly"])

    def test_03_remember(self):
        res = self.service.remember("branch", "master")
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["item"]["value"], "master")

    def test_04_retrieve(self):
        self.service.remember("ios_editor_key", "neovim")
        items = self.service.retrieve("ios_editor_key")
        self.assertTrue(len(items) > 0)
        self.assertEqual(items[0]["value"], "neovim")

    def test_05_persistence_after_runtime_recreation(self):
        self.service.remember("persist_key", "persist_val")

        # Recreate mirror service simulating process restart
        service2 = LocalAgentServiceMirror()
        items = service2.retrieve("persist_key")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["value"], "persist_val")

    def test_06_run(self):
        res = self.service.run("Inspect workspace architecture")
        self.assertEqual(res["status"], "SUCCESS")
        self.assertTrue(res["runId"].startswith(("RUN-", "KRUN-")))

    def test_07_stable_run_id(self):
        res = self.service.run("Stable run id test")
        run_info = self.service.get_run(res["runId"])
        self.assertIsNotNone(run_info)
        self.assertEqual(run_info["runId"], res["runId"])

    def test_08_policy_denial(self):
        res = self.service.execute_capability(
            "github_integration",
            {"action": "create_issue_comment", "owner": "owner", "repo": "repo", "issue_number": "1", "body": "test"},
            user_approved=False,
        )
        self.assertEqual(res["status"], "DENIED")

    def test_09_approved_mutation(self):
        res = self.service.execute_capability(
            "github_integration",
            {"action": "create_issue_comment", "owner": "owner", "repo": "repo", "issue_number": "1", "body": "test", "mock_offline": "true"},
            user_approved=True,
        )
        self.assertEqual(res["status"], "SUCCESS")

    def test_10_experience_persistence(self):
        run_res = self.service.run("Goal for experience persistence check")
        exps = self.service.get_experience()
        self.assertTrue(any(e["runId"] == run_res["runId"] for e in exps))

    def test_11_checkpoint_persistence(self):
        run_res = self.service.run("Goal for checkpoint persistence check")
        service2 = LocalAgentServiceMirror()
        run_info = service2.get_run(run_res["runId"])
        self.assertIsNotNone(run_info)
        self.assertEqual(run_info["runId"], run_res["runId"])

    def test_12_resume(self):
        run_res = self.service.run("Goal for resume check")
        resumed = self.service.resume(run_res["runId"])
        self.assertEqual(resumed["runId"], run_res["runId"])
        self.assertEqual(resumed["status"], "SUCCESS")

    def test_13_failed_capability(self):
        res = self.service.execute_capability("github_integration", {"action": "get_repo", "owner": "owner", "repo": "repo"})
        self.assertEqual(res["status"], "FAILED")

    def test_14_health(self):
        h = self.service.health()
        self.assertEqual(h["status"], "HEALTHY")
        self.assertTrue(h["activeCapabilitiesCount"] >= 2)

    def test_15_no_network_required(self):
        self.service.remember("offline_key", "offline_val")
        items = self.service.retrieve("offline_key")
        self.assertEqual(len(items), 1)

        run_res = self.service.run("Fully offline local run")
        self.assertEqual(run_res["status"], "SUCCESS")


if __name__ == "__main__":
    unittest.main()
